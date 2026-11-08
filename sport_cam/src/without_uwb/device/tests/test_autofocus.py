"""Contrast autofocus: the continuous sweep and the fine pass find the
sharpest focus, quickly, and stop when told. No camera or I2C bus: a
simulated lens moves at the bench kit's measured speed on a simulated clock,
each frame shows where the lens was AF_FRAME_LAG_S before it is handed over,
and a made-up sharpness curve peaks as narrowly as the real lens's.

    python3 device/tests/test_autofocus.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config
from sportcam.autofocus import AutoFocus, _steps

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


TRAVEL_S = 5.4            # measured: 525 steps of 2100 in 1.35 s
FRAME_S = 1 / 30


class World:
    def __init__(self) -> None:
        self.t = 0.0

    def clock(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s


class Ptz:
    """The focus motor, moving at a steady speed toward where it was sent."""

    def __init__(self, world: World, at: float | None = 0.5) -> None:
        self.w = world
        self.focus_pos = at              # where it was last sent (None: never)
        self._from, self._t0 = (at or 0.0), 0.0
        self.moves: list[float] = []
        self.af_active = False
        self.learned: float | None = None
        self.active_seen = False

    def actual(self, t: float | None = None) -> float:
        t = self.w.t if t is None else t
        target = self.focus_pos if self.focus_pos is not None else 0.0
        run = abs(target - self._from) * TRAVEL_S
        if run == 0 or t - self._t0 >= run:
            return target
        return self._from + (target - self._from) * (t - self._t0) / run

    def set_focus_pos(self, pos: float) -> None:
        self.active_seen |= self.af_active
        self._from, self._t0 = self.actual(), self.w.t
        self.focus_pos = pos
        self.moves.append(pos)

    def lens_busy(self) -> bool:
        target = self.focus_pos if self.focus_pos is not None else 0.0
        return abs(self.actual() - target) > 1e-9

    def wait_lens(self, timeout_s=None) -> None:
        while self.lens_busy():
            self.w.t += 0.01
        self.w.t += config.LENS_SETTLE_S

    def learn_focus(self, pos: float) -> None:
        self.learned = pos


class Camera:
    def __init__(self, world: World, ptz: Ptz) -> None:
        self.w, self.ptz = world, ptz
        self.awake = True

    def _capture(self):
        self.w.t += FRAME_S
        # the frame shows the lens as it was a frame lag ago
        return self.ptz.actual(self.w.t - config.AF_FRAME_LAG_S) if self.awake else None


def peaked_at(best: float, where: dict | None = None):
    """Sharp only within ±2 % of the travel of `best`, flat (and a little
    noisy-looking) elsewhere: the real lens's band is about that narrow."""
    def score(frame, x, y, region):
        if where is not None:
            where["at"] = (x, y, region)
        d = abs(frame - best)
        return 4.0 + (120.0 * (1 - d / 0.02) if d < 0.02 else 0.0) + (frame * 7919 % 1) * 0.3
    return score


def run(best: float, start: float | None = 0.5):
    w = World()
    ptz = Ptz(w, start)
    where: dict = {}
    af = AutoFocus(Camera(w, ptz), ptz, score=peaked_at(best, where),
                   sleep=w.sleep, clock=w.clock)
    got = af.focus(0.2, 0.8)
    return got, ptz, af, w, where


def narrow(score, start: float = 0.5):
    w = World()
    ptz = Ptz(w, start)
    af = AutoFocus(Camera(w, ptz), ptz, score=score, sleep=w.sleep, clock=w.clock)
    return af.focus(0.5, 0.5, narrow=True), ptz, w


def hill(best: float):
    """Near focus: sharpness falls off gently, so a peak isn't many medians."""
    return lambda frame, x, y, region: 100.0 - 300.0 * abs(frame - best)


