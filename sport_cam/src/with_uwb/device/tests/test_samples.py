"""The app's Sample button: what the camera saves. No camera: a fake one
hands over two frames and a detection.

    python3 device/tests/test_samples.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from sportcam import config, samples

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


class Camera:
    def __init__(self, awake: bool = True) -> None:
        self.awake = awake
        self._detector = object()
        self.detected_on = None

    def snapshot(self):
        if not self.awake:
            return None
        full = np.zeros((1080, 1920, 3), np.uint8)
        small = np.zeros((720, 1280, 3), np.uint8)
        small[100:300, 200:260] = 255
        return full, small

    def detect_frame(self, rgb):
        self.detected_on = rgb.shape
        return [(200, 100, 60, 200)]


class Tracker:
    labelled_at = None


class Head:
    def __init__(self, awake: bool = True) -> None:
        self.camera = Camera(awake)
        self.tracker = Tracker()
        self.state = "awake" if awake else "sleep"
        self.phase = "person-in-frame"

    def live_boxes(self):
        return [[200, 100, 60, 200, "unsure"]]

    def telemetry(self):
        return {"zoomMm": 2.8, "view": {"rotateDeg": 90, "mirror": True}}


def main() -> None:
    print("samples")
    with tempfile.TemporaryDirectory() as d:
        config.SAMPLE_DIR = d
        head = Head()
        got = samples.save(head)
        name = got["name"]
        check("returns the sample's name and how many are on the card",
              bool(name) and got["count"] == 1, f"{got}")
        check("saves the full frame and the detector's frame",
              os.path.isfile(os.path.join(d, name + ".jpg"))
              and os.path.isfile(os.path.join(d, name + "-detector.jpg")))
        meta = json.load(open(os.path.join(d, name + ".json")))
        check("detection runs on the detector's frame of the same capture",
              head.camera.detected_on == (720, 1280, 3), f"{head.camera.detected_on}")
        check("…and its boxes are saved, in detector-frame pixels",
              meta["detected"] == [[200, 100, 60, 200]] and meta["detectorSize"] == [1280, 720]
              and meta["fullSize"] == [1920, 1080], f"{meta}")
        check("the tracker's labelled boxes and the camera's settings go with it",
              meta["liveBoxes"] == [[200, 100, 60, 200, "unsure"]]
              and meta["telemetry"]["view"]["rotateDeg"] == 90 and meta["state"] == "awake",
              f"{meta}")
        got2 = samples.save(head)
        check("a second sample is counted", got2["count"] == 2 and got2["name"] != name)

        try:
            samples.save(Head(awake=False))
            check("asleep: no sample", False)
        except samples.NoPicture:
            check("asleep: no sample, and it says why", True)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all samples checks passed")


if __name__ == "__main__":
    main()
