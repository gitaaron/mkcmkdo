"""Measure `config.FOCUS_GRID_STEPS` — focus motor position by focal length and distance.

    python -m sportcam.focuscal 5.0        # target taped at 5.0 m from the lens

Stand something with fine, high-contrast detail (a printed test chart, a
newspaper, a printed page) at the given distance, centred in the
frame, and run this once per distance. 2, 5, 10 and 30 m are enough; the
lookup interpolates between them in 1/distance.

At each of five focal lengths it sweeps the focus motor coarsely across its
whole range, then finely around the best position, scoring each frame by the
variance of its Laplacian over the centre of the image — the standard
contrast-autofocus measure, on the frame's grey plane as autofocus does.
Results accumulate in FOCUSCAL_FILE, and after every run the whole grid so
far is printed as a FOCUS_GRID_STEPS literal to paste into config.py: motor
steps, the unit config.py and the logs use.

Run it in the light you will film in. Low light makes the score noisy, and
the sweep then picks a poorer peak.
"""
from __future__ import annotations

import json
import os
import sys
import time

from . import config
from .autofocus import sharpness
from .camera import Camera
from .ptz import LENS_STEPS, Ptz

# in motor steps; a grid saved by an older version (focus_grid.json) was not
FOCUSCAL_FILE = os.path.expanduser("~/.sportcam/focus_grid_steps.json")
SETTLE_S = 0.15
REGION = 1 / 3            # sharpness over the middle third of the frame


def score(cam: Camera) -> float:
    """How sharp the centre of the picture is, in a frame exposed from now."""
    t = time.monotonic()
    got = cam.frame()
    while got is not None and got.at < t:
        got = cam.frame(got)
    return sharpness(got.luma, 0.5, 0.5, REGION)


def sweep(ptz: Ptz, cam: Camera, lo: int, hi: int, step: int) -> tuple[int, float]:
    best = (lo, -1.0)
    for steps in range(lo, hi + 1, step):
        ptz.set_focus_steps(steps)
        ptz.wait_lens()
        time.sleep(SETTLE_S)
        found = score(cam)
        if found > best[1]:
            best = (steps, found)
    return best


def grid_literal(grid: dict) -> str:
    """`grid` as the FOCUS_GRID_STEPS statement config.py wants."""
    rows = []
    for efl in sorted(grid):
        pts = ", ".join(f"({d:g}, {int(steps)})" for d, steps in grid[efl])
        rows.append(f"    {efl:g}: [{pts}],")
    return "\n".join(["FOCUS_GRID_STEPS = {", *rows, "}"])


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

    ptz.start()
    stops = [config.ZOOM_MIN_MM + i * (config.ZOOM_MAX_MM - config.ZOOM_MIN_MM) / 4
             for i in range(5)]
    config.ZOOM_RATE_LIMIT_S = 0.0                 # we are stepping on purpose
    for efl in stops:
        ptz.set_zoom_mm(efl)
        ptz.wait_lens()
        coarse, _ = sweep(ptz, cam, 0, LENS_STEPS, 42)
        steps, found = sweep(ptz, cam, max(0, coarse - 42), min(LENS_STEPS, coarse + 42), 4)
        print(f"  {efl:5.2f} mm @ {dist:5.1f} m → focus step {steps:4d}   (score {found:.0f})")
        row = [p for p in grid.get(round(efl, 2), []) if abs(p[0] - dist) > 1e-6]
        grid[round(efl, 2)] = sorted(row + [[dist, steps]])

    os.makedirs(os.path.dirname(FOCUSCAL_FILE), exist_ok=True)
    with open(FOCUSCAL_FILE, "w") as f:
        json.dump(grid, f, indent=1)

    print(f"\nSaved to {FOCUSCAL_FILE}. Paste into config.py:\n")
    print(grid_literal(grid))
    ptz.park()


if __name__ == "__main__":
    main()
