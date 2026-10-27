"""Compare the two person detectors on the live picture, on the Pi.

    sudo systemctl stop sportcam-head
    python3 -m sportcam.detectbench [seconds]      # default 60

Have someone climb (or stand, crouch, reach, turn their back) in front of the
camera while it runs. Each frame goes through HOG and MobileNet-SSD, both on
the whole frame (as while searching) and on the strip a locked-on session
searches. It prints, per detector: time per frame, the frame rate that
allows, and how many frames found at least one person. The detector that
finds the climber in more frames, at a rate of 3 a second or better, is the
one for `DETECTOR` (docs 15). In this build the strip is centred, not on the tag.
"""
from __future__ import annotations

import sys
import time

from . import config, detector
from .camera import Camera


def main() -> None:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    dets = []
    for make in (detector._hog, detector._ssd):
        det, why = make()
        if det is None:
            print(f"skipped: {why}")
        else:
            dets.append(det)
    if not dets:
        raise SystemExit("no detector to compare")
    cam = Camera()
    cam.set_detect_fps(0.1)                   # its own thread stays out of the way
    time.sleep(config.CAMERA_WARMUP_S)
    pw = config.PREVIEW_SIZE[0]
    half = int(pw * (config.DETECT_STRIP_FRACTION or 1.0) / 2)
    stats = {(d.name, area): [0.0, 0, 0] for d in dets for area in ("whole", "strip")}
    end = time.monotonic() + seconds
    print(f"running {seconds:.0f} s — move about in front of the camera")
    while time.monotonic() < end:
        frame = cam._capture()
        if frame is None:
            raise SystemExit("no picture — is the camera connected?")
        strip = frame[:, pw // 2 - half:pw // 2 + half]
        for d in dets:
            for area, img in (("whole", frame), ("strip", strip)):
                t = time.perf_counter()
                found = d.detect(img)
                s = stats[(d.name, area)]
                s[0] += time.perf_counter() - t
                s[1] += 1
                s[2] += bool(found)
    print(f"\n{'detector':10} {'area':6} {'ms/frame':>9} {'max fps':>8} {'frames with a person':>21}")
    for (name, area), (t, n, hit) in stats.items():
        print(f"{name:10} {area:6} {1000 * t / n:9.0f} {n / t:8.1f} {f'{hit}/{n} ({100 * hit / n:.0f} %)':>21}")


if __name__ == "__main__":
    main()
