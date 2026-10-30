"""Tracking-loop checks that need no Pi, no camera and no I2C bus.

These cover the three things that are easy to get wrong and impossible to
eyeball on hardware:

  * the detector reports freshness, and the tracker acts on it only once —
    the control loop runs far faster than vision, so integrating a repeated
    box would multiply the tilt gain;
  * the bearing-to-pixel hint that crops the detector's search strip;
  * pan slew limiting and the soft limits;
  * tilt from the third anchor, its lens-height correction, and the sign of
    every vertical correction;
  * vision framing: the fill target, the edge guard and the stale relax.

    python3 device/tests/test_tracker.py
"""
from __future__ import annotations

import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config
from sportcam.camera import Camera
from sportcam.tracker import Tracker
from sportcam.uwb import Fix

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


class FakeCamera:
    """Stands in for Camera, with the real rate-limiting behaviour."""

    def __init__(self, bbox):
        self._bbox = bbox
        self._period = 1.0 / config.DETECT_FPS_TRACKING
        self._at = 0.0
        self.column = None
        self.detections = 0
        self.awake = True

    def set_awake(self, on):
        self.awake = on

    def set_detect_fps(self, fps):
        self._period = 1.0 / max(0.1, fps)

    def set_search_column(self, cx):
        self.column = cx

    def person_bbox(self):
        now = time.monotonic()
        if not self.awake:
            return None, False
        if now - self._at < self._period:
            return self._bbox, False
        self._at = now
        self.detections += 1
        return self._bbox, True

    def person_boxes(self):
        box, fresh = self.person_bbox()
        return ([box] if box else []), fresh


class FakeUwb:
    def __init__(self, theta_deg=0.0, dist=10.0, elev_deg=None):
        self.fix_value = Fix(theta_rad=math.radians(theta_deg), dist_m=dist, age_s=0.0,
                             elev_rad=None if elev_deg is None else math.radians(elev_deg))

    def fix(self):
        return self.fix_value


class FakePtz:
    def __init__(self):
        self.pan_deg = 0.0
        self.tilt_deg = 0.0
        self.zoom_mm = config.ZOOM_MIN_MM
        self.tilt_calls = 0
        self.focus_dist = None
        self.jogs = 0
        self.jogging = False                   # no easing: stops at once

    @property
    def hfov_deg(self):
        half_w = config.ZOOM_MIN_MM * math.tan(math.radians(config.HFOV_WIDE_DEG / 2))
        return math.degrees(2 * math.atan(half_w / max(0.1, self.zoom_mm)))

    def set_pan(self, deg):
        self.pan_deg = max(config.PAN_MIN_DEG, min(config.PAN_MAX_DEG, deg))
        return self.pan_deg

    def set_tilt(self, deg):
        self.tilt_deg = max(config.TILT_MIN_DEG, min(config.TILT_MAX_DEG, deg))
        return self.tilt_deg

    def jog(self, x: float, y: float, dt: float) -> None:
        self.jogs += 1
        self.set_pan(self.pan_deg + x * config.JOG_PAN_MAX_DPS * dt)
        self.set_tilt(self.tilt_deg + y * config.JOG_TILT_MAX_DPS * dt)

    def nudge_tilt(self, d):
        self.tilt_calls += 1
        self.set_tilt(self.tilt_deg + d)

    def set_zoom_mm(self, mm, urgent=False):
        self.zoom_mm = max(config.ZOOM_MIN_MM, min(config.ZOOM_MAX_MM, mm))

    def set_focus(self, dist):
        self.focus_dist = dist


def run(tr, n, pause=0.0):
    for _ in range(n):
        tr.step()
        if pause:
            time.sleep(pause)


