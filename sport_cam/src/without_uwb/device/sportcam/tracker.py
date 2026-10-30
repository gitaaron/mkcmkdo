"""Vision-only tracking (docs/04).

There is no ranging radio in this build: the camera is the only sense. The
tracker is a small state machine,

    (awake, no person in frame)       (awake, person in frame)
               │ session start                │ session start
               ▼                              ▼
    SEARCH ──person seen──► FOUND ──FOUND_CONFIRM_S──► TRACK (recording)
       ▲                       │                          │
       └─ nobody seen ◄────────┘                          │
          FOUND_LOST_S                                    │
       ▲                                                  │
       └────────────── missing RESEARCH_AFTER_S ◄─────────┤
                                                 missing  │ zoom out
                                          LOST_ZOOM_OUT_S ▼ to wide

* **awake** — not a tracker mode: the session has not started. The head is
  parked with the lens wide and `watch_awake()` runs the detector at
  DETECT_FPS_AWAKE, so the camera knows whether a person is in frame. A
  session started with a person in frame skips SEARCH and begins in FOUND
  on that person.
* **SEARCH** — lens wide, sweep pan end to end and step the tilt row at each
  turn-around, until the detector sees a person. The first one wins. A new
  session holds still until the detector's first look, since the person may
  already be in frame (a session started from sleep knows nothing yet).
* **FOUND** — the sweep stops and the camera follows and frames that person
  exactly as it will while recording; they need not be centred. Seen
  throughout FOUND_CONFIRM_S (no gap longer than FOUND_LOST_S), the session
  starts recording and calls `confirm()`. A lone false positive does not
  survive the wait.
* **TRACK** — recording. Pan and tilt follow the person, zoom frames them,
  and among several detections the one nearest the last position is
  followed, so a bystander walking through does not steal the shot. If the
  person is gone for LOST_ZOOM_OUT_S the lens zooms straight out to wide,
  still pointing where they were, and the detector looks at the whole frame:
  someone who stepped or climbed just out of a tight shot is usually still
  in a wide one, and seen again the zoom closes back in. Gone for
  RESEARCH_AFTER_S the camera goes back to SEARCH (the sweep starts toward
  the side they were last heading for), still recording; the next person
  found goes straight back to TRACK.

The detector runs at a few frames per second, far slower than the 20 Hz loop
that calls `step()`. Corrections are therefore applied only on a *fresh*
detection and then held as a goal that the servos ease toward; acting on the
cached box every tick would integrate one measurement many times over.
"""
from __future__ import annotations

import math
import time
from collections import deque

from . import config
from .boxlog import CLIMBER, OTHER, UNSURE, Box
from .camera import Camera
from .motion import ease_to
from .ptz import Ptz

SEARCH, FOUND, TRACK = "search", "found", "track"


