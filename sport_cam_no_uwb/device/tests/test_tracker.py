"""Vision-only tracker checks that need no Pi, no camera and no I2C bus.

A tiny simulated world stands in for the hardware: people stand at bearings
around the camera, the fake camera "sees" those inside the field of view and
reports pixel boxes at the real detector's rate, and the fake PTZ records the
angles it is told. Time is a fake clock, so a thirty-second sweep runs in
milliseconds and every run is identical.

What is checked is what is easy to get wrong and impossible to eyeball:

  * the sweep covers the whole pan range, steps its tilt row, stays inside
    the soft limits and never exceeds the slew limit;
  * the first person seen is the one followed, and a bystander does not steal
    the lock;
  * a lone false positive does not lock;
  * following converges without overshoot, and follows someone who moves;
  * losing the person starts a new sweep;
  * zoom frames the person, and focus distance comes from their size.

    python3 device/tests/test_tracker.py
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config, tracker as tracker_mod
from sportcam.tracker import Tracker

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


# ---- simulated world -------------------------------------------------------
class Clock:
    """Replaces the `time` module inside tracker.py."""
    def __init__(self) -> None:
        self.t = 1000.0

    def monotonic(self) -> float:
        return self.t


CLOCK = Clock()
tracker_mod.time = CLOCK          # the tracker reads time only through this name


class Person:
    def __init__(self, bearing: float, dist: float = 5.0, elev: float = 8.0,
                 height: float = 1.7, visible: bool = True) -> None:
        self.bearing, self.dist, self.elev = bearing, dist, elev
        self.height, self.visible = height, visible


class FakePtz:
    def __init__(self) -> None:
        self.pan_deg = 0.0
        self.tilt_deg = 0.0
        self.zoom_mm = config.ZOOM_MIN_MM
        self.focus_dist: float | None = None
        self.max_pan_step = 0.0

    @property
    def hfov_deg(self) -> float:
        half_w = config.ZOOM_MIN_MM * math.tan(math.radians(config.HFOV_WIDE_DEG / 2))
        return math.degrees(2 * math.atan(half_w / max(0.1, self.zoom_mm)))

    def set_pan(self, deg: float) -> float:
        new = max(config.PAN_MIN_DEG, min(config.PAN_MAX_DEG, deg))
        self.max_pan_step = max(self.max_pan_step, abs(new - self.pan_deg))
        self.pan_deg = new
        return new

    def set_tilt(self, deg: float) -> float:
        self.tilt_deg = max(config.TILT_MIN_DEG, min(config.TILT_MAX_DEG, deg))
        return self.tilt_deg

    def set_zoom_mm(self, mm: float) -> None:
        self.zoom_mm = max(config.ZOOM_MIN_MM, min(config.ZOOM_MAX_MM, mm))

    def set_focus(self, dist: float) -> None:
        self.focus_dist = dist

    def park(self) -> None:
        pass


class SimCamera:
    """Detector at DETECT_FPS_TRACKING; sees people inside the field of view."""

    def __init__(self, ptz: FakePtz, people: list[Person]) -> None:
        self.ptz, self.people = ptz, people
        self._period = 1.0 / config.DETECT_FPS_TRACKING
        self._at = -1e9
        self._boxes: list[tuple[int, int, int, int]] = []
        self.column: float | None = None
        self.detections = 0
        self.spurious: list[tuple[int, int, int, int]] = []   # one-shot false positives

    def set_detect_fps(self, fps: float) -> None:
        self._period = 1.0 / max(0.1, fps)

    def set_search_column(self, cx: float | None) -> None:
        self.column = cx

    def person_boxes(self):
        if CLOCK.t - self._at < self._period:
            return self._boxes, False
        self._at = CLOCK.t
        self.detections += 1
        self._boxes = self.project() + self.spurious
        self.spurious = []
        return self._boxes, True

    def project(self):
        pw, ph = config.PREVIEW_SIZE
        half_h = math.radians(self.ptz.hfov_deg / 2)
        half_v = math.atan(math.tan(half_h) * ph / pw)
        out = []
        for p in self.people:
            if not p.visible:
                continue
            dx = math.radians(p.bearing - self.ptz.pan_deg)
            dy = math.radians(p.elev - self.ptz.tilt_deg)
            if abs(dx) > half_h * 0.95 or abs(dy) > half_v * 0.95:
                continue
            cx = pw / 2 + pw / 2 * math.tan(dx) / math.tan(half_h)
            cy = ph / 2 - ph / 2 * math.tan(dy) / math.tan(half_v)
            body_h = ph * (self.ptz.zoom_mm * p.height / p.dist) / config.SENSOR_H_MM
            h = body_h / config.PERSON_IN_BOX_H
            w = body_h * 0.35 / config.PERSON_IN_BOX_W
            out.append((int(cx - w / 2), int(cy - h / 2), int(w), int(h)))
        return out


def world(*people: Person):
    ptz = FakePtz()
    cam = SimCamera(ptz, list(people))
    return Tracker(cam, ptz), cam, ptz


def run(tr: Tracker, seconds: float, dt: float = 0.05, until=None) -> float:
    """Advance the fake clock, stepping the tracker. Returns seconds elapsed."""
    t0 = CLOCK.t
    while CLOCK.t - t0 < seconds:
        CLOCK.t += dt
        tr.step()
        if until and until():
            break
    return CLOCK.t - t0


def main() -> None:
    print("tracker checks\n")

    # ---- 1. searching an empty room ----------------------------------------
    print("search")
    tr, cam, ptz = world()
    pans, tilts = [], []
    for _ in range(int(40 / 0.05)):
        run(tr, 0.05, 0.05)
        pans.append(ptz.pan_deg)
        tilts.append(ptz.tilt_deg)
    check("starts unlocked in SEARCH", tr.mode == "search" and not tr.locked)
    check("sweep reaches both pan limits",
          min(pans) <= config.PAN_MIN_DEG + 0.5 and max(pans) >= config.PAN_MAX_DEG - 0.5,
          f"{min(pans):.1f}..{max(pans):.1f}")
    check("sweep never leaves the soft limits",
          config.PAN_MIN_DEG <= min(pans) and max(pans) <= config.PAN_MAX_DEG)
    check("sweep visits every tilt row",
          all(any(abs(t - r) < 1.0 for t in tilts) for r in config.SEARCH_TILT_ROWS_DEG),
          f"{sorted(set(round(t) for t in tilts))}")
    check("sweep respects SEARCH_PAN_DPS",
          ptz.max_pan_step <= config.SEARCH_PAN_DPS * 0.05 + 1e-6, f"{ptz.max_pan_step:.2f}°/tick")
    check("lens is wide while sweeping", ptz.zoom_mm == config.ZOOM_MIN_MM)
    check("search stalls after ACQUIRE_STALLED_S", tr.acquire_stalled)
    check("searching_for counts up", tr.searching_for() > 30, f"{tr.searching_for():.1f}")

    # ---- 2. finds and locks a person ---------------------------------------
    print("\nlock-on")
    tr, cam, ptz = world(Person(50.0))
    t = run(tr, 30, until=lambda: tr.locked)
    check("sweep finds a person and locks", tr.locked and tr.ever_locked, f"mode={tr.mode}")
    check("…within one sweep", t < 12, f"{t:.1f}s")
    run(tr, 4)
    check("camera is pointing at them", abs(ptz.pan_deg - 50.0) < 3.0, f"pan {ptz.pan_deg:.1f}")
    check("…and tilted to their height", abs(ptz.tilt_deg - 8.0) < 3.0, f"tilt {ptz.tilt_deg:.1f}")

    # ---- 3. a lone false positive does not lock ------------------------------
    tr, cam, ptz = world()
    run(tr, 3)
    cam.spurious = [(100, 200, 80, 200)]          # appears in one frame only
    run(tr, 0.4)
    check("a sighting stops the sweep (CENTRE)", tr.mode == "centre", tr.mode)
    run(tr, config.CENTRE_TIMEOUT_S + 1.0)
    check("…but one frame never locks; sweep resumes", tr.mode == "search" and not tr.ever_locked,
          f"mode={tr.mode}")

    # ---- 4. the first person found wins; bystanders do not steal the lock ------
    print("\nfirst person")
    a, b = Person(30.0, dist=6.0), Person(-70.0, dist=3.0)     # b is bigger, but behind us
    tr, cam, ptz = world(a, b)
    run(tr, 30, until=lambda: tr.locked)
    run(tr, 3)
    check("locks the first one the sweep reaches", tr.locked and abs(ptz.pan_deg - 30.0) < 4.0,
          f"pan {ptz.pan_deg:.1f}")
    c = Person(45.0, dist=2.0)                                  # a big bystander walks in
    cam.people.append(c)
    run(tr, 8)
    check("a nearer bystander does not take over",
          abs(ptz.pan_deg - 30.0) < 5.0 and tr.locked, f"pan {ptz.pan_deg:.1f}")
    check("detector searches a strip around the person once locked", cam.column is not None)

    # ---- 5. following ----------------------------------------------------------
    print("\nfollowing")
    a = Person(20.0)
    tr, cam, ptz = world(a)
    run(tr, 20, until=lambda: tr.locked)
    run(tr, 4)
    peak = 0.0
    for _ in range(int(4 / 0.05)):
        run(tr, 0.05)
        peak = max(peak, ptz.pan_deg - 20.0)
    check("static subject: settles with no overshoot", peak < 2.0 and abs(ptz.pan_deg - 20.0) < 2.0,
          f"peak +{peak:.1f}°, pan {ptz.pan_deg:.1f}")
    err = []
    for _ in range(int(10 / 0.05)):
        a.bearing += 5.0 * 0.05                                  # walks 5°/s
        run(tr, 0.05)
        err.append(abs(ptz.pan_deg - a.bearing))
    check("walking subject: tracked within 6°", max(err[40:]) < 6.0, f"worst {max(err[40:]):.1f}°")
    check("…and still locked", tr.locked)
    a.bearing = 120.0                                           # beyond the soft limit
    run(tr, 6)
    check("subject past the limit: pan stops at the limit",
          ptz.pan_deg <= config.PAN_MAX_DEG + 1e-9)

    # ---- 6. losing the person ----------------------------------------------------
    print("\nlost")
    a = Person(25.0)
    tr, cam, ptz = world(a)
    run(tr, 20, until=lambda: tr.locked)
    a.visible = False
    run(tr, 1.0)
    check("a missing person is held, not chased", tr.locked)
    check("lost_for rises", tr.lost_for() > 0.5, f"{tr.lost_for():.2f}")
    run(tr, config.RESEARCH_AFTER_S + 0.5)
    check("gone long enough → search again", tr.mode == "search" and not tr.locked)
    check("…but the session remembers it locked once", tr.ever_locked)
    a.visible, a.bearing = True, -50.0
    run(tr, 30, until=lambda: tr.locked)
    check("re-finds them somewhere else", tr.locked and abs(ptz.pan_deg + 50.0) < 4.0,
          f"pan {ptz.pan_deg:.1f}")

    # ---- 7. framing ---------------------------------------------------------------
    print("\nframing")
    far = Person(10.0, dist=7.0)
    tr, cam, ptz = world(far)
    run(tr, 20, until=lambda: tr.locked)
    run(tr, 25)
    body = cam.project()[0][3] * config.PERSON_IN_BOX_H / config.PREVIEW_SIZE[1]
    check("a person across the room is zoomed in on", ptz.zoom_mm > config.ZOOM_MIN_MM + 2.0,
          f"{ptz.zoom_mm:.1f} mm")
    check("…to roughly the fill target", abs(body - config.ZOOM_FILL_TARGET) < 0.2,
          f"fills {body:.2f}")
    check("distance estimate is near the truth", far.dist * 0.7 < (tr.dist_m or 0) < far.dist * 1.4,
          f"{tr.dist_m}")
    check("focus follows the estimate",
          ptz.focus_dist is not None and abs(ptz.focus_dist - (tr.dist_m or 0)) < 1e-6)
    check("zoom stays inside the lens range",
          config.ZOOM_MIN_MM <= ptz.zoom_mm <= config.ZOOM_MAX_MM)

    zoomed = ptz.zoom_mm
    far.visible = False
    run(tr, 5)                                                  # before RESEARCH_AFTER_S
    check("no detections → zoom eases back toward wide", ptz.zoom_mm < zoomed - 0.5,
          f"{zoomed:.1f} → {ptz.zoom_mm:.1f} mm")

    near = Person(10.0, dist=1.6)
    tr, cam, ptz = world(near)
    run(tr, 20, until=lambda: tr.locked)
    run(tr, 10)
    check("a person close in is not zoomed past wide", ptz.zoom_mm <= config.ZOOM_MIN_MM + 0.5,
          f"{ptz.zoom_mm:.1f} mm")

    # ---- 8. a new session starts clean --------------------------------------------
    print("\nreset")
    tr.reset_lock()
    check("reset_lock forgets the subject",
          tr.mode == "search" and not tr.ever_locked and tr.dist_m is None)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all tracker checks passed")


if __name__ == "__main__":
    main()
