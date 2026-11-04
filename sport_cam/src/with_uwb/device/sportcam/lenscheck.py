"""Find out, from the lens itself, which register is zoom and which is focus,
which way each runs, and how the controller reports its moves.

    ./scripts/pi/lenscheck.sh           # from the Mac; stop `run main` first: it needs the camera

which keeps its output and contact sheet in logs/ on the Mac. On the Pi
alone: ./scripts/pi/run lenscheck.

Point the camera at a scene with detail at two metres or more — the lens
can't focus closer than 1.5 m (Arducam's spec) — and leave it still. About
three minutes.

It writes the controller's two lens registers directly — 0x00 and 0x01, at
0…2100 as Arducam's Focuser.py does — ignoring LENS_SWAP_ZOOM_FOCUS and
ZOOM_CURVE, so what it shows doesn't depend on them. For each register in
turn, with the other held mid-way:

  * a row of the contact sheet (~/lenscheck.jpg): the picture at five values,
    each taken once the controller says the motor has stopped, labelled with
    the value, how long the move took and the sharpness. The zoom register
    changes the framing; the focus register the sharpness, the framing barely
  * a slow sweep, up and back down in steps of 105 (5 %), sharpness at each:
    the focus register shows a peak; its position going up and coming down
    says how much backlash there is

and before that, what the controller says about itself: firmware, mode, and
its built-in zoom → focus tracking map (registers 0x50 / 0x5b).
"""
from __future__ import annotations

import os
import time

from .autofocus import sharpness
from .camera import Camera
from .ptz import _REG_BUSY, CHIP_ADDR, Ptz

REGS = (0x00, 0x01)
TOP = 2100
MID = 1050
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
    print(f"mode register 0x30 = {raw.read(0x30)}   (1: 'Adjust', the firmware moves focus with zoom)")
    print(f"busy word now = {raw.busy_word()}")
    print(f"tracking map 0x50: {raw.block(0x50, 22)}")
    print(f"tracking map 0x5b: {raw.block(0x5b, 22)}")
    print(f"registers now: 0x00 = {raw.read(0x00)}, 0x01 = {raw.read(0x01)}")

    rows = []
    for reg in REGS:
        other = REGS[1 - REGS.index(reg)]
        print(f"\n== register 0x{reg:02x} alone (0x{other:02x} held at {MID}) ==")
        raw.move(other, MID)
        raw.move(reg, 0)
        tiles = []
        for value in (0, 525, 1050, 1575, 2100):
            dt, seen = raw.move(reg, value)
            s = score(cam)
            back = raw.read(reg)
            print(f"  0x{reg:02x} = {value:4d}: move {dt:5.2f} s, busy {'seen' if seen else 'never set'}, "
                  f"reads back {back}, sharpness {s:6.1f}")
            small = cv2.resize(cam._capture(), (384, 216))
            cv2.putText(small, f"0x{reg:02x}={value} {dt:.1f}s s={s:.0f}", (8, 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            tiles.append(small)
        rows.append(np.hstack(tiles))

        print(f"  slow sweep of 0x{reg:02x}, steps of 105:")
        raw.move(reg, 0)
        up = []
        for value in range(0, TOP + 1, 105):
            raw.move(reg, value)
            up.append((value, score(cam)))
        down = []
        for value in range(TOP, -1, -105):
            raw.move(reg, value)
            down.append((value, score(cam)))
        print("    up:   " + " ".join(f"{v}:{s:.0f}" for v, s in up))
        print("    down: " + " ".join(f"{v}:{s:.0f}" for v, s in reversed(down)))
        bu = max(up, key=lambda p: p[1])
        bd = max(down, key=lambda p: p[1])
        print(f"    peak going up at {bu[0]} ({bu[1]:.0f}), coming down at {bd[0]} ({bd[1]:.0f})")
        raw.move(reg, MID)

    path = os.path.expanduser("~/lenscheck.jpg")
    cv2.imwrite(path, np.vstack(rows)[:, :, ::-1])
    print(f"\nsaved {path}: top row register 0x00, bottom row 0x01")
    ptz.park()


if __name__ == "__main__":
    main()
