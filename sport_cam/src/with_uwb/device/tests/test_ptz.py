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
from sportcam import ptz as ptz_mod
from sportcam.ptz import (OPT_FOCUS, OPT_MOTOR_X, OPT_MOTOR_Y, OPT_ZOOM, ArducamServos,
                          Focuser, PigpioServos, Ptz, focus_raw)

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


class FakeBus:
    """The PTZ controller's registers: busy never set, mode as given."""

    def __init__(self, firmware: int, mode: int = 0):
        self.regs = {0x40: firmware, 0x30: mode, 0x04: 0}
        self.writes: list[tuple[int, int]] = []

    def read_i2c_block_data(self, addr, reg, n):
        v = self.regs.get(reg, 0)
        return [(v >> 8) & 0xFF, v & 0xFF]

    def write_i2c_block_data(self, addr, reg, data):
        self.regs[reg] = (data[0] << 8) | data[1]
        self.writes.append((reg, self.regs[reg]))


def focuser_on(bus: FakeBus) -> Focuser:
    saved, ptz_mod.SMBus = ptz_mod.SMBus, lambda _n: bus
    try:
        return Focuser()
    finally:
        ptz_mod.SMBus = saved


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

    # ---- zooming out for a lost person skips the rate limit ----------------
    config.ZOOM_RATE_LIMIT_S = 2.0                 # section 4 turned it off
    p = Ptz()
    p.focuser = RecordingFocuser()
    p.set_zoom_mm(8.0)
    p.set_zoom_mm(5.0)
    check("a second zoom inside ZOOM_RATE_LIMIT_S is dropped", p.zoom_mm == 8.0, f"{p.zoom_mm}")
    p.set_zoom_mm(config.ZOOM_MIN_MM, urgent=True)
    check("…but an urgent one goes at once", p.zoom_mm == config.ZOOM_MIN_MM, f"{p.zoom_mm}")

    # ---- the app's joystick: speed grows with the square of the pull --------
    p = Ptz()
    p.focuser = RecordingFocuser()
    p.servos = ArducamServos(p.focuser)       # so servo writes are recorded

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

    # ---- servo drivers: pigpio hardware PWM, or the controller's registers --
    class FakePi:
        def __init__(self):
            self.pwm: dict[int, tuple[int, int]] = {}

        def hardware_PWM(self, gpio, hz, duty):
            self.pwm[gpio] = (hz, duty)

    def us(pi, gpio):
        hz, duty = pi.pwm[gpio]
        return duty / hz                          # millionths of the period → µs

    p = Ptz()
    pi = FakePi()
    p.servos = PigpioServos(pi)
    p.set_pan(0.0)
    p.set_tilt(0.0)
    centre = config.SERVO_US_AT_0 + config.PAN_CENTER_RAW / 180 * (
        config.SERVO_US_AT_180 - config.SERVO_US_AT_0)
    check("pigpio: centre is the centre pulse, at SERVO_PWM_HZ, on PAN_GPIO",
          pi.pwm[config.PAN_GPIO][0] == config.SERVO_PWM_HZ
          and abs(us(pi, config.PAN_GPIO) - centre) < 0.05, f"{pi.pwm}")
    check("…and tilt on TILT_GPIO", config.TILT_GPIO in pi.pwm)
    per_deg = (config.SERVO_US_AT_180 - config.SERVO_US_AT_0) / 180
    p.set_pan(0.1)
    check("pigpio: a tenth of a degree moves the pulse a tenth of a degree's width",
          abs(us(pi, config.PAN_GPIO) - (centre + 0.1 * per_deg * config.PAN_SIGN)) < 0.05,
          f"{us(pi, config.PAN_GPIO):.2f} µs")
    p.set_tilt(30.0)
    check("pigpio: tilt follows TILT_SIGN",
          abs(us(pi, config.TILT_GPIO) - (centre + 30 * per_deg * config.TILT_SIGN)) < 0.05)
    p.set_pan(500.0)
    check("pigpio: the soft limit still holds",
          abs(us(pi, config.PAN_GPIO)
              - (centre + config.PAN_MAX_DEG * per_deg * config.PAN_SIGN)) < 0.05)
    saved, ptz_mod.pigpio = ptz_mod.pigpio, None
    idle = PigpioServos()
    idle.write(OPT_MOTOR_X, 90.0)
    check("pigpio: no pigpio installed (dev machine) is a no-op, not a crash", not idle.available)
    ptz_mod.pigpio = saved

    p = Ptz()
    p.servos = ArducamServos(RecordingFocuser())
    p.set_pan(10.4)
    p.set_tilt(-5.6)
    writes = dict(p.servos.focuser.writes)
    check("arducam: pan and tilt go to the registers in whole degrees",
          writes.get(OPT_MOTOR_X) == round(config.PAN_CENTER_RAW + 10.4 * config.PAN_SIGN)
          and writes.get(OPT_MOTOR_Y) == round(config.TILT_CENTER_RAW - 5.6 * config.TILT_SIGN),
          f"{writes}")

    # ---- the IMX477 kit's controller (firmware 0x0104) ---------------------
    bus = FakeBus(0x0104)
    f = focuser_on(bus)
    f.set(OPT_ZOOM, 20000)
    f.set(OPT_FOCUS, 10000)
    f.set(OPT_MOTOR_X, 120)
    check("imx477: zoom on 0x01, focus on 0x00, rescaled to 0-2100; pan unchanged",
          bus.writes == [(0x01, 2100), (0x00, 1050), (0x05, 120)], f"{bus.writes}")
    check("imx477: reads come back on the older scale",
          f.get(OPT_ZOOM) == 20000 and f.get(OPT_FOCUS) == 10000)
    bus.writes.clear()
    f.wake()
    check("imx477: wake resets the lens, then leaves mode 0",
          bus.writes == [(0x0B, 0), (0x0A, 0), (0x30, 1)], f"{bus.writes}")
    bus.writes.clear()
    f.wake()
    check("imx477: already in mode 1, wake leaves the mode alone",
          (0x30, 1) not in bus.writes, f"{bus.writes}")

    bus = FakeBus(0x0000)
    f = focuser_on(bus)
    f.set(OPT_ZOOM, 20000)
    f.wake()
    check("older controller: zoom on 0x00 as is, and no wake writes",
          bus.writes == [(0x00, 20000)], f"{bus.writes}")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all ptz checks passed")


if __name__ == "__main__":
    main()
