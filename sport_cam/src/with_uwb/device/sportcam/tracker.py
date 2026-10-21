"""Tracking control loops (docs/04).

Pan is an **absolute position** on the PTZ base: the static anchor bar gives
the subject's bearing from its own normal, and the camera is simply told to
point there. The vision trim does not fight that — it accumulates into a slow
bias that cancels residual ranging error, so UWB sets the coarse angle and the
camera cleans it up.

Tilt works the same way when the third anchor is fitted: A3 gives elevation,
the camera is told to point there, and vision trims a bias. Without A3 — a
two-anchor build, or a frame where A3's range dropped out — tilt falls back
to driving the axis from the detector alone, as it always did.

Zoom and focus both come from distance. Vision then frames the shot: it
zooms so the person fills ZOOM_FILL_TARGET of the frame with a margin all
round, and backs the lens off fast if the body nears an edge.

Acquisition runs the same state machine as the camera-only build. The
difference is SEARCH: the tag gives the subject's location at once, so there
is no sweep; the head turns straight to the bearing.

    (idle, no person in frame)       (idle, person in frame)
               │ session start                │ session start
               ▼                              ▼
    SEARCH ──on target, person seen──► FOUND ──FOUND_CONFIRM_S──► TRACK (recording)
       ▲                                  │
       └──── nobody seen FOUND_LOST_S ────┘

* **idle** — not a tracker mode: the session has not started. The head is
  parked with the lens wide and `watch_idle()` runs the detector at
  DETECT_FPS_IDLE. A session started with a person in frame skips SEARCH and
  begins in FOUND.
* **SEARCH** — turn to the tag's bearing, and hold there ACQUIRE_SETTLE_S
  until the detector sees a person.
* **FOUND** — the same pan, tilt, zoom and focus as recording; the person
  does not have to be centred. Seen throughout FOUND_CONFIRM_S (no gap
  longer than FOUND_LOST_S), the session starts recording and calls
  `confirm()`.
* **TRACK** — recording, for the rest of the session: a hidden tag or a
  missed detection afterwards is ordinary tracking.

Every mode runs the same control loop in `step()`; the modes only decide
when the session moves on.
"""
from __future__ import annotations

import math
import time

from simple_pid import PID

from . import config
from .camera import Camera
from .ptz import Ptz
from .uwb import UwbArray

SEARCH, FOUND, TRACK = "search", "found", "track"


