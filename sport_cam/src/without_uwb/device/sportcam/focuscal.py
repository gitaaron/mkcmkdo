"""Measure `config.FOCUS_GRID` — focus motor position by focal length and distance.

    python -m sportcam.focuscal 5.0        # target taped at 5.0 m from the lens

Stand something with fine, high-contrast detail (a printed test chart, a
newspaper, a printed page) at the given distance, centred in the
frame, and run this once per distance. 2, 5, 10 and 30 m are enough; the
lookup interpolates between them in 1/distance.

At each of five focal lengths it sweeps the focus motor coarsely across its
whole range, then finely around the best position, scoring each frame by the
variance of its Laplacian over the centre of the image — the standard
contrast-autofocus measure. Results accumulate in FOCUSCAL_FILE, and after
every run the whole grid so far is printed as a FOCUS_GRID literal to paste
into config.py.

Run it in the light you will film in. Low light makes the score noisy, and
the sweep then picks a poorer peak.
"""
from __future__ import annotations

import json
import os
import sys
import time

from . import config
from .camera import Camera
from .ptz import OPT_FOCUS, Ptz, _CHANNELS

FOCUSCAL_FILE = os.path.expanduser("~/.sportcam/focus_grid.json")
SETTLE_S = 0.15


def sharpness(cam: Camera) -> float:
    import cv2
    rgb = cam._capture()
    h, w = rgb.shape[:2]
    centre = rgb[h // 3: 2 * h // 3, w // 3: 2 * w // 3]
    gray = cv2.cvtColor(centre, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def sweep(ptz: Ptz, cam: Camera, lo: int, hi: int, step: int) -> tuple[int, float]:
    best = (lo, -1.0)
    for raw in range(lo, hi + 1, step):
        ptz.focuser.set(OPT_FOCUS, raw)
        time.sleep(SETTLE_S)
        score = sharpness(cam)
        if score > best[1]:
            best = (raw, score)
    return best


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    dist = float(sys.argv[1])
    ptz, cam = Ptz(), Camera()
    if not (ptz.focuser.available and cam._cam):
        print("Needs the Pi: no I2C bus or no camera.")
        sys.exit(1)

    try:
        with open(FOCUSCAL_FILE) as f:
            grid = {float(k): v for k, v in json.load(f).items()}
    except FileNotFoundError:
        grid = {}

    _, f_lo, f_hi = _CHANNELS[OPT_FOCUS]
    ptz.start()
    stops = [config.ZOOM_MIN_MM + i * (config.ZOOM_MAX_MM - config.ZOOM_MIN_MM) / 4
             for i in range(5)]
    config.ZOOM_RATE_LIMIT_S = 0.0                 # we are stepping on purpose
    for efl in stops:
        ptz.set_zoom_mm(efl)
        time.sleep(2.0)
        coarse, _ = sweep(ptz, cam, f_lo, f_hi, 400)
        raw, score = sweep(ptz, cam, max(f_lo, coarse - 400), min(f_hi, coarse + 400), 40)
        print(f"  {efl:5.2f} mm @ {dist:5.1f} m → focus {raw:5d}   (score {score:.0f})")
        row = [p for p in grid.get(round(efl, 2), []) if abs(p[0] - dist) > 1e-6]
        grid[round(efl, 2)] = sorted(row + [[dist, raw]])

    os.makedirs(os.path.dirname(FOCUSCAL_FILE), exist_ok=True)
    with open(FOCUSCAL_FILE, "w") as f:
        json.dump(grid, f, indent=1)

    print(f"\nSaved to {FOCUSCAL_FILE}. Paste into config.py:\n")
    print("FOCUS_GRID = {")
    for efl in sorted(grid):
        pts = ", ".join(f"({d:g}, {r})" for d, r in grid[efl])
        print(f"    {efl:g}: [{pts}],")
    print("}")
    ptz.park()


if __name__ == "__main__":
    main()