class Tracker:
    def __init__(self, camera: Camera, ptz: Ptz) -> None:
        self.camera = camera
        self.ptz = ptz
        self.dist_m: float | None = None   # estimated from the person's size
        self.confirmed = False             # recording: found people go straight to TRACK
        self._awake_box: Box | None = None  # largest person seen while awake
        self._awake_seen_at: float | None = None
        # every box of the last fresh detection, labelled for the recording's
        # overlay (boxlog): climber, other, or unsure
        self.labelled: list[tuple[Box, str]] = []
        self.labelled_at: float | None = None
        self._poses: deque[tuple[float, float, float]] = deque(maxlen=40)   # (t, pan, tilt), 2 s
        self.reset_lock()

    # ---- session ----------------------------------------------------------
    def reset_lock(self) -> None:
        """Forget any subject and start a new session.

        Normally that is a fresh SEARCH. If awake had a person in frame, the
        sweep is skipped and the session starts in FOUND on that person; if
        they have gone, FOUND_LOST_S later it falls back to SEARCH.

        SEARCH holds still until the detector has taken a fresh look: the
        person may already be in front of the camera — always so when it was
        asleep a moment ago and saw nothing — and the sweep would turn away
        from them.
        """
        now = time.monotonic()
        box = self._awake_box if self.awake_person_in_frame else None
        self._awake_box = self._awake_seen_at = None
        self.confirmed = False
        self._begin_search(now, direction=1 if self.ptz.pan_deg <= 0 else -1)
        self._first_look = True
        if box is not None:
            self._first_sighting(now, box)

    def confirm(self) -> None:
        """Recording has started: follow the person (TRACK) for the rest of it."""
        self.confirmed = True
        if self.mode == FOUND:
            self.mode = TRACK

    # ---- awake --------------------------------------------------------------
    def watch_awake(self) -> None:
        """One awake tick: keep the lens wide and note whether anyone is in frame.

        Detection runs at DETECT_FPS_AWAKE here. A person counts as in frame
        until AWAKE_PERSON_HOLD_S passes with no detection, so one missed frame
        does not flip the awake sub-state.

        Every box is labelled UNSURE for the live view: with no session
        running, nobody has been picked as the climber yet.
        """
        self.ptz.set_zoom_mm(config.ZOOM_MIN_MM)    # retried: zoom is rate-limited
        boxes, fresh = self.camera.person_boxes()
        if fresh:
            self.labelled_at = time.monotonic()
            self.labelled = [(b, UNSURE) for b in boxes]
        if fresh and boxes and self.ptz.zoom_mm <= config.ZOOM_MIN_MM:
            self._awake_box = max(boxes, key=lambda b: b[2] * b[3])
            self._awake_seen_at = time.monotonic()

    def forget_awake(self) -> None:
        """Going to sleep: nobody is known to be in frame any more."""
        self._awake_box = self._awake_seen_at = None

    @property
    def awake_person_in_frame(self) -> bool:
        """Awake sub-state: a person was detected within AWAKE_PERSON_HOLD_S."""
        return (self._awake_seen_at is not None
                and time.monotonic() - self._awake_seen_at <= config.AWAKE_PERSON_HOLD_S)

    def _begin_search(self, now: float, direction: int) -> None:
        self.mode = SEARCH
        self._first_look = False             # re-searching: it has been looking all along
        self._dir = 1 if direction >= 0 else -1
        self._row = 0
        self._searching_since = now
        self._last_step = now
        self._found_since = now
        self._last_centre: tuple[float, float] | None = None
        self._last_seen_at: float | None = None
        self._last_side = 0                  # which way the subject was drifting
        self._pan_goal = self.ptz.pan_deg
        self._tilt_goal = self.ptz.tilt_deg
        self._pan_vel = self._tilt_vel = 0.0   # deg/s, for easing (_slew)
        self._efl = config.ZOOM_MIN_MM
        self.dist_m = None
        self.camera.set_search_column(None)
        self.ptz.set_zoom_mm(config.ZOOM_MIN_MM)
        self.ptz.set_focus(config.SEARCH_FOCUS_M)

    # ---- status the rest of the system reads -------------------------------
    def found_for(self) -> float:
        """Seconds in FOUND (0 in any other mode)."""
        return time.monotonic() - self._found_since if self.mode == FOUND else 0.0

    @property
    def ready_to_record(self) -> bool:
        """The person has stayed in frame for FOUND_CONFIRM_S."""
        return self.mode == FOUND and self.found_for() >= config.FOUND_CONFIRM_S

    @property
    def countdown(self) -> int:
        """Whole seconds left in FOUND before recording (0 outside FOUND)."""
        if self.mode != FOUND:
            return 0
        return max(1, math.ceil(config.FOUND_CONFIRM_S - self.found_for()))

    @property
    def acquire_stalled(self) -> bool:
        """Searching a long while with nobody found — tell the user."""
        return self.mode == SEARCH and (
            time.monotonic() - self._searching_since > config.ACQUIRE_STALLED_S)

    def searching_for(self) -> float:
        """Seconds the current search has run (0 when not searching)."""
        return time.monotonic() - self._searching_since if self.mode == SEARCH else 0.0

    def lost_for(self) -> float:
        """Seconds the person being recorded has been missing (0 outside TRACK)."""
        if self.mode != TRACK or self._last_seen_at is None:
            return 0.0
        return time.monotonic() - self._last_seen_at

    # ---- the loop ----------------------------------------------------------
    def step(self) -> None:
        """One 20 Hz iteration. Commands the PTZ base directly."""
        now = time.monotonic()
        dt = min(now - self._last_step, 0.25)
        self._last_step = now
        self._poses.append((now, self.ptz.pan_deg, self.ptz.tilt_deg))

        boxes, fresh = self.camera.person_boxes()
        boxes = boxes if fresh else []

        if self.mode == SEARCH:
            if boxes:
                first = max(boxes, key=lambda b: b[2] * b[3])
                self._first_sighting(now, first)
                self._label(now, boxes, first)
            else:
                if fresh:
                    self._label(now, boxes, None)
                    self._first_look = False     # looked, and nobody is here: sweep
                if not self._first_look:
                    self._sweep(dt)
            return

        matched = self._select(boxes) if boxes else None
        if fresh:
            self._label(now, boxes, matched)
        if matched:
            self._seen(now, matched)
        gone = now - (self._last_seen_at or now)
        if self.mode == TRACK and gone > config.LOST_ZOOM_OUT_S:
            self._look_wide()
        else:
            self.ptz.set_zoom_mm(self._efl)      # retry anything the rate limit dropped
        self._slew(dt)

        if self.mode == FOUND and gone > config.FOUND_LOST_S:
            self._begin_search(now, direction=self._last_side or self._dir)
        elif self.mode == TRACK and gone > config.RESEARCH_AFTER_S:
            self._begin_search(now, direction=self._last_side or self._dir)

    def _label(self, now: float, boxes: list[Box], followed: Box | None) -> None:
        """Label a fresh detection's boxes for the recording's overlay.

        Without a tag "the climber" can only mean the person being followed:
        CLIMBER, and everyone else OTHER. When that person is out of sight
        and someone else is in frame, the camera cannot tell whether it is
        them, so every box is UNSURE.
        """
        self.labelled_at = now
        self.labelled = [(b, UNSURE if followed is None else CLIMBER if b == followed else OTHER)
                         for b in boxes]

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
        # Moving at sweep speed: a person found now is eased to, not stopped dead for.
        self._pan_vel, self._tilt_vel = self._dir * config.SEARCH_PAN_DPS, 0.0

    def _first_sighting(self, now: float, box: Box) -> None:
        """Stop the sweep and start following the first person seen."""
        self.mode = TRACK if self.confirmed else FOUND
        self._found_since = now
        self._last_centre = None            # nothing to gate against yet
        self._seen(now, box)
        self._slew(0.05)

    # ---- FOUND / TRACK -----------------------------------------------------
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
        # Offsets are from where the head pointed when the frame was taken.
        pan, tilt = self._pose_at(getattr(self.camera, "captured_at", None))
        if abs(cx_err) > config.TRACK_DEADBAND_FRACTION * pw:
            self._last_side = 1 if cx_err > 0 else -1
            self._pan_goal = _clamp(
                pan + config.TRACK_PAN_GAIN * self._px_to_hdeg(cx_err),
                config.PAN_MIN_DEG, config.PAN_MAX_DEG)
        if abs(cy_err) > config.TRACK_DEADBAND_FRACTION * ph:
            # Pixel y grows downward: a person below centre means aim lower.
            self._tilt_goal = _clamp(
                tilt - config.TRACK_TILT_GAIN * self._px_to_vdeg(cy_err),
                config.TILT_MIN_DEG, config.TILT_MAX_DEG)
        self.camera.set_search_column(cx)
        self._estimate_distance(h)
        self._frame_zoom(x, y, w, h)

    def _pose_at(self, t: float | None) -> tuple[float, float]:
        """Pan and tilt when the frame captured at `t` was taken.

        Detection runs on its own thread, so by the time boxes arrive the
        head has moved on; offsets in them are from where it pointed then.
        Falls back to the current pose when `t` is unknown (test cameras) or
        older than the log.
        """
        if t is not None:
            for at, pan, tilt in reversed(self._poses):
                if at <= t:
                    if t - at <= 0.2:
                        return pan, tilt
                    break
        return self.ptz.pan_deg, self.ptz.tilt_deg

    def _slew(self, dt: float) -> None:
        """Ease the servos toward the goals instead of snapping between frames.

        The goals jump a few times a second, on each fresh detection; easing
        spreads each jump over the gap until the next one (see motion.ease_to).
        """
        pan, self._pan_vel = ease_to(self.ptz.pan_deg, self._pan_vel, self._pan_goal, dt,
                                     config.PAN_MAX_DPS, config.PAN_MAX_ACCEL_DPS2)
        self.ptz.set_pan(pan)
        tilt, self._tilt_vel = ease_to(self.ptz.tilt_deg, self._tilt_vel, self._tilt_goal, dt,
                                       config.TILT_MAX_DPS, config.TILT_MAX_ACCEL_DPS2)
        self.ptz.set_tilt(tilt)

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

    def _look_wide(self) -> None:
        """Recording, and the person out of sight LOST_ZOOM_OUT_S: zoom out.

        Straight to the wide end, past the rate limit, still pointing where
        they were last seen, and the detector searches the whole frame rather
        than the strip they were in. Where they were last seen moves toward
        the centre by the zoom ratio, so the follow gate still finds them
        there. Seen again, the fill loop zooms back in from wide.
        """
        if self.ptz.zoom_mm > config.ZOOM_MIN_MM and self._last_centre is not None:
            k = config.ZOOM_MIN_MM / self.ptz.zoom_mm
            pw, ph = config.PREVIEW_SIZE
            lx, ly = self._last_centre
            self._last_centre = (pw / 2 + (lx - pw / 2) * k, ph / 2 + (ly - ph / 2) * k)
        self._efl = config.ZOOM_MIN_MM
        self.ptz.set_zoom_mm(self._efl, urgent=True)
        self.camera.set_search_column(None)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
