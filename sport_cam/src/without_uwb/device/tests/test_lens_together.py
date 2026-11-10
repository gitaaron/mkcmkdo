"""The real lens code together: Ptz, its lens queue, AutoFocus and Refocus
against a simulated controller on the real clock. The other tests take each
alone with a stand-in for the rest; this is the seams between them — who has
the lens, when it has really stopped, and a sweep's timing.

The controller here runs two lens motors at a steady speed and sets its busy
flag while either moves, as the bench kit's does (only faster).

    python3 device/tests/test_lens_together.py
"""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config, ptz as ptz_mod
from sportcam.autofocus import AutoFocus, Refocus
from sportcam.ptz import LensMove, Ptz

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


STEPS_PER_S = 2100.0      # the whole travel in a second: five times the real lens
FOCUS, ZOOM, BUSY = 0x00, 0x01, 0x04
BEST = 900                # where the picture is sharp, in focus motor steps


class Controller:
    """The I2C bus with the PTZ controller on it (firmware 0x0104, mode 1)."""

    def __init__(self) -> None:
        self.regs = {0x40: 0x0104, 0x30: 1}
        self.at = {FOCUS: 0.0, ZOOM: 0.0}
        self.goal = dict(self.at)
        self._t = time.monotonic()
        self._lock = threading.Lock()
        self.cut_short = 0            # lens writes that landed while a motor ran

    def _run(self) -> None:
        now = time.monotonic()
        step = STEPS_PER_S * (now - self._t)
        self._t = now
        for reg, goal in self.goal.items():
            left = goal - self.at[reg]
            self.at[reg] = goal if abs(left) <= step else self.at[reg] + (step if left > 0 else -step)

    def moving(self) -> bool:
        return any(self.at[r] != self.goal[r] for r in self.at)

    def read_i2c_block_data(self, _addr, reg, _n):
        with self._lock:
            self._run()
            v = int(self.moving()) if reg == BUSY else self.regs.get(reg, 0)
        return [(v >> 8) & 0xFF, v & 0xFF]

    def write_i2c_block_data(self, _addr, reg, data):
        with self._lock:
            self._run()
            value = (data[0] << 8) | data[1]
            if reg in self.goal:
                self.cut_short += self.moving()
                self.goal[reg] = value
            else:
                self.regs[reg] = value

    def focus(self) -> float:
        with self._lock:
            self._run()
            return self.at[FOCUS]


class Shot:
    def __init__(self, luma: float, at: float) -> None:
        self.luma, self.at = luma, at


class Camera:
    """60 frames a second, each showing where the focus motor was when exposed."""

    def __init__(self, bus: Controller) -> None:
        self.bus = bus

    def frame(self, newer_than=None):
        time.sleep(1 / 60)
        return Shot(self.bus.focus(), time.monotonic())


def sharp_at_best(luma, x, y, region) -> float:
    d = abs(luma - BEST)
    return 4.0 + (120.0 * (1 - d / 42) if d < 42 else 0.0)


def main() -> None:
    print("the lens code together")
    bus = Controller()
    saved, ptz_mod.SMBus = ptz_mod.SMBus, lambda _n: bus
    config.SERVO_DRIVER = "arducam"
    config.ZOOM_RATE_LIMIT_S = 0.0
    try:
        ptz = Ptz()
    finally:
        ptz_mod.SMBus = saved
    af = AutoFocus(Camera(bus), ptz, score=sharp_at_best)

    ptz.set_focus_steps(1000)
    check("a move asked for: the lens is moving, with no time passed", ptz.lens_moving)
    ptz.wait_lens()
    check("wait_lens returns once the motor has really stopped",
          bus.focus() == 1000 and not bus.moving() and not ptz.lens_moving)

    done: list = []
    af.start(0.5, 0.5, on_done=done.append)
    check("autofocus started: the lens is its own at once, and a zoom is turned away",
          af.busy and ptz.lens_moving and ptz.set_zoom_mm(8.0) is LensMove.HELD
          and ptz.zoom_mm == config.ZOOM_MIN_MM)
    t0 = time.monotonic()
    while not done and time.monotonic() - t0 < 20:
        time.sleep(0.02)
    out = done[0] if done else None
    check("it finds the sharp position through the real lens queue",
          out is not None and out.focused and abs(out.steps - BEST) <= config.AF_FINE_STEPS[0],
          f"{out}")
    check("…leaves the motor there, and gives the lens back",
          out is not None and bus.focus() == out.steps and not af.busy and not ptz.lens_moving)
    check("…with no lens write landing on a moving motor", bus.cut_short == 0,
          f"{bus.cut_short}")

    # a zoom, then the refocus: only once zoom and its refocus have both stopped
    refocus = Refocus(ptz, af)
    started: list[float] = []
    real_start = af.start

    def start(*a, **k):
        started.append(time.monotonic())
        started.append(bus.moving())
        real_start(*a, **k)
    af.start = start
    check("a zoom is taken now", ptz.set_zoom_mm(8.0) is LensMove.MOVED)
    t0 = time.monotonic()
    moving_ticks = 0
    while not started and time.monotonic() - t0 < 10:
        moving_ticks += ptz.lens_moving
        refocus.tick(0.5, 0.5, narrow=True)
        time.sleep(0.02)
    check("Refocus waits through the zoom and the refocus that follows it…",
          moving_ticks > 5 and bool(started), f"{moving_ticks} ticks moving")
    check("…and starts autofocus with both motors at rest, where they were sent",
          len(started) == 2 and started[1] is False and bus.at == bus.goal, f"{started}")
    check("…the zoom and its refocus ran one after the other, neither cut short",
          bus.cut_short == 0, f"{bus.cut_short}")
    t0 = time.monotonic()
    while af.busy and time.monotonic() - t0 < 20:
        time.sleep(0.02)
    check("that autofocus ends too, the lens free again", not af.busy and not ptz.lens_moving)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all lens-together checks passed")


if __name__ == "__main__":
    main()
