"""Find out, from the lens itself, which motor is the zoom and how far it goes.

    ./scripts/pi/lenscheck.sh           # from the Mac; stop `run main` first: it needs the camera
    ./scripts/pi/lenscheck.sh --stops 0,300,600,900,1200,1500,1800,1995

which keeps its output and contact sheet in logs/ on the Mac. On the Pi
alone: ./scripts/pi/run lenscheck [--stops …].

Point the camera at a detailed scene two metres or more away — the lens
can't focus closer than 1.5 m (Arducam's spec) — and leave it still. About
half a minute a stop for each register: four stops, four minutes.

It writes the controller's two lens registers directly, 0x00 and 0x01, in
motor steps (0…2100), not through ptz.py's idea of which is which or
ZOOM_CURVE_STEPS, so what it finds doesn't depend on them. Taking each
register in turn as the zoom, it steps that register through `--stops`
(STOPS by default); at each stop it sweeps the other to find where the
picture is sharpest, and measures the sharp picture's scale against the first
from matched points (a blurred picture can't show its true scale).

The zoom is the register that changes the scale by about the lens's rating,
2.4×. Focus breathing moves it only a little. The contact sheet
(~/lenscheck.jpg) has a row of the sharp pictures per register. For the
register ptz.py takes as the zoom, the log ends with ZOOM_CURVE_STEPS and
FOCUS_GRID_STEPS statements ready to paste into config.py: more stops, a
truer curve between them.
"""
from __future__ import annotations

import os
import sys
import time

from . import config
from .autofocus import sharpness
from .camera import Camera
from .ptz import _IMX477_LENS, _REG_BUSY, LENS_STEPS, OPT_ZOOM, Ptz

REGS = (0x00, 0x01)
TOP = LENS_STEPS
STOPS = (0, 700, 1400, 2100)
COARSE, FINE = 60, 15   # steps of the sweep for focus; a sharp band is under 105 wide
REGION = 0.5            # sharpness over the middle half of the frame
TIMEOUT_S = 15.0


class Raw:
    """The controller's registers, bypassing Ptz's mapping."""

    def __init__(self, ptz: Ptz) -> None:
        self.f = ptz.focuser

    def read(self, reg: int) -> int | None:
        return self.f._read(reg)

    def busy_word(self) -> int | None:
        return self.f._read(_REG_BUSY)

    def move(self, reg: int, value: int) -> tuple[float, bool]:
        """Write and wait until the busy word clears (or TIMEOUT_S, or 0.4 s
        with it never set); how long it took, and whether busy was seen."""
        t0 = time.monotonic()
        self.f._write(reg, value)
        seen = False
        while time.monotonic() - t0 < TIMEOUT_S:
            b = self.busy_word()
            if b:
                seen = True
            elif seen or time.monotonic() - t0 > 0.4:
                break
            time.sleep(0.01)
        if not seen:
            time.sleep(3.0)          # no flag to go by: give it time
        return time.monotonic() - t0, seen


def shot(cam: Camera):
    """A frame exposed from now on: not one already under way."""
    t = time.monotonic()
    got = cam.frame()
    while got is not None and got.at < t:
        got = cam.frame(got)
    return got


def score(cam: Camera) -> float:
    return sharpness(shot(cam).luma, 0.5, 0.5, REGION)


def parse_stops(argv: list[str]) -> tuple[int, ...]:
    """`--stops 0,700,1400` from the command line, or STOPS; in motor steps,
    each held to the travel, in rising order, at least two."""
    if "--stops" not in argv:
        return STOPS
    i = argv.index("--stops")
    if i + 1 >= len(argv):
        raise SystemExit("--stops needs a list: --stops 0,700,1400,2100")
    try:
        stops = sorted({max(0, min(TOP, int(v))) for v in argv[i + 1].split(",") if v.strip()})
    except ValueError:
        raise SystemExit(f"--stops takes whole motor steps, 0 to {TOP}: {argv[i + 1]!r}")
    if len(stops) < 2:
        raise SystemExit("--stops needs at least two different stops")
    return tuple(stops)


def config_lines(found: list[tuple[int, int, float | None]]) -> str:
    """What was measured with the zoom register, as the statements config.py
    wants, in its unit (motor steps).

    `found`: (zoom steps, sharpest focus steps, scale against the first stop
    or None if it couldn't be measured) per stop. Focal lengths come from the
    scales, the longest taken as the lens's rating (ZOOM_MAX_MM); stops with
    no scale are left out. The scene was at one distance, so each row of the
    grid is flat in distance: focuscal measures that.
    """
    scaled = [(z, f, s) for z, f, s in found if s]
    if len(scaled) < 2:
        return "(too few stops with a measured scale to write ZOOM_CURVE_STEPS)"
    longest = max(s for _z, _f, s in scaled)
    rows = sorted((round(config.ZOOM_MAX_MM * s / longest, 2), z, f) for z, f, s in scaled)
    curve = ", ".join(f"({efl:g}, {z})" for efl, z, _f in rows)
    grid = [f"    {efl:g}: [(2.0, {f}), (30.0, {f})]," for efl, _z, f in rows]
    return "\n".join([f"ZOOM_CURVE_STEPS = [{curve}]", "FOCUS_GRID_STEPS = {", *grid, "}"])


