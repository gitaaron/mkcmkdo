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

    awake ──session start──► SEARCH ──on target, tag wearer seen──► FOUND ──FOUND_CONFIRM_S──► TRACK (recording)
                               ▲                                      │
                               └───── tag wearer unseen FOUND_LOST_S ─┘

* **awake** — not a tracker mode: the session has not started. The head is
  parked with the lens wide and `watch_awake()` runs the detector at
  DETECT_FPS_AWAKE for the awake sub-state. That is anyone at all, so unlike
  the camera-only build it never skips SEARCH.
* **SEARCH** — turn to the tag's bearing, and hold there ACQUIRE_SETTLE_S
  until the detector sees the tag wearer (`_match_tag`).
* **FOUND** — the same pan, tilt, zoom and focus as recording; the person
  does not have to be centred. Seen throughout FOUND_CONFIRM_S (no gap
  longer than FOUND_LOST_S), and clearly the tag wearer rather than someone
  beside them, the session starts recording and calls `confirm()`.
* **TRACK** — recording, for the rest of the session: a hidden tag or a
  missed detection afterwards is ordinary tracking. With the wearer out of
  sight LOST_ZOOM_OUT_S, the lens zooms straight out to wide (still turning
  with the tag) so vision can find them again, and closes back in once it
  does.