class Tracker:
    def __init__(self, uwb: UwbArray, camera: Camera, ptz: Ptz) -> None:
        self.uwb = uwb
        self.camera = camera
        self.ptz = ptz
        self._pan_pid = PID(**config.PAN_PID, setpoint=0.0,
                            output_limits=(-config.PAN_MAX_DPS, config.PAN_MAX_DPS))
        self._tilt_pid = PID(**config.TILT_PID, setpoint=0.0, output_limits=(-30, 30))
        self._pan_bias = 0.0           # CV-learned correction to the UWB bearing
        self._tilt_bias = 0.0          # same, for the UWB elevation
        self._zoom_scale = 1.0         # vision framing: multiplies the distance zoom
        self._last_seen_at: float | None = None   # last fresh person detection
        self.last_fix_at = time.monotonic()
        self.dist_m: float | None = None
        self._last_step = time.monotonic()
        self._idle_seen_at: float | None = None   # last person detection while idle
        self.reset_lock()

    def lost_for(self) -> float:
        return time.monotonic() - self.last_fix_at

    # ---- session ----------------------------------------------------------
    # Vision must verify: ranging alone never records. FOUND takes the camera
    # pointing where the tag says the subject is AND the detector seeing
    # someone there.
    def reset_lock(self) -> None:
        """Start a new session's acquisition.

        Normally that is SEARCH. If idle had a person in frame, the session
        starts in FOUND; if nobody is seen for FOUND_LOST_S it falls back to
        SEARCH.
        """
        now = time.monotonic()
        self.mode = FOUND if self.idle_person_in_frame else SEARCH
        self._idle_seen_at = None
        self._settled_since: float | None = None
        self._acquiring_since = now
        self._found_since = now
        self._found_seen_at = now

    def confirm(self) -> None:
        """Recording has started: hold the subject for the rest of the session."""
        self.mode = TRACK

    # ---- idle --------------------------------------------------------------
    def watch_idle(self) -> None:
        """One idle tick: keep the lens wide and note whether anyone is in frame.

        Detection runs at DETECT_FPS_IDLE here. A person counts as in frame
        until IDLE_PERSON_HOLD_S passes with no detection, so one missed frame
        does not flip the idle sub-state.
        """
        self.ptz.set_zoom_mm(config.ZOOM_MIN_MM)    # retried: zoom is rate-limited
        box, fresh = self.camera.person_bbox()
        if fresh and box is not None and self.ptz.zoom_mm <= config.ZOOM_MIN_MM:
            self._idle_seen_at = time.monotonic()

    @property
    def idle_person_in_frame(self) -> bool:
        """Idle sub-state: a person was detected within IDLE_PERSON_HOLD_S."""
        return (self._idle_seen_at is not None
                and time.monotonic() - self._idle_seen_at <= config.IDLE_PERSON_HOLD_S)

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
        """Acquiring for a long time without vision agreeing — tell the user."""
        return (self.mode != TRACK and
                time.monotonic() - self._acquiring_since > config.ACQUIRE_STALLED_S)

    def _advance(self, now: float, have_fix: bool, pan_target: float,
                 tilt_target: float | None, saw_person: bool) -> None:
        """SEARCH ⇄ FOUND. FOUND → TRACK is the session's call (`confirm()`)."""
        if self.mode == TRACK:
            return
        on_target = False
        if have_fix:
            # Error against the reachable target: a subject past a soft limit
            # can still be locked onto, from the limit.
            pan_goal = _clamp(pan_target, config.PAN_MIN_DEG, config.PAN_MAX_DEG)
            err = abs(pan_goal - self.ptz.pan_deg)
            if tilt_target is not None:
                tilt_goal = _clamp(tilt_target, config.TILT_MIN_DEG, config.TILT_MAX_DEG)
                err = max(err, abs(tilt_goal - self.ptz.tilt_deg))
            on_target = err <= config.ACQUIRE_POINT_TOL_DEG
        if not on_target:
            self._settled_since = None
        elif self._settled_since is None:
            self._settled_since = now

        if self.mode == SEARCH:
            settled = (self._settled_since is not None
                       and now - self._settled_since >= config.ACQUIRE_SETTLE_S)
            if saw_person and settled:
                self.mode = FOUND
                self._found_since = self._found_seen_at = now
        elif saw_person:
            self._found_seen_at = now
        elif now - self._found_seen_at > config.FOUND_LOST_S:
            self.mode = SEARCH                # gone: the countdown starts again

    def step(self) -> None:
        """One 20 Hz iteration. Commands the PTZ base directly."""
        now = time.monotonic()
        dt = min(now - self._last_step, 0.25)
        self._last_step = now

        target = self.ptz.pan_deg
        tilt_target: float | None = None
        fix = self.uwb.fix()
        have_fix = bool(fix and fix.age_s < 0.5)
        if have_fix:
            self.last_fix_at = now
            self.dist_m = fix.dist_m
            target = math.degrees(fix.theta_rad) + self._pan_bias
            if fix.elev_rad is not None:
                tilt_target = self._aim_tilt(fix.elev_rad, fix.dist_m) + self._tilt_bias
            self._update_zoom(fix.dist_m)
            self._hint_search_column(target)

        # Vision runs at a few frames per second, far slower than this loop.
        # Acting only on a *fresh* box is what stops one measurement being
        # integrated over and over — with a 3 fps detector and a 20 Hz loop
        # that would be nearly seven times the intended gain.
        bbox, fresh = self.camera.person_bbox()
        saw_person = bool(bbox and fresh)
        if saw_person:
            x, y, w, h = bbox
            self._last_seen_at = now
            cx_err = (x + w / 2) - config.PREVIEW_SIZE[0] / 2
            cy_err = (y + h / 2) - config.PREVIEW_SIZE[1] / 2
            # Horizontal: learn a slow bias rather than jogging the axis, so
            # vision never fights the ranging loop.
            self._pan_bias = _clamp(
                self._pan_bias + config.PAN_CV_BIAS_GAIN * cx_err,
                -config.PAN_CV_BIAS_LIMIT, config.PAN_CV_BIAS_LIMIT)
            if tilt_target is not None:
                # Vertical, with A3: the same slow bias as pan. Measured in
                # degrees rather than pixels, so the gain holds across zoom.
                # Pixel y grows downward, so a subject below centre (cy_err
                # > 0) means aim lower.
                self._tilt_bias = _clamp(
                    self._tilt_bias - config.TILT_CV_BIAS_GAIN * self._px_to_vdeg(cy_err),
                    -config.TILT_CV_BIAS_LIMIT, config.TILT_CV_BIAS_LIMIT)
            else:
                # Vertical, without A3: vision is the only elevation source.
                # simple_pid returns Kp·(setpoint − input) = −Kp·cy_err, which
                # is already "down when the subject is low", so it is applied
                # as is.
                self.ptz.nudge_tilt(_clamp(
                    self._tilt_pid(cy_err) * config.TILT_STEP_GAIN,
                    -config.TILT_MAX_DPS * dt * 4, config.TILT_MAX_DPS * dt * 4))
            self._frame_zoom(x, y, w, h)
        elif (self._last_seen_at is None
              or now - self._last_seen_at > config.ZOOM_STALE_S):
            # Vision has gone quiet: ease back toward the looser distance
            # framing, in log space so zooming out and in relax alike.
            k = max(0.0, 1.0 - config.ZOOM_STALE_RELAX * dt)
            self._zoom_scale = math.exp(math.log(self._zoom_scale) * k)

        # No ranging fix means we hold, rather than letting the detector chase
        # whoever happens to be in frame. Vision cannot tell your subject from
        # a bystander; the tag can, and that is the whole reason it is there.

        # Slew-limit so the servos glide instead of snapping between frames.
        max_step = config.PAN_MAX_DPS * dt
        self.ptz.set_pan(self.ptz.pan_deg + _clamp(target - self.ptz.pan_deg,
                                                   -max_step, max_step))
        if tilt_target is not None:
            max_tilt = config.TILT_MAX_DPS * dt
            self.ptz.set_tilt(self.ptz.tilt_deg + _clamp(tilt_target - self.ptz.tilt_deg,
                                                         -max_tilt, max_tilt))
        self._advance(now, have_fix, target, tilt_target, saw_person)

    @staticmethod
    def _aim_tilt(elev_rad: float, dist_m: float) -> float:
        """Elevation at the anchors → tilt angle at the lens, in degrees.

        φ is measured from the A1-A2 plane, but the tilt axis sits about
        10 cm higher. Rebuild the subject's height and horizontal distance,
        move the origin up to the lens, and take the angle again. The aim
        point can also be raised above the tag itself (TAG_AIM_OFFSET_M).
        """
        horiz = dist_m * math.cos(elev_rad)
        height = (dist_m * math.sin(elev_rad) + config.TAG_AIM_OFFSET_M
                  - config.LENS_ABOVE_ANCHORS_M)
        return math.degrees(math.atan2(height, max(0.1, horiz)))

    def _px_to_vdeg(self, dy_px: float) -> float:
        """Vertical pixel offset from centre → degrees, at the current zoom."""
        pw, ph = config.PREVIEW_SIZE
        half_v = math.atan(math.tan(math.radians(self.ptz.hfov_deg / 2)) * ph / pw)
        return math.degrees(math.atan(dy_px / (ph / 2) * math.tan(half_v)))

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
            self._zoom_scale *= config.ZOOM_GUARD_STEP
        else:
            self._zoom_scale *= (config.ZOOM_FILL_TARGET / fill) ** config.ZOOM_VISION_GAIN
        self._zoom_scale = _clamp(self._zoom_scale, config.ZOOM_SCALE_MIN, config.ZOOM_SCALE_MAX)

    def _hint_search_column(self, bearing_deg: float) -> None:
        """Tell the detector which column of the frame the subject is in.

        We know the bearing and where the camera is pointed, so the horizontal
        position is already solved. Vision only has to answer how high.
        """
        off = bearing_deg - self.ptz.pan_deg
        half_fov = max(1.0, self.ptz.hfov_deg / 2)
        if abs(off) >= half_fov:
            self.camera.set_search_column(None)      # off-frame: search it all
            return
        half_w = config.PREVIEW_SIZE[0] / 2
        px = half_w + half_w * math.tan(math.radians(off)) / math.tan(math.radians(half_fov))
        self.camera.set_search_column(px)

    def _update_zoom(self, dist_m: float) -> None:
        # Thin lens: a subject of height H at distance d is f·H/d tall on the
        # sensor. Solve for the f that makes it TARGET_FRAME_FRACTION of the
        # frame height.
        base_mm = (config.TARGET_FRAME_FRACTION * config.SENSOR_H_MM
                   * dist_m / config.SUBJECT_HEIGHT_M)
        efl_mm = _clamp(base_mm * self._zoom_scale, config.ZOOM_MIN_MM, config.ZOOM_MAX_MM)
        # Anti-windup: at the end of the lens's range, keep the vision scale
        # at what the lens can actually do, so it responds at once on the way back.
        self._zoom_scale = _clamp(efl_mm / base_mm, config.ZOOM_SCALE_MIN, config.ZOOM_SCALE_MAX)
        self.ptz.set_focus(dist_m)        # first, so a zoom move refocuses for this distance
        self.ptz.set_zoom_mm(efl_mm)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