def sharpest(raw: Raw, cam: Camera, reg: int) -> tuple[int, float]:
    """Sweep `reg` for the sharpest picture; it ends there. (value, score)."""
    raw.move(reg, 0)
    scores = []
    for value in range(0, TOP + 1, COARSE):
        raw.move(reg, value)
        scores.append((score(cam), value))
    _s, peak = max(scores)
    lo, hi = max(0, peak - COARSE), min(TOP, peak + COARSE)
    raw.move(reg, max(0, lo - 30))
    scores = []
    for value in range(lo, hi + 1, FINE):
        raw.move(reg, value)
        scores.append((score(cam), value))
    best, value = max(scores)
    raw.move(reg, max(0, value - 30))
    raw.move(reg, value)
    return value, best


def scale_between(a, b) -> tuple[float, int] | None:
    """How much bigger things are in `b` than in `a`, and on how many matched
    points; None if the pictures don't match well enough to say."""
    import cv2
    import numpy as np
    orb = cv2.ORB_create(4000)
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None:
        return None
    pairs = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db),
                   key=lambda m: m.distance)[:400]
    if len(pairs) < 12:
        return None
    pa = np.float32([ka[m.queryIdx].pt for m in pairs])
    pb = np.float32([kb[m.trainIdx].pt for m in pairs])
    m, inliers = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=3)
    if m is None or int(inliers.sum()) < 12:
        return None
    return float(np.hypot(m[0, 0], m[1, 0])), int(inliers.sum())


def main() -> None:
    import cv2
    import numpy as np

    stops = parse_stops(sys.argv[1:])
    ptz, cam = Ptz(), Camera()
    if not (ptz.focuser.available and cam._cam):
        print("Needs the Pi: no I2C bus or no camera.")
        return
    raw = Raw(ptz)
    print(f"stops (motor steps): {', '.join(map(str, stops))}")
    print(f"controller firmware 0x{ptz.focuser.firmware or 0:04x}; waking the lens…")
    ptz.start()
    ptz.wait_lens()                      # the home moves, which queue
    print(f"mode register 0x30 = {raw.read(0x30)}")

    rows = []
    ranges = {}
    measured: dict[int, list[tuple[int, int, float | None]]] = {}
    for zoom_reg in REGS:
        focus_reg = REGS[1 - REGS.index(zoom_reg)]
        print(f"\n== 0x{zoom_reg:02x} as the zoom, 0x{focus_reg:02x} as the focus ==")
        first = None
        scales = [1.0]
        tiles = []
        for z in stops:
            raw.move(zoom_reg, z)
            value, best = sharpest(raw, cam, focus_reg)
            got = shot(cam)
            rgb = got.rgb
            grey = np.ascontiguousarray(got.luma)
            found = None if first is None else scale_between(first, grey)
            measured.setdefault(zoom_reg, []).append(
                (z, value, 1.0 if first is None else found[0] if found else None))
            if first is None:
                first = grey
            elif found:
                scales.append(found[0])
            said = "first" if found is None and grey is first else (
                f"scale {found[0]:.3f} on {found[1]} points" if found else "scale unknown")
            print(f"  0x{zoom_reg:02x} = {z:4d}: sharpest at 0x{focus_reg:02x} = {value:4d} "
                  f"(sharpness {best:.0f}), {said}")
            small = cv2.resize(rgb, (384, 216))
            cv2.putText(small, f"0x{zoom_reg:02x}={z} 0x{focus_reg:02x}={value}", (8, 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            tiles.append(small)
        rows.append(np.hstack(tiles))
        ranges[zoom_reg] = max(scales) / min(scales)
        print(f"  range of scale: {ranges[zoom_reg]:.2f}×")

    path = os.path.expanduser("~/lenscheck.jpg")
    cv2.imwrite(path, np.vstack(rows)[:, :, ::-1])
    print(f"\nsaved {path}: top row 0x00 as the zoom, bottom row 0x01")
    print("range of scale: " + ", ".join(f"0x{r:02x} {v:.2f}×" for r, v in ranges.items()))
    zoom_reg = _IMX477_LENS[OPT_ZOOM][0]
    print(f"\nWith 0x{zoom_reg:02x} as the zoom (as ptz.py has it), for config.py, in motor steps:\n")
    print(config_lines(measured.get(zoom_reg, [])))
    ptz.park()


if __name__ == "__main__":
    main()
