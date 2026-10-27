"""The detector thread, with no camera or OpenCV attached.

HOG takes a few hundred milliseconds on a Pi 4. Run inside the 20 Hz control
tick, it froze the servos that long every detection, so it runs on its own
thread. What is checked is what threads get wrong: each result is handed
over exactly once, the caller never waits on a detection, and a result in
flight when the camera sleeps is dropped rather than acted on after waking.

    python3 device/tests/test_camera.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config
from sportcam.camera import Camera

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


class FakeSensor:
    def start(self):
        pass

    def stop(self):
        pass


DETECT_S = 0.25          # about what a detection takes on a Pi 4
BOX = (100, 50, 80, 200)


def slow_camera() -> Camera:
    """A Camera whose detection takes DETECT_S and finds one person."""
    cam = Camera()
    cam._cam, cam._detector = FakeSensor(), object()
    cam.starts = 0

    def detect(strip_cx):
        cam.starts += 1
        time.sleep(DETECT_S)
        return [BOX]

    cam._detect = detect
    cam.set_detect_fps(config.DETECT_FPS_TRACKING)
    cam._start_detector()
    return cam


def main() -> None:
    print("camera detector thread\n")
    cam = slow_camera()
    worst, fresh_n = 0.0, 0
    check_box, took_at = False, None
    t0 = time.monotonic()
    while time.monotonic() - t0 < 2.0:              # a 20 Hz control loop, for 2 s
        t = time.monotonic()
        boxes, fresh = cam.person_boxes()
        worst = max(worst, time.monotonic() - t)
        if fresh:
            fresh_n += 1
            check_box = boxes == [BOX]
            took_at = cam.captured_at
        time.sleep(0.05)
    check("the control loop never waits on a detection", worst < 0.02, f"{worst * 1000:.0f} ms")
    expect = 2.0 * config.DETECT_FPS_TRACKING
    check("detections arrive at DETECT_FPS_TRACKING", expect - 2 <= fresh_n <= expect + 1,
          f"{fresh_n} in 2 s")
    check("each result is handed over once, with its boxes", fresh_n == cam.starts or
          fresh_n == cam.starts - 1, f"{fresh_n} handed, {cam.starts} run")
    check("…and its boxes", check_box)
    check("captured_at is when the frame was taken, before the detection finished",
          took_at is not None and time.monotonic() - took_at >= DETECT_S - 0.01)

    # sleep while a detection is in flight: its result must not survive the wake
    cam = slow_camera()
    while cam.starts == 0:
        time.sleep(0.01)
    cam.set_awake(False)
    time.sleep(DETECT_S + 0.1)                      # the in-flight detection finishes
    cam.set_awake(True)
    boxes, fresh = cam.person_boxes()
    check("a detection in flight at sleep is dropped, not handed over after waking",
          not fresh and boxes == [], f"{boxes} fresh={fresh}")
    time.sleep(config.CAMERA_WARMUP_S + DETECT_S + 0.2)
    boxes, fresh = cam.person_boxes()
    check("…and detection resumes after the warm-up", fresh and boxes == [BOX])

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all camera checks passed")


if __name__ == "__main__":
    main()
