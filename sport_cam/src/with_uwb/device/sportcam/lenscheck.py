"""Find out, from the lens itself, which motor is the zoom and how far it goes.

    ./scripts/pi/lenscheck.sh           # from the Mac; stop `run main` first: it needs the camera

which keeps its output and contact sheet in logs/ on the Mac. On the Pi
alone: ./scripts/pi/run lenscheck.

Point the camera at a detailed scene two metres or more away — the lens
can't focus closer than 1.5 m (Arducam's spec) — and leave it still. About
four minutes.

It writes the controller's two lens registers directly, 0x00 and 0x01 at
0…2100, ignoring LENS_SWAP_ZOOM_FOCUS and ZOOM_CURVE, so what it finds
doesn't depend on them. Taking each register in turn as the zoom, it steps
that register across its travel; at each stop it sweeps the other to find
where the picture is sharpest, and measures the sharp picture's scale against
the first from matched points (a blurred picture can't show its true scale).

The zoom is the register that changes the scale by about the lens's rating,
2.4×. Focus breathing moves it only a little. The contact sheet (~/lenscheck.jpg)
has a row of the sharp pictures per register, and the log gives the zoom →
focus pairs FOCUS_GRID wants.
"""
from __future__ import annotations

import os
import time

from .autofocus import sharpness
from .camera import Camera
from .ptz import _REG_BUSY, CHIP_ADDR, Ptz

REGS = (0x00, 0x01)
TOP = 2100
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
        try:
            with self.f._lock:
                hi, lo = self.f._bus.read_i2c_block_data(CHIP_ADDR, _REG_BUSY, 2)
        except OSError:
            return None
        return (hi << 8) | lo

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

    def block(self, reg: int, n: int) -> list[int]:
        try:
            with self.f._lock:
                data = self.f._bus.read_i2c_block_data(CHIP_ADDR, reg, n)
        except OSError:
            return []
        return [(data[i] << 8) | data[i + 1] for i in range(0, len(data) - 1, 2)]


def score(cam: Camera) -> float:
    cam._capture()                       # the frame already under way
    return sharpness(cam._capture(), 0.5, 0.5, REGION)


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

    ptz, cam = Ptz(), Camera()
    if not (ptz.focuser.available and cam._cam):
        print("Needs the Pi: no I2C bus or no camera.")
        return
    raw = Raw(ptz)
    print(f"controller firmware 0x{ptz.focuser.firmware or 0:04x}; waking the lens…")
    ptz.start()
    print(f"mode register 0x30 = {raw.read(0x30)}")

    rows = []
    ranges = {}
    for zoom_reg in REGS:
        focus_reg = REGS[1 - REGS.index(zoom_reg)]
        print(f"\n== 0x{zoom_reg:02x} as the zoom, 0x{focus_reg:02x} as the focus ==")
        first = None
        scales = [1.0]
        tiles = []
        for z in STOPS:
            raw.move(zoom_reg, z)
            value, best = sharpest(raw, cam, focus_reg)
            cam._capture()
            rgb = cam._capture()
            grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            found = None if first is None else scale_between(first, grey)
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
    ptz.park()


if __name__ == "__main__":
    main()