def main() -> None:
    print("tracker checks\n")

    # ---- 1. tilt is applied once per detection, not once per control tick --
    cam = FakeCamera((640, 200, 100, 300))     # off centre → tilt should move
    ptz = FakePtz()
    tr = Tracker(FakeUwb(), cam, ptz)
    for _ in range(40):                        # 40 ticks ≈ 2 s at 20 Hz
        tr.step()
        time.sleep(0.005)
    check("tilt applied once per fresh detection",
          ptz.tilt_calls == cam.detections,
          f"{ptz.tilt_calls} nudges for {cam.detections} detections")
    check("a stale box is not integrated repeatedly",
          ptz.tilt_calls < 40, f"{ptz.tilt_calls} of 40 ticks")

    # ---- 2. no detection → no tilt movement -------------------------------
    cam2 = FakeCamera(None)
    ptz2 = FakePtz()
    tr2 = Tracker(FakeUwb(), cam2, ptz2)
    for _ in range(20):
        tr2.step()
    check("no person → tilt untouched", ptz2.tilt_calls == 0)

    # ---- 3. the search-column hint ----------------------------------------
    ptz3 = FakePtz()
    cam3 = FakeCamera(None)
    tr3 = Tracker(FakeUwb(theta_deg=0.0), cam3, ptz3)
    tr3.step()
    centre = config.PREVIEW_SIZE[0] / 2
    check("subject on boresight → strip centred",
          cam3.column is not None and abs(cam3.column - centre) < 2,
          f"{cam3.column} vs {centre}")

    tr4 = Tracker(FakeUwb(theta_deg=12.0), cam3, FakePtz())
    tr4.step()
    check("subject to the right → strip right of centre",
          cam3.column is not None and cam3.column > centre + 50, f"{cam3.column}")

    tr5 = Tracker(FakeUwb(theta_deg=80.0), cam3, FakePtz())
    tr5.step()
    check("subject beyond the field of view → search the whole frame",
          cam3.column is None, f"{cam3.column}")

    # ---- 4. zoom narrows the strip's angular span -------------------------
    p_wide = FakePtz()
    p_tele = FakePtz(); p_tele.zoom_mm = config.ZOOM_MAX_MM
    check("hfov shrinks as the lens zooms in",
          p_tele.hfov_deg < p_wide.hfov_deg - 30,
          f"{p_wide.hfov_deg:.0f} deg wide, {p_tele.hfov_deg:.0f} deg tele")
    check("wide hfov matches the lens spec",
          abs(p_wide.hfov_deg - config.HFOV_WIDE_DEG) < 1.0, f"{p_wide.hfov_deg:.1f}")

    # ---- 5. pan slews rather than snapping --------------------------------
    ptz6 = FakePtz()
    tr6 = Tracker(FakeUwb(theta_deg=60.0), FakeCamera(None), ptz6)
    tr6.step()
    first = ptz6.pan_deg
    check("pan is slew-limited, not snapped",
          0 < first < 20, f"moved {first:.1f} deg in one tick")
    run(tr6, 200, 0.02)                                   # ≈ 4 s: eased, not raced
    check("pan converges on the bearing", abs(ptz6.pan_deg - 60.0) < 3.0,
          f"{ptz6.pan_deg:.1f} deg")

    # ---- 6. soft limits hold ----------------------------------------------
    ptz7 = FakePtz()
    tr7 = Tracker(FakeUwb(theta_deg=179.0), FakeCamera(None), ptz7)
    for _ in range(400):
        tr7.step()
        time.sleep(0.001)
    check("pan stops at the soft limit", ptz7.pan_deg <= config.PAN_MAX_DEG + 1e-6,
          f"{ptz7.pan_deg:.1f} deg")

    # ---- 7. vision-only tilt goes the right way ---------------------------
    pw, ph = config.PREVIEW_SIZE
    low = FakeCamera((pw // 2 - 50, ph // 2 - 50, 100, 300))     # centre well below
    ptz8 = FakePtz()
    run(Tracker(FakeUwb(), low, ptz8), 200, 0.005)     # ~1 s: several detections
    check("no A3, subject low in frame → camera tilts down",
          ptz8.tilt_deg < -0.5, f"{ptz8.tilt_deg:.2f} deg")
    high = FakeCamera((pw // 2 - 50, ph // 2 - 310, 100, 300))   # centre well above
    ptz9 = FakePtz()
    run(Tracker(FakeUwb(), high, ptz9), 200, 0.005)
    check("no A3, subject high in frame → camera tilts up",
          ptz9.tilt_deg > 0.5, f"{ptz9.tilt_deg:.2f} deg")

    # ---- 8. tilt from the third anchor ------------------------------------
    ptz10 = FakePtz()
    tr10 = Tracker(FakeUwb(dist=10.0, elev_deg=30.0), FakeCamera(None), ptz10)
    tr10.step()
    check("A3 tilt is slew-limited, not snapped",
          0 < ptz10.tilt_deg < 15, f"{ptz10.tilt_deg:.1f} deg in one tick")
    run(tr10, 200, 0.02)
    expect = Tracker._aim_tilt(math.radians(30.0), 10.0)
    check("A3 tilt converges on the elevation", abs(ptz10.tilt_deg - expect) < 0.5,
          f"{ptz10.tilt_deg:.1f} vs {expect:.1f}")
    check("A3 tilt drives the axis directly, not through nudges",
          ptz10.tilt_calls == 0, f"{ptz10.tilt_calls} nudges")

    # the lens sits above the anchors, so a tag level with them is below it
    level = Tracker._aim_tilt(0.0, 5.0)
    check("tag level with the anchors → aim slightly down",
          -2.0 < level < -0.5, f"{level:.2f} deg")
    check("lens correction fades with distance",
          abs(Tracker._aim_tilt(0.0, 30.0)) < abs(level))

    # vision trims a bias in the same sense as the fallback
    ptz11 = FakePtz()
    tr11 = Tracker(FakeUwb(dist=10.0, elev_deg=20.0), low, ptz11)
    run(tr11, 60, 0.005)
    check("A3 + subject low in frame → bias pulls tilt down",
          tr11._tilt_bias < 0, f"bias {tr11._tilt_bias:.2f}")
    run(tr11, 400, 0.005)
    check("tilt bias is clamped",
          abs(tr11._tilt_bias) <= config.TILT_CV_BIAS_LIMIT + 1e-9,
          f"{tr11._tilt_bias:.1f}")

    # ---- 9. vision framing: fill target, guard, stale relax ---------------
    class FramedCamera(FakeCamera):
        """A body whose size in the frame follows the zoom, like a real lens."""
        def __init__(self, ptz, dist, body_m=1.8, cx=None, cy=None):
            super().__init__(None)
            self.ptz, self.dist, self.body_m = ptz, dist, body_m
            self.cx, self.cy = cx, cy

        def person_bbox(self):
            body_px = self.body_m * self.ptz.zoom_mm / (config.SENSOR_H_MM * self.dist) * ph
            h = int(body_px / config.PERSON_IN_BOX_H)
            w = int(h * 0.5)
            cx = pw // 2 if self.cx is None else self.cx
            cy = ph // 2 if self.cy is None else self.cy
            self._bbox = (cx - w // 2, cy - h // 2, w, h)
            return super().person_bbox()

    def fill_of(cam):
        body_px = cam.body_m * cam.ptz.zoom_mm / (config.SENSOR_H_MM * cam.dist) * ph
        return body_px / ph

    config.ZOOM_RATE_LIMIT_S = 0.0
    ptz12 = FakePtz()
    cam12 = FramedCamera(ptz12, dist=8.0)
    tr12 = Tracker(FakeUwb(dist=8.0), cam12, ptz12)
    tr12.step()
    first_fill = fill_of(cam12)
    run(tr12, 400, 0.01)          # ~4 s: about a dozen detections
    check("distance alone frames loosely", first_fill < config.ZOOM_FILL_TARGET - 0.1,
          f"{first_fill:.2f}")
    check("vision zooms in until the person fills the target",
          abs(fill_of(cam12) - config.ZOOM_FILL_TARGET) < 0.05,
          f"fill {fill_of(cam12):.2f}, target {config.ZOOM_FILL_TARGET}")

    ptz13 = FakePtz()
    cam13 = FramedCamera(ptz13, dist=4.0, body_m=2.6)    # full reach, close in
    tr13 = Tracker(FakeUwb(dist=4.0), cam13, ptz13)
    run(tr13, 400, 0.01)
    check("a body too big for the frame is zoomed out to the target",
          fill_of(cam13) <= config.ZOOM_FILL_TARGET + 0.05 or ptz13.zoom_mm <= config.ZOOM_MIN_MM + 1e-6,
          f"fill {fill_of(cam13):.2f} at {ptz13.zoom_mm:.2f} mm")

    ptz14 = FakePtz()
    cam14 = FramedCamera(ptz14, dist=8.0, cy=int(ph * 0.12))   # body hard against the top
    tr14 = Tracker(FakeUwb(dist=8.0), cam14, ptz14)
    tr14.step()
    before = tr14._zoom_scale
    run(tr14, 120, 0.01)
    check("a body near the edge backs the zoom off, whatever its size",
          tr14._zoom_scale < before, f"{before:.2f} → {tr14._zoom_scale:.2f}")
    check("zoom scale stays within its limits",
          config.ZOOM_SCALE_MIN - 1e-9 <= tr14._zoom_scale <= config.ZOOM_SCALE_MAX + 1e-9)

    ptz15 = FakePtz()
    cam15 = FramedCamera(ptz15, dist=40.0)                # tiny, far beyond full zoom
    tr15 = Tracker(FakeUwb(dist=40.0), cam15, ptz15)
    run(tr15, 200, 0.01)
    check("at the end of the lens the scale does not wind up",
          ptz15.zoom_mm == config.ZOOM_MAX_MM and tr15._zoom_scale <= config.ZOOM_SCALE_MAX,
          f"{ptz15.zoom_mm:.2f} mm, scale {tr15._zoom_scale:.2f}")

    # vision goes quiet (an overhang): ease back to the looser distance framing
    tr12.camera = FakeCamera(None)
    zoomed = tr12._zoom_scale
    run(tr12, 400, 0.01)
    check("no detections → zoom relaxes toward distance framing",
          1.0 <= tr12._zoom_scale < zoomed - 0.1, f"{zoomed:.2f} → {tr12._zoom_scale:.2f}")
    check("focus follows the ranged distance", ptz12.focus_dist == 8.0,
          f"{ptz12.focus_dist}")

    # ---- 10. recording, and the wearer out of sight: zoom out to find them ----
    ptz16 = FakePtz()
    cam16 = FramedCamera(ptz16, dist=8.0)
    tr16 = Tracker(FakeUwb(theta_deg=10.0, dist=8.0), cam16, ptz16)
    tr16.confirm()                                        # recording
    run(tr16, 400, 0.01)
    tight = ptz16.zoom_mm
    seen = cam16.person_bbox
    cam16.person_bbox = lambda: (None, FakeCamera.person_bbox(cam16)[1])   # out of shot
    run(tr16, 50, 0.01)                                   # ≈ 0.5 s
    check("recording, wearer out of sight under LOST_ZOOM_OUT_S: zoom held",
          abs(ptz16.zoom_mm - tight) < 0.5, f"{tight:.1f} → {ptz16.zoom_mm:.1f} mm")
    run(tr16, int(config.LOST_ZOOM_OUT_S / 0.01), 0.01)   # past LOST_ZOOM_OUT_S
    check("…then straight out to wide, still turned to the tag",
          ptz16.zoom_mm == config.ZOOM_MIN_MM and abs(ptz16.pan_deg - 10.0) < 1.0,
          f"{ptz16.zoom_mm:.1f} mm, pan {ptz16.pan_deg:.1f}")
    tr16.uwb.fix_value = None                             # and the tag drops out too
    run(tr16, 20, 0.01)
    check("…still wide with no tag, searching the whole frame",
          ptz16.zoom_mm == config.ZOOM_MIN_MM and cam16.column is None, f"{cam16.column}")
    tr16.uwb = FakeUwb(theta_deg=10.0, dist=8.0)
    cam16.person_bbox = seen                              # back in the wide shot
    run(tr16, 400, 0.01)
    check("…seen again: the framing closes back in",
          ptz16.zoom_mm > config.ZOOM_MIN_MM + 1.0, f"{ptz16.zoom_mm:.1f} mm")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all tracker checks passed")


if __name__ == "__main__":
    main()
