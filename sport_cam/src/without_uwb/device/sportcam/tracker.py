"""Vision-only tracking (docs/04).

There is no ranging radio in this build: the camera is the only sense. The
tracker is a small state machine,

    (idle, no person in frame)       (idle, person in frame)
               │ session start                │ session start
               ▼                              ▼
    SEARCH ──person seen──► CENTRE ──N centred detections──► TRACK
       ▲                       │                                │
       └───── nobody seen ◄────┴──── missing RESEARCH_AFTER_S ◄─┘

* **idle** — not a tracker mode: the session has not started. The head is
  parked with the lens wide and `watch_idle()` runs the detector at
  DETECT_FPS_IDLE, so the camera knows whether a person is in frame. A
  session started with a person in frame skips SEARCH and begins in CENTRE
  on that person.
* **SEARCH** — lens wide, sweep pan end to end and step the tilt row at each
  turn-around, until the detector sees a person. The first one wins.
* **CENTRE** — the sweep stops and the camera turns to put that person in the
  middle. A lone false positive does not survive this: it takes
  ACQUIRE_DETECTIONS consecutive centred detections to lock.
* **TRACK** — locked. Pan and tilt follow the person, zoom frames them, and
  among several detections the one nearest the last position is followed, so
  a bystander walking through does not steal the lock. If the person is gone
  for RESEARCH_AFTER_S the camera goes back to SEARCH (the sweep starts toward
  the side they were last heading for).

The detector runs at a few frames per second, far slower than the 20 Hz loop
that calls `step()`. Corrections are therefore applied only on a *fresh*
detection and then held as a goal that the servos slew toward; acting on the
cached box every tick would integrate one measurement many times over.
"""
from __future__ import annotations

import math
import time

from . import config
from .camera import Camera
from .ptz import Ptz

Box = tuple[int, int, int, int]

SEARCH, CENTRE, TRACK = "search", "centre", "track"


