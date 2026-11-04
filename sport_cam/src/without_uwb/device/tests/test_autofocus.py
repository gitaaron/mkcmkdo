"""Contrast autofocus: the sweep finds the sharpest motor position, and a
newer request stops an older one. No camera or I2C bus: the "frame" is the
motor position itself, scored by a made-up sharpness curve.

    python3 device/tests/test_autofocus.py
"""
from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config
from sportcam.autofocus import AutoFocus, _steps

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


class Ptz:
    def __init__(self) -> None:
        self.focus_pos: float | None = None
        self.moves: list[float] = []
        self.waited = 0

    def set_focus_pos(self, pos: float) -> None:
        self.focus_pos = pos
        self.moves.append(pos)

    def wait_lens(self, timeout_s: float = 5.0) -> None:
        self.waited += 1


class Camera:
    """Each capture is the motor position it was taken at; None asleep."""
    def __init__(self, ptz: Ptz) -> None:
        self.ptz = ptz
        self.awake = True

    def _capture(self):
        return self.ptz.focus_pos if self.awake else None


def peaked_at(best: float, where: dict):
    """Sharpest at `best`; notes where in the frame it was asked to score."""
    def score(frame, x, y, region):
        where["at"] = (x, y, region)
        return 1.0 / (1e-3 + abs(frame - best))
    return score


def main() -> None:
    print("autofocus")
    check("the first pass covers the whole travel", _steps(0, 1, 0.05)[0] == 0.0
          and _steps(0, 1, 0.05)[-1] == 1.0)
    check("later ones stay inside it", min(_steps(-0.05, 0.05, 0.01)) == 0.0
          and max(_steps(0.95, 1.05, 0.01)) == 1.0)
    finest = config.AF_FINE_PASSES[-1][0]

    for best in (0.0, 0.37, 0.7134, 1.0):
        ptz = Ptz()
        where: dict = {}
        af = AutoFocus(Camera(ptz), ptz, score=peaked_at(best, where), sleep=lambda s: None)
        got = af.focus(0.2, 0.8)
        check(f"finds the sharpest position ({best})",
              got is not None and abs(got - best) <= finest / 2 + 1e-9,
              f"{got}")
        check("…and leaves the motor there", ptz.focus_pos == got)
        check("…scoring around the point asked for",
              where["at"] == (0.2, 0.8, config.AF_REGION), f"{where}")
        check("…waiting on the motor after every move", ptz.waited == len(ptz.moves) + 1,
              f"{ptz.waited} waits, {len(ptz.moves)} moves")
        ups = [b > a for a, b in zip(ptz.moves, ptz.moves[1:]) if b != a]
        check("…arriving on it from below", ptz.moves[-2] < ptz.moves[-1] or got == 0.0,
              f"{ptz.moves[-3:]}")
        downs = sum(1 for u in ups if not u)
        check("…measuring only on upward moves: down only to start a scan, and before the last",
              downs <= len(config.AF_WINDOWS) + len(config.AF_FINE_PASSES) + 1,
              f"{downs} downward moves")
        check("…and isn't busy afterwards", not af.busy)

    # a slow motor: the search starts where the lens is and stays near it
    ptz = Ptz()
    ptz.focus_pos = 0.8
    af = AutoFocus(Camera(ptz), ptz, score=peaked_at(0.82, {}), sleep=lambda s: None)
    got = af.focus(0.5, 0.5)
    check("starting near the peak, it finds it without crossing the travel",
          got is not None and abs(got - 0.82) <= finest / 2 + 1e-9
          and min(ptz.moves) >= 0.8 - config.AF_WINDOWS[0] - config.AF_BACKLASH - 1e-9,
          f"{got}, lowest {min(ptz.moves):.2f}")

    # asleep partway: no picture, nothing chosen
    ptz = Ptz()
    cam = Camera(ptz)
    calls = {"n": 0}

    def sleepy(frame, x, y, region):
        calls["n"] += 1
        if calls["n"] == 3:
            cam.awake = False
        return 1.0
    af = AutoFocus(cam, ptz, score=sleepy, sleep=lambda s: None)
    check("the camera going to sleep stops it", af.focus(0.5, 0.5) is None and not af.busy)

    # a newer request stops a running sweep at its next step
    ptz = Ptz()
    gate = threading.Event()
    steps = {"n": 0}

    def slow(_s):
        steps["n"] += 1
        if steps["n"] == 2:
            gate.wait(2)
    af = AutoFocus(Camera(ptz), ptz, score=peaked_at(0.5, {}), sleep=slow)
    result: dict = {}
    t = threading.Thread(target=lambda: result.setdefault("old", af.focus(0.5, 0.5)))
    t.start()
    while steps["n"] < 2:
        pass
    af.cancel()
    moved = len(ptz.moves)
    gate.set()
    t.join(2)
    check("cancelled: the old sweep stops and moves nothing more",
          result.get("old") is None and len(ptz.moves) == moved and not af.busy,
          f"{result}, {len(ptz.moves) - moved} moves after")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all autofocus checks passed")


if __name__ == "__main__":
    main()
