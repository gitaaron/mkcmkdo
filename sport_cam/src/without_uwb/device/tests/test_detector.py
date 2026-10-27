"""Person detectors (detector.py), with no camera and no model download.

A fake network stands in for MobileNet-SSD, so what is checked is the code
around it: which detections count, how tiles map back to the frame, that a
person seen in both tiles is reported once, that SSD's tight boxes are
padded to the HOG convention the tracker is tuned for, and the fallback
between detectors. If the real weights are present
(`python3 -m sportcam.getmodel`), they are loaded once as well.

    python3 device/tests/test_detector.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config, detector

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def main() -> None:
    print("person detectors\n")
    if detector.cv2 is None:
        print("  skipped: OpenCV is not installed")
        return
    import numpy as np

    # ---- SSD's tight boxes become HOG-convention padded boxes -------------
    body = (100, 50, 40, 150)
    x, y, w, h = detector._pad(body)
    bw, bh = w * config.PERSON_IN_BOX_W, h * config.PERSON_IN_BOX_H
    check("padded box keeps the body's centre",
          abs(x + w / 2 - 120) <= 1 and abs(y + h / 2 - 125) <= 1, f"{(x, y, w, h)}")
    check("…and the tracker's body fraction recovers the body",
          abs(bw - 40) <= 1 and abs(bh - 150) <= 1, f"{bw:.1f} × {bh:.1f}")

    # ---- tiles: a whole wide frame is split, a strip is not -----------------
    wide = np.zeros((720, 1280, 3), np.uint8)
    tiles = detector._tiles(wide)
    check("a whole wide frame is searched as two overlapping halves",
          len(tiles) == 2 and tiles[0][0] == 0
          and tiles[1][0] + tiles[1][1].shape[1] == 1280 and tiles[1][0] < tiles[0][1].shape[1],
          f"{[(x0, t.shape[1]) for x0, t in tiles]}")
    check("a strip is searched whole", len(detector._tiles(wide[:, :768])) == 1)

    # ---- the SSD wrapper, around a fake network ------------------------------
    class FakeNet:
        """Rows of [_, class, score, x1, y1, x2, y2], normalised to the tile."""
        def __init__(self, rows_for):
            self.rows_for, self.calls = rows_for, 0

        def setInput(self, blob):
            self.blob = blob

        def forward(self):
            rows = self.rows_for(self.calls)
            self.calls += 1
            return np.array(rows, np.float32).reshape(1, 1, -1, 7)

    def in_tile(call):
        # tile 0: a person, a dog, and a person under the confidence bar
        if call == 0:
            return [[0, 1, 0.9, 0.1, 0.2, 0.3, 0.9],
                    [0, 18, 0.95, 0.5, 0.5, 0.6, 0.6],
                    [0, 1, config.SSD_CONFIDENCE - 0.1, 0.6, 0.1, 0.7, 0.5]]
        return []

    found = detector.SsdDetector(FakeNet(in_tile)).detect(wide[:, :768])
    check("only people over SSD_CONFIDENCE count", len(found) == 1, f"{found}")
    x, y, w, h = found[0]
    bw, bh = w * config.PERSON_IN_BOX_W, h * config.PERSON_IN_BOX_H
    check("…scaled from the network's 0–1 to the image's pixels, padded",
          abs(x + w / 2 - 0.2 * 768) <= 2 and abs(bh - 0.7 * 720) <= 2 and abs(bw - 0.2 * 768) <= 2,
          f"{found[0]}")

    # one person standing in the overlap: both halves see them
    tw = tiles[0][1].shape[1]
    px1, px2 = 600, 680                         # inside the overlap (576…704)

    def overlap(call):
        x0 = tiles[call][0]
        return [[0, 1, 0.9 - 0.05 * call, (px1 - x0) / tw, 0.2, (px2 - x0) / tw, 0.9]]
    found = detector.SsdDetector(FakeNet(overlap)).detect(wide)
    check("a person seen in both halves is reported once", len(found) == 1, f"{found}")
    check("…at their place in the whole frame",
          found and abs(found[0][0] + found[0][2] / 2 - (px1 + px2) / 2) <= 2, f"{found}")

    # a person across the seam: whole in the left half, cut off in the right
    def seam(call):
        if call == 0:
            return [[0, 1, 0.9, 500 / tw, 0.2, 650 / tw, 0.9]]
        x0 = tiles[1][0]
        return [[0, 1, 0.8, 0.0, 0.2, (650 - x0) / tw, 0.9]]
    found = detector.SsdDetector(FakeNet(seam)).detect(wide)
    check("a person cut off by the seam in one half is still reported once",
          len(found) == 1, f"{found}")

    # a person wider than the overlap: each half sees a different cut-off piece
    def wide_person(call):
        if call == 0:                           # left half: 400 → its right edge
            return [[0, 1, 0.9, 400 / tw, 0.2, 1.0, 0.9]]
        x0 = tiles[1][0]                        # right half: its left edge → 900
        return [[0, 1, 0.8, 0.0, 0.25, (900 - x0) / tw, 0.9]]
    found = detector.SsdDetector(FakeNet(wide_person)).detect(wide)
    x, y, w, h = found[0] if found else (0, 0, 0, 0)
    bw = w * config.PERSON_IN_BOX_W
    check("a person wider than the overlap, cut in both halves, is joined into one",
          len(found) == 1 and abs(x + w / 2 - 650) <= 3 and abs(bw - 500) <= 3, f"{found}")

    # two people side by side are two people
    def pair(call):
        return [[0, 1, 0.9, 0.05, 0.2, 0.2, 0.9], [0, 1, 0.9, 0.22, 0.2, 0.37, 0.9]] if call == 0 else []
    check("two people side by side stay two", len(detector.SsdDetector(FakeNet(pair)).detect(wide)) == 2)

    # ---- fallback between detectors ------------------------------------------
    real_hog, real_ssd, real_choice = detector._hog, detector._ssd, config.DETECTOR
    sentinel = object()
    try:
        detector._hog = lambda: (None, "no HOG")
        detector._ssd = lambda: (sentinel, None)
        config.DETECTOR = "hog"
        check("the chosen detector missing → the other is used",
              detector.make_detector() == (sentinel, None))
        detector._ssd = lambda: (None, "no model")
        det, why = detector.make_detector()
        check("neither → no detector, with both reasons",
              det is None and "no HOG" in why and "no model" in why, f"{why}")
        detector._hog = lambda: (sentinel, None)
        config.DETECTOR = "ssd"
        check("SSD chosen but missing → HOG", detector.make_detector() == (sentinel, None))
    finally:
        detector._hog, detector._ssd, config.DETECTOR = real_hog, real_ssd, real_choice

    # ---- the real model, when it has been fetched ----------------------------
    if os.path.exists(detector.SSD_WEIGHTS):
        det, why = detector._ssd()
        check("the fetched MobileNet-SSD loads", det is not None, f"{why}")
        if det is not None:
            check("…and runs on a frame", det.detect(wide) == [])
    else:
        print("  (real model not fetched — python3 -m sportcam.getmodel to check it loads)")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all detector checks passed")


if __name__ == "__main__":
    main()