class Tracker:
    def __init__(self, camera: Camera, ptz: Ptz) -> None:
        self.camera = camera
        self.ptz = ptz
        self.dist_m: float | None = None   # estimated from the person's size
        self.ever_locked = False           # has this session ever locked on?
        self._idle_box: Box | None = None  # largest person seen while idle
        self._idle_seen_at: float | None = None
        self.reset_lock()

    # ---- session ----------------------------------------------------------
    def reset_lock(self) -> None:
        """Forget any subject and start a new session.

        Normally that is a fresh SEARCH. If idle had a person in frame, the
        sweep is skipped and the session starts in CENTRE on that person; if
        they have gone, CENTRE_TIMEOUT_S later it falls back to SEARCH.
        """
        now = time.monotonic()
        box = self._idle_box if self.idle_person_in_frame else None
        self._idle_box = self._idle_seen_at = None
        self.ever_locked = False
        self._begin_search(now, direction=1 if self.ptz.pan_deg <= 0 else -1)
        if box is not None:
            self._first_sighting(now, box)

    # ---- idle --------------------------------------------------------------
    def watch_idle(self) -> None:
        """One idle tick: keep the lens wide and note whether anyone is in frame.

        Detection runs at DETECT_FPS_IDLE here. A person counts as in frame
        until IDLE_PERSON_HOLD_S passes with no detection, so one missed frame
        does not flip the idle sub-state.
        """
        self.ptz.set_zoom_mm(config.ZOOM_MIN_MM)    # retried: zoom is rate-limited
        boxes, fresh = self.camera.person_boxes()
        if fresh and boxes and self.ptz.zoom_mm <= config.ZOOM_MIN_MM:
            self._idle_box = max(boxes, key=lambda b: b[2] * b[3])
            self._idle_seen_at = time.monotonic()

    @property
    def idle_person_in_frame(self) -> bool:
        """Idle sub-state: a person was detected within IDLE_PERSON_HOLD_S."""
        return (self._idle_seen_at is not None
                and time.monotonic() - self._idle_seen_at <= config.IDLE_PERSON_HOLD_S)

    def _begin_search(self, now: float, direction: int) -> None:
        self.mode = SEARCH
        self._dir = 1 if direction >= 0 else -1
        self._row = 0
        self._searching_since = now
        self._last_step = now
        self._confirmations = 0
        self._last_centre: tuple[float, float] | None = None
        self._last_seen_at: float | None = None
        self._last_side = 0                  # which way the subject was drifting
        self._pan_goal = self.ptz.pan_deg
        self._tilt_goal = self.ptz.tilt_deg
        self._efl = config.ZOOM_MIN_MM
        self.dist_m = None
        self.camera.set_search_column(None)
        self.ptz.set_zoom_mm(config.ZOOM_MIN_MM)
        self.ptz.set_focus(config.SEARCH_FOCUS_M)

    # ---- status the rest of the system reads -------------------------------
    @property
    def locked(self) -> bool:
        return self.mode == TRACK

    @property
    def centred(self) -> int:
        """Consecutive centred detections toward the lock (ACQUIRE_DETECTIONS once locked)."""
        if self.mode == TRACK:
            return config.ACQUIRE_DETECTIONS
        return self._confirmations if self.mode == CENTRE else 0

    @property
    def acquire_stalled(self) -> bool:
        """Searching a long while with nobody found — tell the user."""
        return self.mode == SEARCH and (
            time.monotonic() - self._searching_since > config.ACQUIRE_STALLED_S)

    def searching_for(self) -> float:
        """Seconds the current search has run (0 when not searching)."""
        return time.monotonic() - self._searching_since if self.mode == SEARCH else 0.0

    def lost_for(self) -> float:
        """Seconds a locked-on person has been missing (0 when not locked)."""
        if self.mode != TRACK or self._last_seen_at is None:
            return 0.0
        return time.monotonic() - self._last_seen_at

    # ---- the loop ----------------------------------------------------------
    def step(self) -> None:
        """One 20 Hz iteration. Commands the PTZ base directly."""
        now = time.monotonic()
        dt = min(now - self._last_step, 0.25)
        self._last_step = now

        boxes, fresh = self.camera.person_boxes()
        boxes = boxes if fresh else []

        if self.mode == SEARCH:
            if boxes:
                self._first_sighting(now, max(boxes, key=lambda b: b[2] * b[3]))
            else:
                self._sweep(dt)
            return

        matched = self._select(boxes) if boxes else None
        if matched:
            self._seen(now, matched)
        elif fresh:
            self._confirmations = 0
        self._relax_zoom_if_stale(now, dt)
        if self.mode == TRACK:
            self.ptz.set_zoom_mm(self._efl)      # retry anything the rate limit dropped
        self._slew(dt)

        gone = now - (self._last_seen_at or now)
        if self.mode == CENTRE and gone > config.CENTRE_TIMEOUT_S:
            self._begin_search(now, direction=self._last_side or self._dir)
        elif self.mode == TRACK and gone > config.RESEARCH_AFTER_S:
            self._begin_search(now, direction=self._last_side or self._dir)

    # ---- SEARCH ------------------------------------------------------------
    def _sweep(self, dt: float) -> None:
        # The PTZ rate-limits zoom and focus and drops requests inside the
        # window, so ask again every tick until the lens has arrived.
        self.ptz.set_zoom_mm(config.ZOOM_MIN_MM)
        self.ptz.set_focus(config.SEARCH_FOCUS_M)
        pan = self.ptz.pan_deg + self._dir * config.SEARCH_PAN_DPS * dt
        if pan >= config.PAN_MAX_DEG or pan <= config.PAN_MIN_DEG:
            pan = _clamp(pan, config.PAN_MIN_DEG, config.PAN_MAX_DEG)
            self._dir = -self._dir                       # turn around…
            self._row = (self._row + 1) % len(config.SEARCH_TILT_ROWS_DEG)   # …one row up/down
        self.ptz.set_pan(pan)
        row = _clamp(config.SEARCH_TILT_ROWS_DEG[self._row],
                     config.TILT_MIN_DEG, config.TILT_MAX_DEG)
        step = config.SEARCH_TILT_DPS * dt
        self.ptz.set_tilt(self.ptz.tilt_deg + _clamp(row - self.ptz.tilt_deg, -step, step))
        self._pan_goal, self._tilt_goal = pan, self.ptz.tilt_deg

    def _first_sighting(self, now: float, box: Box) -> None:
        """Stop the sweep and start turning toward the first person seen."""
        self.mode = CENTRE
        self._last_centre = None            # nothing to gate against yet
        self._seen(now, box)
        self._slew(0.05)

    # ---- CENTRE / TRACK ----------------------------------------------------
    def _select(self, boxes: list[Box]) -> Box | None:
        """The detection that is 'our' person, or None.

        With no previous position (first sighting) it is the largest. After
        that, the nearest to where we last saw them, within a gate.
        """
        if self._last_centre is None:
            return max(boxes, key=lambda b: b[2] * b[3])
        lx, ly = self._last_centre
        best = min(boxes, key=lambda b: math.hypot(b[0] + b[2] / 2 - lx, b[1] + b[3] / 2 - ly))
        d = math.hypot(best[0] + best[2] / 2 - lx, best[1] + best[3] / 2 - ly)
        return best if d <= config.TRACK_GATE_FRACTION * config.PREVIEW_SIZE[0] else None

    def _seen(self, now: float, box: Box) -> None:
        x, y, w, h = box
        pw, ph = config.PREVIEW_SIZE
        cx, cy = x + w / 2, y + h / 2
        self._last_seen_at = now
        self._last_centre = (cx, cy)
        cx_err, cy_err = cx - pw / 2, cy - ph / 2
        if abs(cx_err) > config.TRACK_DEADBAND_FRACTION * pw:
            self._last_side = 1 if cx_err > 0 else -1
            self._pan_goal = _clamp(
                self.ptz.pan_deg + config.TRACK_PAN_GAIN * self._px_to_hdeg(cx_err),
                config.PAN_MIN_DEG, config.PAN_MAX_DEG)
        if abs(cy_err) > config.TRACK_DEADBAND_FRACTION * ph:
            # Pixel y grows downward: a person below centre means aim lower.
            self._tilt_goal = _clamp(
                self.ptz.tilt_deg - config.TRACK_TILT_GAIN * self._px_to_vdeg(cy_err),
                config.TILT_MIN_DEG, config.TILT_MAX_DEG)

        centred = (abs(cx_err) <= config.ACQUIRE_CENTRE_FRACTION * pw
                   and abs(cy_err) <= config.ACQUIRE_CENTRE_FRACTION * ph)
        self._confirmations = self._confirmations + 1 if centred else 0
        if self.mode == CENTRE and self._confirmations >= config.ACQUIRE_DETECTIONS:
            self.mode = TRACK
            self.ever_locked = True

        if self.mode == TRACK:
            self.camera.set_search_column(cx)
            self._estimate_distance(h)
            self._frame_zoom(x, y, w, h)

    def _slew(self, dt: float) -> None:
        """Glide the servos toward the goals instead of snapping between frames."""
        max_pan = config.PAN_MAX_DPS * dt
        self.ptz.set_pan(self.ptz.pan_deg + _clamp(self._pan_goal - self.ptz.pan_deg,
                                                   -max_pan, max_pan))
        max_tilt = config.TILT_MAX_DPS * dt
        self.ptz.set_tilt(self.ptz.tilt_deg + _clamp(self._tilt_goal - self.ptz.tilt_deg,
                                                     -max_tilt, max_tilt))

    # ---- geometry ----------------------------------------------------------
    def _px_to_hdeg(self, dx_px: float) -> float:
        """Horizontal pixel offset from centre → degrees, at the current zoom."""
        half_w = config.PREVIEW_SIZE[0] / 2
        return math.degrees(math.atan(
            dx_px / half_w * math.tan(math.radians(self.ptz.hfov_deg / 2))))

    def _px_to_vdeg(self, dy_px: float) -> float:
        """Vertical pixel offset from centre → degrees, at the current zoom."""
        pw, ph = config.PREVIEW_SIZE
        half_v = math.atan(math.tan(math.radians(self.ptz.hfov_deg / 2)) * ph / pw)
        return math.degrees(math.atan(dy_px / (ph / 2) * math.tan(half_v)))

    def _estimate_distance(self, box_h_px: float) -> None:
        """Distance from the person's apparent height, for focus.

        Thin lens: a body of height H at distance d is f·H/d tall on the
        sensor. Solve for d, smoothed because a person's pose changes their
        apparent height from frame to frame.
        """
        _pw, ph = config.PREVIEW_SIZE
        body_on_sensor_mm = max(1e-3, box_h_px * config.PERSON_IN_BOX_H / ph * config.SENSOR_H_MM)
        d = _clamp(self.ptz.zoom_mm * config.SUBJECT_HEIGHT_M / body_on_sensor_mm,
                   config.DIST_MIN_M, config.DIST_MAX_M)
        self.dist_m = d if self.dist_m is None else (
            self.dist_m + config.DIST_SMOOTHING * (d - self.dist_m))
        self.ptz.set_focus(self.dist_m)   # first, so a zoom move refocuses for this distance

    def _frame_zoom(self, x: int, y: int, w: int, h: int) -> None:
        """Zoom so the person fills ZOOM_FILL_TARGET of the frame, with margin.

        Measured on the body, not the padded HOG box. Two parts:

        * **guard** — the body is near an edge, or fills more than
          ZOOM_GUARD_FILL: zoom out a step at once. HOG cannot detect a body
          that is already clipped, so this acts on the approach, and it wins.
        * **fill loop** — otherwise move part of the way toward the target
          fill each detection, in log space so in and out behave alike.
        """
        pw, ph = config.PREVIEW_SIZE
        bw, bh = w * config.PERSON_IN_BOX_W, h * config.PERSON_IN_BOX_H
        cx, cy = x + w / 2, y + h / 2
        left, right, top, bottom = cx - bw / 2, cx + bw / 2, cy - bh / 2, cy + bh / 2
        fill = max(bh / ph, bw / pw, 1e-3)
        ex, ey = config.ZOOM_GUARD_EDGE * pw, config.ZOOM_GUARD_EDGE * ph
        near_edge = left < ex or top < ey or right > pw - ex or bottom > ph - ey
        if near_edge or fill > config.ZOOM_GUARD_FILL:
            self._efl *= config.ZOOM_GUARD_STEP
        else:
            self._efl *= (config.ZOOM_FILL_TARGET / fill) ** config.ZOOM_VISION_GAIN
        self._efl = _clamp(self._efl, config.ZOOM_MIN_MM, config.ZOOM_MAX_MM)
        self.ptz.set_zoom_mm(self._efl)

    def _relax_zoom_if_stale(self, now: float, dt: float) -> None:
        """No detection for a while: ease back toward wide, in log space."""
        if self.mode != TRACK or self._efl <= config.ZOOM_MIN_MM:
            return
        if self._last_seen_at is not None and now - self._last_seen_at > config.ZOOM_STALE_S:
            k = max(0.0, 1.0 - config.ZOOM_STALE_RELAX * dt)
            ratio = self._efl / config.ZOOM_MIN_MM
            self._efl = config.ZOOM_MIN_MM * math.exp(math.log(ratio) * k)
            self.ptz.set_zoom_mm(self._efl)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