Every mode runs the same control loop in `step()`; the modes only decide
when the session moves on.
"""
from __future__ import annotations

import math
import time
from collections import deque

from simple_pid import PID

from . import config
from .boxlog import CLIMBER, OTHER, UNSURE, Box
from .camera import Camera
from .motion import ease_to
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
        self._pan_vel = 0.0            # deg/s, for easing toward the target
        self._tilt_vel = 0.0
        self._looking_wide = False     # recording, wearer out of sight: lens wide
        self._last_seen_at: float | None = None   # last fresh person detection
        self.last_fix_at = time.monotonic()
        self.dist_m: float | None = None
        self._last_step = time.monotonic()
        self._awake_seen_at: float | None = None   # last person detection while awake
        self._people: list[_Person] = []          # everyone in the tag's gate
        self._chosen: _Person | None = None       # the one taken for the tag wearer
        self._admitted: list[Box] = []            # boxes of people in the gate, last detection
        # every box of the last fresh detection, labelled for the recording's
        # overlay (boxlog): climber, other, or unsure
        self.labelled: list[tuple[Box, str]] = []
        self.labelled_at: float | None = None
        self._poses: deque[tuple[float, float, float]] = deque(maxlen=40)   # (t, pan, tilt), 2 s
        self._view_pan = 0.0           # pan when the latest detection's frame was taken
        self.reset_lock()

    def lost_for(self) -> float:
        return time.monotonic() - self.last_fix_at

    # ---- session ----------------------------------------------------------
    # Vision must verify: ranging alone never records. FOUND takes the camera
    # pointing where the tag says the subject is AND the detector seeing the
    # tag wearer there — not merely someone.
    def reset_lock(self) -> None:
        """Start a new session's acquisition, always in SEARCH.

        Awake's person in frame is not used: it could be anyone, and only the
        tag can say who.
        """
        now = time.monotonic()
        self.mode = SEARCH
        self._awake_seen_at = None
        self._settled_since: float | None = None
        self._acquiring_since = now
        self._people, self._chosen = [], None
        self._found_since = self._found_seen_at = now

    def confirm(self) -> None:
        """Recording has started: hold the subject for the rest of the session."""
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
            self._awake_seen_at = time.monotonic()

    def forget_awake(self) -> None:
        """Going to sleep: nobody is known to be in frame any more."""
        self._awake_seen_at = None

    @property
    def awake_person_in_frame(self) -> bool:
        """Awake sub-state: a person was detected within AWAKE_PERSON_HOLD_S."""
        return (self._awake_seen_at is not None
                and time.monotonic() - self._awake_seen_at <= config.AWAKE_PERSON_HOLD_S)

    # ---- status the rest of the system reads -------------------------------
    def found_for(self) -> float:
        """Seconds in FOUND (0 in any other mode)."""
        return time.monotonic() - self._found_since if self.mode == FOUND else 0.0

    @property
    def ready_to_record(self) -> bool:
        """The tag wearer has stayed in frame for FOUND_CONFIRM_S, and is
        clearly the tag wearer rather than someone beside them."""
        return (self.mode == FOUND and self.found_for() >= config.FOUND_CONFIRM_S
                and self._chosen_is_clear())

    def _chosen_is_clear(self) -> bool:
        """Nobody else in the gate is anywhere near as close to the tag."""
        c = self._chosen
        return c is not None and all(
            p is c or p.miss() >= c.miss() + _lead_needed(c, p) for p in self._people)

    @property
    def crowded(self) -> bool:
        """More than one person has come through the tag's gate lately."""
        return len(self._people) > 1

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
                 tilt_target: float | None, saw_wearer: bool) -> None:
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
            if saw_wearer and settled:
                self.mode = FOUND
                self._found_since = self._found_seen_at = now
        elif saw_wearer:
            self._found_seen_at = now
        elif now - self._found_seen_at > config.FOUND_LOST_S:
            self.mode = SEARCH                # gone: the countdown starts again

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

    def _box_deg(self, box: tuple[int, int, int, int]) -> float:
        """A box's centre as a pan bearing, in the same frame as the tag's."""
        x, _, w, _ = box
        half_w = config.PREVIEW_SIZE[0] / 2
        half_fov = math.radians(max(1.0, self.ptz.hfov_deg) / 2)
        off = math.atan((x + w / 2 - half_w) / half_w * math.tan(half_fov))
        return self._view_pan + math.degrees(off)

    def _range_agrees(self, box: tuple[int, int, int, int], dist_m: float) -> bool:
        """Does the box's height put the person roughly at the tag's distance?

        Thin lens again: a SUBJECT_HEIGHT_M body h pixels tall is f·H/h away.
        Loose on purpose (height, pose). A box clipped at the top or bottom
        shows only part of the body, so it can only prove someone too near.
        """
        _, y, _, h = box
        ph = config.PREVIEW_SIZE[1]
        edge = config.ZOOM_GUARD_EDGE * ph
        body_px = max(1.0, h * config.PERSON_IN_BOX_H)
        seen_m = (config.SUBJECT_HEIGHT_M * self.ptz.zoom_mm / config.SENSOR_H_MM
                  * ph / body_px)
        ratio = seen_m / max(0.1, dist_m)
        if y < edge or y + h > ph - edge:
            return ratio >= 1 / config.TAG_MATCH_RANGE_RATIO
        return 1 / config.TAG_MATCH_RANGE_RATIO <= ratio <= config.TAG_MATCH_RANGE_RATIO

    def _match_tag(self, boxes: list[tuple[int, int, int, int]], tag_deg: float | None,
                   dist_m: float) -> tuple[int, int, int, int] | None:
        """Pick the tag wearer out of one fresh detection, or None.

        Gate each box on the tag (bearing and distance), follow each person
        in the gate from one detection to the next, and keep a running
        average of how far each sits from the tag. See config, "The tag
        wearer, not just a person".
        """
        now = time.monotonic()
        self._admitted = []
        if tag_deg is None and (self.mode != TRACK or self._chosen is None):
            # No ranging. An established subject is followed on position
            # alone; acquisition never proceeds without the tag.
            return None

        # Follow: each box goes to the nearest known person not already
        # taken, if they have moved less than TAG_FOLLOW_DEG. Otherwise it is
        # someone new, admitted only through the gate. Once admitted, a
        # person is averaged on every detection, wherever the noisy tag
        # bearing happens to be, and forgotten only after TAG_FORGET_S out of
        # view, so a rival is never dropped from the comparison by noise.
        seen: dict[int, tuple[int, int, int, int]] = {}
        for box in sorted(boxes, key=lambda b: b[2] * b[3], reverse=True):
            deg = self._box_deg(box)
            free = [p for p in self._people if id(p) not in seen]
            p = min(free, key=lambda p: abs(p.deg - deg), default=None)
            if p is None or abs(p.deg - deg) > config.TAG_FOLLOW_DEG:
                if (tag_deg is None
                        or abs(deg - tag_deg) > config.TAG_MATCH_BEARING_DEG
                        or not self._range_agrees(box, dist_m)):
                    continue
                p = _Person(deg)
                self._people.append(p)
            p.deg, p.seen_at = deg, now
            if tag_deg is not None:
                if not p.looks:
                    p.first_at = now
                p.off_sum += deg - tag_deg
                p.looks += 1
            seen[id(p)] = box
        self._people = [p for p in self._people
                        if now - p.seen_at <= config.TAG_FORGET_S]
        if self._chosen is not None and self._chosen not in self._people:
            self._chosen = None
        self._admitted = list(seen.values())

        if self.mode == SEARCH or self._chosen is None:
            # Take whoever has, on average, been nearest the tag so far.
            if self.mode == FOUND or not seen or tag_deg is None:
                return None                  # FOUND lost them: FOUND_LOST_S decides
            self._chosen = min((p for p in self._people if id(p) in seen),
                               key=lambda p: p.miss())
        elif self.mode == FOUND:
            # Someone else has, on average, been clearly nearer the tag: that
            # is the wearer. Switch to them and count again.
            best = min(self._people, key=lambda p: p.miss())
            if (best is not self._chosen and id(best) in seen
                    and best.miss() + _lead_needed(best, self._chosen) <= self._chosen.miss()):
                self._chosen = best
                self._found_since = self._found_seen_at = now
        return seen.get(id(self._chosen))

    def _label(self, boxes: list[Box], wearer: Box | None,
               have_fix: bool) -> list[tuple[Box, str]]:
        """Label each box of a detection for the recording's overlay.

        The wearer is CLIMBER and everyone else OTHER once the camera can
        tell them apart: recording (TRACK), or the chosen person clear of
        everyone else in the gate. Boxes that all failed the gate are OTHER:
        none of them is where the tag is. Otherwise — two people still being
        told apart, the wearer out of sight while someone in the gate is
        not, or no ranging to judge by — every box is UNSURE.
        """
        if wearer is not None and (self.mode == TRACK or self._chosen_is_clear()):
            return [(b, CLIMBER if b == wearer else OTHER) for b in boxes]
        if not self._admitted and (have_fix or self.mode == TRACK):
            return [(b, OTHER) for b in boxes]
        return [(b, UNSURE) for b in boxes]

    def step(self) -> None:
        """One 20 Hz iteration. Commands the PTZ base directly."""
        now = time.monotonic()
        dt = min(now - self._last_step, 0.25)
        self._last_step = now
        self._poses.append((now, self.ptz.pan_deg, self.ptz.tilt_deg))

        target = self.ptz.pan_deg
        tilt_target: float | None = None
        fix = self.uwb.fix()
        have_fix = bool(fix and fix.age_s < 0.5)
        self._looking_wide = self.mode == TRACK and (
            self._last_seen_at is None or now - self._last_seen_at > config.LOST_ZOOM_OUT_S)
        if have_fix:
            self.last_fix_at = now
            self.dist_m = fix.dist_m
            target = math.degrees(fix.theta_rad) + self._pan_bias
            if fix.elev_rad is not None:
                tilt_target = self._aim_tilt(fix.elev_rad, fix.dist_m) + self._tilt_bias
            self._update_zoom(fix.dist_m)
            self._hint_search_column(target)
        elif self._looking_wide:
            # no tag either: widen anyway, and look at the whole frame
            self.ptz.set_zoom_mm(config.ZOOM_MIN_MM, urgent=True)
            self.camera.set_search_column(None)

        # Vision runs at a few frames per second, far slower than this loop.
        # Acting only on a *fresh* detection is what stops one measurement
        # being integrated over and over — with a 3 fps detector and a 20 Hz
        # loop that would be nearly seven times the intended gain. Only the
        # tag wearer's box is used: a bystander moves nothing.
        boxes, fresh = self.camera.person_boxes()
        bbox = None
        if fresh:
            self._view_pan = self._pose_at(getattr(self.camera, "captured_at", None))[0]
            bbox = self._match_tag(boxes, target if have_fix else None,
                                   fix.dist_m if have_fix else (self.dist_m or 0.0))
        if fresh:
            self.labelled = self._label(boxes, bbox, have_fix)
            self.labelled_at = now
        saw_wearer = bbox is not None
        if saw_wearer:
            x, y, w, h = bbox
            self._last_seen_at = now
            cx_err = (x + w / 2) - config.PREVIEW_SIZE[0] / 2
            cy_err = (y + h / 2) - config.PREVIEW_SIZE[1] / 2
            # Horizontal: learn a slow bias rather than jogging the axis, so
            # vision never fights the ranging loop. Not while two people are
            # still being told apart: the bias would lean toward whoever was
            # chosen first, and the choice is judged against it.
            if self.mode == TRACK or not self.crowded:
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
        elif not self._looking_wide and (
                self._last_seen_at is None or now - self._last_seen_at > config.ZOOM_STALE_S):
            # Vision has gone quiet: ease back toward the looser distance
            # framing, in log space so zooming out and in relax alike.
            k = max(0.0, 1.0 - config.ZOOM_STALE_RELAX * dt)
            self._zoom_scale = math.exp(math.log(self._zoom_scale) * k)

        # No ranging fix means we hold, rather than letting the detector chase
        # whoever happens to be in frame. Vision cannot tell your subject from
        # a bystander; the tag can, and that is the whole reason it is there.

        # Ease rather than slew at full rate, so ranging noise and each
        # vision bias update bend the motion instead of jerking it (motion.ease_to).
        pan, self._pan_vel = ease_to(self.ptz.pan_deg, self._pan_vel, target, dt,
                                     config.PAN_MAX_DPS, config.PAN_MAX_ACCEL_DPS2)
        self.ptz.set_pan(pan)
        if tilt_target is not None:
            tilt, self._tilt_vel = ease_to(self.ptz.tilt_deg, self._tilt_vel, tilt_target, dt,
                                           config.TILT_MAX_DPS, config.TILT_MAX_ACCEL_DPS2)
            self.ptz.set_tilt(tilt)
        else:
            self._tilt_vel = 0.0               # tilt is vision's PID's (nudge_tilt)
        self._advance(now, have_fix, target, tilt_target, saw_wearer)

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
        if self._looking_wide:
            efl_mm = config.ZOOM_MIN_MM       # lost from sight while recording: find them
        else:
            efl_mm = _clamp(base_mm * self._zoom_scale, config.ZOOM_MIN_MM, config.ZOOM_MAX_MM)
        # Anti-windup: at the end of the lens's range, keep the vision scale
        # at what the lens can actually do, so it responds at once on the way back.
        self._zoom_scale = _clamp(efl_mm / base_mm, config.ZOOM_SCALE_MIN, config.ZOOM_SCALE_MAX)
        self.ptz.set_focus(dist_m)        # first, so a zoom move refocuses for this distance
        self.ptz.set_zoom_mm(efl_mm, urgent=self._looking_wide)


class _Person:
    """Someone in the tag's gate, followed across detections."""

    def __init__(self, deg: float) -> None:
        self.deg = deg               # bearing of their box, last detection
        self.seen_at = 0.0
        self.first_at = 0.0          # first detection against the tag
        self.off_sum = 0.0           # Σ (box bearing − tag bearing)
        self.looks = 0

    def miss(self) -> float:
        """How far, on average, they have been from the tag's bearing."""
        return abs(self.off_sum / self.looks) if self.looks else math.inf


def _lead_needed(a: _Person, b: _Person) -> float:
    """How much nearer the tag, on average, `a` must be than `b` to be sure.

    The averages share the tag's bearing noise, and their uncertainty falls
    as the square root of how many independent bearings they span: one per
    TAG_BEARING_CORR_S, the filtered bearing's correlation time. Require
    TAG_MATCH_Z of those, and never less than TAG_MATCH_MARGIN_DEG.
    """
    span = min(a.seen_at - a.first_at, b.seen_at - b.first_at)
    n = max(1.0, span / config.TAG_BEARING_CORR_S)
    return max(config.TAG_MATCH_MARGIN_DEG,
               config.TAG_MATCH_Z * config.TAG_BEARING_SIGMA_DEG / math.sqrt(n))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