def main() -> None:
    print("autofocus")
    # after a zoom: the lens nearly right, perhaps on film
    step, _half = config.AF_FINE
    got, ptz, w = narrow(hill(0.53))
    check("narrow: a gentle peak close by is found",
          got is not None and abs(got - 0.53) <= step + 1e-9, f"{got}")
    check("…in a moment", w.t < 4.0, f"{w.t:.1f} s")
    got, ptz, w = narrow(hill(0.75))
    check("narrow: outside the window, it walks to the peak",
          got is not None and abs(got - 0.75) <= step + 1e-9, f"{got}")
    reach = config.AF_REFOCUS_WINDOWS * 2 * config.AF_REFOCUS_HALF + 2 * config.AF_BACKLASH
    check("…without running the whole travel",
          max(ptz.moves) - min(ptz.moves) < reach + 1e-9, f"{ptz.moves}")
    got, ptz, w = narrow(lambda frame, x, y, region: 5.0)
    check("narrow: no peak at all gives up", got is None and ptz.learned is None, f"{got}")
    check("…and puts the lens back", ptz.focus_pos == 0.5, f"{ptz.focus_pos}")
    check("fine steps stay inside the travel", min(_steps(-0.05, 0.05, 0.01)) == 0.0
          and max(_steps(0.95, 1.05, 0.01)) == 1.0)
    step, _half = config.AF_FINE

    for best, start, within_s in ((0.43, 0.5, 6.0), (0.62, 0.5, 6.0),
                                  (0.95, 0.5, 19.0), (0.05, 0.5, 19.0)):
        got, ptz, af, w, where = run(best, start)
        near = abs(start - best) <= config.AF_SWEEP_HALVES[0]
        check(f"finds the sharp band ({best:.2f}, from {start:.2f})",
              got is not None and abs(got - best) <= step + 1e-9, f"{got}")
        check(f"…in {w.t:.1f} s ({'one window' if near else 'then the whole travel'})",
              w.t <= within_s, f"{w.t:.1f} s")
        check("…and leaves the motor there, arriving from below",
              ptz.focus_pos == got and (ptz.moves[-2] < ptz.moves[-1] or got == 0.0),
              f"{ptz.moves[-3:]}")
        check("…keeping it as the focus trim", ptz.learned == got)
        check("…holding everyone else's zoom and focus off while it ran, not after",
              ptz.active_seen and not ptz.af_active and not af.busy)
        check("…scoring round the point asked for",
              where["at"] == (0.2, 0.8, config.AF_REGION), f"{where}")

    got, ptz, *_ = run(0.5, start=None)
    check("never focused before: starts from the middle", got is not None and abs(got - 0.5) <= step)

    # asleep partway: no picture, nothing chosen
    w = World()
    ptz = Ptz(w)
    cam = Camera(w, ptz)
    n = {"scores": 0}

    def sleepy(frame, x, y, region):
        n["scores"] += 1
        if n["scores"] == 10:
            cam.awake = False
        return 4.0
    af = AutoFocus(cam, ptz, score=sleepy, sleep=w.sleep, clock=w.clock)
    check("the camera going to sleep stops it, nothing learned",
          af.focus(0.5, 0.5) is None and not af.busy and not ptz.af_active
          and ptz.learned is None)

    # a newer request (or cancel) stops a running one at its next step
    w = World()
    ptz = Ptz(w)
    holder: dict = {}

    def cancelling(frame, x, y, region):
        holder.setdefault("n", 0)
        holder["n"] += 1
        if holder["n"] == 5:
            holder["af"].cancel()
            holder["moves"] = len(ptz.moves)
        return 4.0
    af = AutoFocus(Camera(w, ptz), ptz, score=cancelling, sleep=w.sleep, clock=w.clock)
    holder["af"] = af
    got = af.focus(0.5, 0.5)
    check("cancelled: the sweep stops, moves nothing more, learns nothing",
          got is None and len(ptz.moves) == holder["moves"] and not af.busy
          and not ptz.af_active and ptz.learned is None, f"{got}")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all autofocus checks passed")


if __name__ == "__main__":
    main()
