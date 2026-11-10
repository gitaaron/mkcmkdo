"""The calibration tools speak config.py's unit: what lenscheck and focuscal
print can be pasted into it as it stands. No camera or I2C bus.

    python3 device/tests/test_lenstools.py
"""
from __future__ import annotations

import ast
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config
from sportcam.focuscal import grid_literal
from sportcam.lenscheck import STOPS, config_lines, parse_stops
from sportcam.ptz import LENS_STEPS, grid_focus_steps, _interp

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def settings(text: str) -> dict:
    """The assignments in `text`, evaluated as config.py would."""
    out: dict = {}
    for node in ast.parse(text).body:
        out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


def main() -> None:
    print("lens calibration tools")
    check("lenscheck: no --stops is the usual four", parse_stops([]) == STOPS)
    check("lenscheck: --stops is taken in rising order, held to the travel, once each",
          parse_stops(["--stops", "1400,0,700,9999,700"]) == (0, 700, 1400, LENS_STEPS))
    for bad in (["--stops"], ["--stops", "0,abc"], ["--stops", "700"]):
        try:
            parse_stops(bad)
            ok = False
        except SystemExit:
            ok = True
        check(f"lenscheck: {' '.join(bad)!r} is refused", ok)

    # the bench kit's own measurement: zoom steps, sharpest focus, scale against the first
    found = [(0, 225, 1.0), (700, 330, 0.78), (1400, 840, None), (1995, 2100, 0.41)]
    text = config_lines(found)
    got = settings(text)
    curve, grid = got["ZOOM_CURVE_STEPS"], got["FOCUS_GRID_STEPS"]
    check("lenscheck prints ZOOM_CURVE_STEPS and FOCUS_GRID_STEPS as config.py statements",
          set(got) == {"ZOOM_CURVE_STEPS", "FOCUS_GRID_STEPS"}, text)
    check("…sorted by focal length, the longest the lens's rating, in motor steps",
          curve == sorted(curve) and curve[-1] == (config.ZOOM_MAX_MM, 0)
          and curve[0] == (round(config.ZOOM_MAX_MM * 0.41, 2), 1995), f"{curve}")
    check("…a stop whose scale couldn't be measured is left out", len(curve) == 3, f"{curve}")
    check("…each focal length with the focus found there, flat in distance",
          grid[config.ZOOM_MAX_MM] == [(2.0, 225), (30.0, 225)]
          and set(grid) == {efl for efl, _z in curve}, f"{grid}")
    check("…and the lookups take them as they are",
          _interp(config.ZOOM_MAX_MM, curve) == 0
          and grid_focus_steps(curve[0][0], 5.0, grid) == 2100)
    check("too few scales: says so, writes no curve",
          "ZOOM_CURVE_STEPS =" not in config_lines([(0, 225, 1.0), (700, 330, None)]))

    text = grid_literal({10.71: [[2.0, 300], [5.0, 240]], 4.38: [[5.0, 2100.0]]})
    grid = settings(text)["FOCUS_GRID_STEPS"]
    check("focuscal prints FOCUS_GRID_STEPS as a config.py statement, in whole steps",
          grid == {4.38: [(5.0, 2100)], 10.71: [(2.0, 300), (5.0, 240)]}, text)
    check("…which the lookup takes", grid_focus_steps(10.71, 2.0, grid) == 300)

    shipped = config.FOCUS_GRID_STEPS
    check("config.py's own calibration is in motor steps, inside the travel",
          all(0 <= steps <= LENS_STEPS for row in shipped.values() for _d, steps in row)
          and all(0 <= steps <= LENS_STEPS for _efl, steps in config.ZOOM_CURVE_STEPS)
          and 0 < config.FOCUS_TRIM_MAX_STEPS < LENS_STEPS)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all lens tool checks passed")


if __name__ == "__main__":
    main()
