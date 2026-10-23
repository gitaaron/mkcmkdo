"""Focus lookup and focus/zoom sequencing, with no I2C bus attached.

Focus is a two-dimensional calibration — focal length by subject distance —
and the lookup interpolates in 1/distance. Both are easy to get subtly wrong
and invisible until the footage is soft, so they are checked here.

    python3 device/tests/test_ptz.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config
from sportcam.ptz import OPT_FOCUS, Ptz, focus_raw

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


# A made-up but plausibly shaped grid: nearer subjects need more extension,
# and more so at the long end.
GRID = {
    2.8:  [(2.0, 2600), (10.0, 2120), (30.0, 2040)],
    10.6: [(2.0, 19000), (10.0, 16600), (30.0, 16200)],
}


class RecordingFocuser:
    available = False

    def __init__(self):
        self.writes: list[tuple[str, int]] = []

    def set(self, channel, value, wait=False):
        self.writes.append((channel, int(value)))
        return value


def main() -> None:
    print("ptz checks\n")

    # ---- 1. lookup hits the measured points exactly -----------------------
    for efl, row in GRID.items():
        for d, raw in row:
            got = focus_raw(efl, d, GRID)
            check(f"grid point {efl} mm @ {d} m", got == raw, f"{got} vs {raw}")

    # ---- 2. interpolation is in 1/d, not d --------------------------------
    # 1/d halfway between 1/2 and 1/10 is 0.3, i.e. 3.33 m, not 6 m
    mid = focus_raw(10.6, 1 / 0.3, GRID)
    check("halfway in 1/d lands halfway in raw", abs(mid - (19000 + 16600) / 2) <= 1, f"{mid}")
    check("6 m is nearer the 10 m setting than the 2 m one",
          abs(focus_raw(10.6, 6.0, GRID) - 16600) < abs(focus_raw(10.6, 6.0, GRID) - 19000))

    # ---- 3. between focal lengths, and clamped outside the grid -----------
    between = focus_raw(6.7, 10.0, GRID)
    check("between rows interpolates on focal length",
          abs(between - (2120 + 16600) / 2) <= 1, f"{between}")
    check("past the far end clamps", focus_raw(10.6, 500.0, GRID) == 16200)
    check("inside the near end clamps", focus_raw(10.6, 0.6, GRID) == 19000)
    check("past the tele end clamps", focus_raw(14.0, 10.0, GRID) == 16600)

    # ---- 4. the shipped grid reproduces the old focal-length-only curve ---
    for efl, old in ((2.8, 2000), (10.6, 16000), (6.7, 9000)):
        flat = {focus_raw(efl, d) for d in (1.0, 3.0, 8.0, 40.0)}
        check(f"uncalibrated grid is distance-independent at {efl} mm",
              flat == {old}, f"{flat}")

    # ---- 5. set_focus deadband, and zoom refocusing at the known distance --
    config.FOCUS_GRID = GRID
    config.FOCUS_RATE_LIMIT_S = 0.0
    config.ZOOM_RATE_LIMIT_S = 0.0
    ptz = Ptz()
    ptz.focuser = RecordingFocuser()
    ptz.set_focus(10.0)
    n = len(ptz.focuser.writes)
    check("first focus call moves the motor", n == 1, f"{ptz.focuser.writes}")
    ptz.set_focus(10.5)            # 1/10 − 1/10.5 ≈ 0.005 D, inside the deadband
    check("ranging jitter inside the deadband is ignored", len(ptz.focuser.writes) == n)
    ptz.set_focus(4.0)
    check("a real move refocuses", len(ptz.focuser.writes) == n + 1)

    ptz.set_zoom_mm(10.6)
    focus_after = [v for ch, v in ptz.focuser.writes if ch == OPT_FOCUS][-1]
    check("a zoom move refocuses for the last ranged distance",
          focus_after == focus_raw(10.6, 4.0, GRID), f"{focus_after}")

    # ---- the app's joystick: speed grows with the square of the pull --------
    p = Ptz()
    p.focuser = RecordingFocuser()

    def jogged(x, y, dt=1.0):
        p.park()
        p.jog(x, y, dt)
        return p.pan_deg, p.tilt_deg
    check("full pull right pans right at JOG_PAN_MAX_DPS",
          jogged(1.0, 0.0) == (config.JOG_PAN_MAX_DPS, 0.0), f"{jogged(1.0, 0.0)}")
    check("full pull left pans left", jogged(-1.0, 0.0)[0] == -config.JOG_PAN_MAX_DPS)
    check("full pull up tilts up at JOG_TILT_MAX_DPS",
          jogged(0.0, 1.0) == (0.0, config.JOG_TILT_MAX_DPS), f"{jogged(0.0, 1.0)}")
    check("half a pull turns at a quarter of the speed",
          abs(jogged(0.5, 0.0)[0] - config.JOG_PAN_MAX_DPS / 4) < 1e-9, f"{jogged(0.5, 0.0)}")
    pan, tilt = jogged(1.0, 1.0)
    check("a pull past the rim counts as the rim, in the same direction",
          abs(pan / config.JOG_PAN_MAX_DPS - 0.5 ** 0.5) < 1e-9
          and abs(tilt / config.JOG_TILT_MAX_DPS - 0.5 ** 0.5) < 1e-9, f"{pan:.1f}, {tilt:.1f}")
    check("…and the soft limits still hold", jogged(1.0, 0.0, dt=10.0)[0] == config.PAN_MAX_DEG)
    p.park()
    p.focuser.writes.clear()
    p.jog(0.0, 0.0, 1.0)
    check("knob at the centre: no servo writes", p.focuser.writes == [])

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all ptz checks passed")


if __name__ == "__main__":
    main()
