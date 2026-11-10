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
from sportcam.ptz import (LENS_STEPS, OPT_FOCUS, OPT_MOTOR_X, OPT_MOTOR_Y, OPT_ZOOM,
                          ArducamServos, Focuser, LensMove, PigpioServos, Ptz,
                          grid_focus_steps)

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


# A made-up but plausibly shaped grid: nearer subjects need more extension,
# and more so at the long end.
# In lens motor steps, 0…LENS_STEPS, as everything about the lens is.
GRID = {
    2.8:  [(2.0, 260), (10.0, 212), (30.0, 204)],
    10.6: [(2.0, 1900), (10.0, 1660), (30.0, 1620)],
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
    lens_idle = True
    lens_started_at = lens_stopped_at = 0.0

    def __init__(self):
        self.writes: list[tuple[str, int]] = []
        self.expected: list[float] = []

    def set(self, channel, value, expect_s=0.0):
        self.writes.append((channel, int(value)))
        self.expected.append(expect_s)
        return value


def main() -> None:
    print("ptz checks\n")

    # ---- 1. lookup hits the measured points exactly -----------------------
    for efl, row in GRID.items():
        for d, raw in row:
            got = grid_focus_steps(efl, d, GRID)
            check(f"grid point {efl} mm @ {d} m", got == raw, f"{got} vs {raw}")

    # ---- 2. interpolation is in 1/d, not d --------------------------------
    # 1/d halfway between 1/2 and 1/10 is 0.3, i.e. 3.33 m, not 6 m
    mid = grid_focus_steps(10.6, 1 / 0.3, GRID)
    check("halfway in 1/d lands halfway in raw", abs(mid - (1900 + 1660) / 2) <= 1, f"{mid}")
    check("6 m is nearer the 10 m setting than the 2 m one",
          abs(grid_focus_steps(10.6, 6.0, GRID) - 1660) < abs(grid_focus_steps(10.6, 6.0, GRID) - 1900))

    # ---- 3. between focal lengths, and clamped outside the grid -----------
    between = grid_focus_steps(6.7, 10.0, GRID)
    check("between rows interpolates on focal length",
          abs(between - (212 + 1660) / 2) <= 1, f"{between}")
    check("past the far end clamps", grid_focus_steps(10.6, 500.0, GRID) == 1620)
    check("inside the near end clamps", grid_focus_steps(10.6, 0.6, GRID) == 1900)
    check("past the tele end clamps", grid_focus_steps(14.0, 10.0, GRID) == 1660)

    # ---- 4. the shipped (uncalibrated) grid depends on focal length only ---
    for efl, old in ((4.38, 2100), (6.27, 840), (10.71, 225)):
        flat = {grid_focus_steps(efl, d) for d in (1.0, 3.0, 8.0, 40.0)}
        check(f"uncalibrated grid is distance-independent at {efl} mm",
              flat == {old}, f"{flat}")

    # ---- 5. set_focus deadband, and zoom refocusing at the known distance --
    config.FOCUS_GRID_STEPS = GRID
    config.FOCUS_RATE_LIMIT_S = 0.0
    config.ZOOM_RATE_LIMIT_S = 0.0
    ptz = Ptz()
    ptz.focuser = RecordingFocuser()
    said = ptz.set_focus(10.0)
    n = len(ptz.focuser.writes)
    check("first focus call moves the motor, and says so",
          n == 1 and said is LensMove.MOVED and bool(said), f"{ptz.focuser.writes} {said}")
    said = ptz.set_focus(10.5)     # 1/10 − 1/10.5 ≈ 0.005 D, inside the deadband
    check("ranging jitter inside the deadband is ignored, and says why",
          len(ptz.focuser.writes) == n and said is LensMove.SMALL and not said, f"{said}")
    check("a real move refocuses", bool(ptz.set_focus(4.0)) and len(ptz.focuser.writes) == n + 1)

    ptz.set_zoom_mm(10.6)
    focus_after = [v for ch, v in ptz.focuser.writes if ch == OPT_FOCUS][-1]
    check("a zoom move refocuses for the last ranged distance",
          focus_after == grid_focus_steps(10.6, 4.0, GRID), f"{focus_after}")

    # ---- the app's focus slider skips the rate limit, not the deadband -------
    config.FOCUS_RATE_LIMIT_S = 2.0
    f = Ptz()
    f.focuser = RecordingFocuser()
    f.set_focus(10.0)
    said = f.set_focus(3.0)
    check("a second focus inside FOCUS_RATE_LIMIT_S is dropped, and says so",
          f.focus_m == 10.0 and said is LensMove.PACED, f"{f.focus_m} {said}")
    f.set_focus(3.0, urgent=True)
    check("…but the app's goes at once", f.focus_m == 3.0, f"{f.focus_m}")
    n = len(f.focuser.writes)
    f.set_focus(3.05, urgent=True)
    check("…and still inside the deadband does nothing", len(f.focuser.writes) == n)
    config.FOCUS_RATE_LIMIT_S = 0.0

    # ---- waking: homing leaves the lens blurred, refocus puts it back --------
    r = Ptz()
    r.focuser = RecordingFocuser()
    r.set_focus(config.AWAKE_FOCUS_M)
    r.home()
    n = len(r.focuser.writes)
    r.set_focus(config.AWAKE_FOCUS_M)
    check("homing forgets the distance focused for: the same request moves the motor again",
          len(r.focuser.writes) == n + 1, f"{r.focuser.writes[n:]}")
    r.home()
    n = len(r.focuser.writes)
    r.refocus()
    check("refocus() always moves it, deadband or not",
          len(r.focuser.writes) == n + 1 and r.focuser.writes[-1][0] == OPT_FOCUS)

    # ---- what autofocus learns carries over to other zooms -------------------
    config.ZOOM_RATE_LIMIT_S = 0.0
    a = Ptz()
    a.focuser = RecordingFocuser()
    a.set_zoom_mm(5.0, urgent=True)
    a.refocus(5.0)
    a.learn_focus(a.focus_steps + 20)       # autofocus: sharp 20 steps from the grid's
    a.set_zoom_mm(10.0, urgent=True)
    check("after autofocus, a zoom move refocuses at the grid's position plus its trim, "
          "grown with the square of the focal length: twice as long, four times the trim",
          a.focus_steps == grid_focus_steps(10.0, 5.0) + 80,
          f"{a.focus_steps} vs {grid_focus_steps(10.0, 5.0)} + 80")
    a.set_zoom_mm(5.0, urgent=True)
    a.learn_focus(a.focus_steps - 20 + 100)     # 100 steps out at 5 mm: 400 at 10 mm…
    a.set_zoom_mm(10.0, urgent=True)
    check("…capped at 150 motor steps (FOCUS_TRIM_MAX_STEPS), of a travel of 2100",
          a.focus_steps == grid_focus_steps(10.0, 5.0) + 150 and config.FOCUS_TRIM_MAX_STEPS == 150
          and LENS_STEPS == 2100, f"{a.focus_steps} vs {grid_focus_steps(10.0, 5.0)} + 150")

    # ---- autofocus has the lens: nobody else moves zoom or focus ----------------
    af = object()
    a.take_lens(af)
    n = len(a.focuser.writes)
    said = (a.set_zoom_mm(4.4, urgent=True), a.set_focus(1.0), a.refocus(2.0),
            a.set_focus_steps(100))
    check("the lens taken: everyone else's zoom and focus come back HELD, nothing moves",
          len(a.focuser.writes) == n and set(said) == {LensMove.HELD} and a.lens_moving
          and a.lens_owner is af, f"{a.focuser.writes[n:]} {said}")
    check("…its owner's own moves go through",
          a.set_focus_steps(100, owner=af) is LensMove.MOVED and a.focus_steps == 100)
    a.give_lens(object())
    check("…only its owner can give it back", a.lens_owner is af)
    a.give_lens(af)
    check("…and then the others' requests are taken again",
          a.lens_owner is None and not a.lens_moving and bool(a.set_zoom_mm(4.4, urgent=True)))

    # ---- how long a move should take goes with it, for a controller with no busy flag
    w = Ptz()
    w.focuser = RecordingFocuser()
    w.set_focus_steps(0)
    w.set_focus_steps(LENS_STEPS)
    w.set_focus_steps(LENS_STEPS - 105)
    check("a move across the whole focus travel is expected to take LENS_TRAVEL_S",
          abs(w.focuser.expected[-2] - (config.LENS_SETTLE_S + config.LENS_TRAVEL_S)) < 1e-9,
          f"{w.focuser.expected}")
    check("…a short one a share of it",
          abs(w.focuser.expected[-1] - (config.LENS_SETTLE_S + 0.05 * config.LENS_TRAVEL_S)) < 1e-9,
          f"{w.focuser.expected}")
    w.home()
    zoom_writes = [v for ch, v in w.focuser.writes if ch == OPT_ZOOM]
    check("home zooms to the curve's wide end, whichever way the motor runs",
          zoom_writes[-1] == ptz_mod._interp(config.ZOOM_MIN_MM, config.ZOOM_CURVE_STEPS)
          and w.zoom_mm == config.ZOOM_MIN_MM and w.zoom_steps == zoom_writes[-1],
          f"{zoom_writes}")

    # ---- autofocus and the tools move the focus motor itself ------------------
    f = Ptz()
    f.focuser = RecordingFocuser()
    f.set_focus(10.0)
    f.set_focus_steps(525)
    check("set_focus_steps: straight to that step of the motor's travel",
          f.focuser.writes[-1] == (OPT_FOCUS, 525) and f.focus_steps == 525,
          f"{f.focuser.writes[-1]}, {f.focus_steps}")
    check("…the same again is no move", f.set_focus_steps(525) is LensMove.SAME)
    n = len(f.focuser.writes)
    f.set_focus(10.0)
    check("…and the tracker's next focus moves it, even to the distance it had",
          len(f.focuser.writes) == n + 1)
    check("the distance last asked for is kept, moved for or not", f.subject_m == 10.0)

    # ---- zooming out for a lost person skips the rate limit ----------------
    config.ZOOM_RATE_LIMIT_S = 2.0                 # section 4 turned it off
    p = Ptz()
    p.focuser = RecordingFocuser()
    first = p.set_zoom_mm(8.0)
    said = p.set_zoom_mm(5.0)
    check("a second zoom inside ZOOM_RATE_LIMIT_S is dropped, and says so",
          p.zoom_mm == 8.0 and first is LensMove.MOVED and said is LensMove.PACED,
          f"{p.zoom_mm} {first} {said}")
    check("a change under ZOOM_MIN_STEP_MM says it is too small, the same zoom that it is the same",
          p.set_zoom_mm(8.0 + config.ZOOM_MIN_STEP_MM / 2, urgent=True) is LensMove.SMALL
          and p.set_zoom_mm(8.0, urgent=True) is LensMove.SAME and p.zoom_mm == 8.0)
    said = p.set_zoom_mm(config.ZOOM_MIN_MM, urgent=True)
    check("…but an urgent one goes at once", p.zoom_mm == config.ZOOM_MIN_MM and bool(said),
          f"{p.zoom_mm}")

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
    check("both sticks full: each axis at its own full speed",
          jogged(1.0, 1.0) == (config.JOG_PAN_MAX_DPS, config.JOG_TILT_MAX_DPS),
          f"{jogged(1.0, 1.0)}")
    check("one stick's speed doesn't depend on the other's",
          jogged(0.5, 1.0)[0] == jogged(0.5, 0.0)[0], f"{jogged(0.5, 1.0)}")
    check("past the end counts as the end", jogged(2.0, 0.0)[0] == config.JOG_PAN_MAX_DPS)
    check("…and the soft limits still hold", jogged(1.0, 0.0, dt=10.0)[0] == config.PAN_MAX_DEG)
    p.park()
    p.focuser.writes.clear()
    p.jog(0.0, 0.0, 1.0)
    check("knob at the centre: no servo writes", p.focuser.writes == [])
    p.park()
    p.jog(1.0, 0.0, 0.05)
    first = p.pan_deg
    check("eases in: the first tick is slower than full speed",
          0 < first < config.JOG_PAN_MAX_DPS * 0.05, f"{first:.2f}")
    for _ in range(20):
        p.jog(1.0, 0.0, 0.05)
    held_at = p.pan_deg
    p.jog(0.0, 0.0, 0.05)
    check("let go, it eases out: still turning one tick later",
          p.pan_deg > held_at and p.jogging, f"{p.pan_deg - held_at:.2f}")
    for _ in range(20):
        p.jog(0.0, 0.0, 0.05)
    stopped_at = p.pan_deg
    p.jog(0.0, 0.0, 0.05)
    check("…and comes to a stop", not p.jogging and p.pan_deg == stopped_at)

    # ---- servo drivers: pigpio hardware PWM, or the controller's registers --
    class FakePi:
        def __init__(self):
            self.pwm: dict[int, tuple[int, int]] = {}
            self.calls = 0

        def hardware_PWM(self, gpio, hz, duty):
            self.pwm[gpio] = (hz, duty)
            self.calls += 1

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
    n = pi.calls
    for _ in range(20):                       # a head at rest, asked every tick
        p.set_pan(0.0)
        p.set_tilt(0.0)
    check("pigpio: an unchanged angle is not sent again", pi.calls == n, f"{pi.calls - n}")
    per_deg = (config.SERVO_US_AT_180 - config.SERVO_US_AT_0) / 180
    p.set_pan(0.1)
    check("pigpio: a tenth of a degree moves the pulse a tenth of a degree's width",
          abs(us(pi, config.PAN_GPIO) - (centre + 0.1 * per_deg * config.PAN_SIGN)) < 0.05,
          f"{us(pi, config.PAN_GPIO):.2f} µs")
    p.set_tilt(30.0)
    tilt_centre = config.SERVO_US_AT_0 + config.TILT_CENTER_RAW / 180 * (
        config.SERVO_US_AT_180 - config.SERVO_US_AT_0)
    check("pigpio: tilt follows TILT_CENTER_RAW and TILT_SIGN",
          abs(us(pi, config.TILT_GPIO) - (tilt_centre + 30 * per_deg * config.TILT_SIGN)) < 0.05)
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
    p.set_tilt(30.6)
    writes = dict(p.servos.focuser.writes)
    check("arducam: pan and tilt go to the registers in whole degrees",
          writes.get(OPT_MOTOR_X) == round(config.PAN_CENTER_RAW + 10.4 * config.PAN_SIGN)
          and writes.get(OPT_MOTOR_Y) == round(config.TILT_CENTER_RAW + 30.6 * config.TILT_SIGN),
          f"{writes}")

    # ---- the IMX477 kit's controller (firmware 0x0104) ---------------------
    bus = FakeBus(0x0104)
    f = focuser_on(bus)
    f.set(OPT_ZOOM, 2100)
    f.set(OPT_FOCUS, 1050)
    f.set(OPT_MOTOR_X, 120)
    check("imx477: zoom on 0x01, focus on 0x00, in steps as they are; pan unchanged",
          bus.writes == [(0x01, 2100), (0x00, 1050), (0x05, 120)], f"{bus.writes}")
    check("imx477: reads come back in steps",
          f.get(OPT_ZOOM) == 2100 and f.get(OPT_FOCUS) == 1050)
    check("a position past the travel is held to it", f.set(OPT_FOCUS, 9999) == LENS_STEPS)
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
    f.set(OPT_ZOOM, 2100)
    f.set(OPT_FOCUS, 1050)
    f.wake()
    check("older controller: steps become its own numbers at the write, zoom on 0x00 "
          "(3000-20000) and focus on 0x01 (0-20000); no wake writes",
          bus.writes == [(0x00, 20000), (0x01, 10000)], f"{bus.writes}")
    check("…and reads come back in steps", f.get(OPT_ZOOM) == 2100 and f.get(OPT_FOCUS) == 1050)

    # ---- the busy flag is the low byte of a 16-bit word ----------------------
    bus = FakeBus(0x0104)
    f = focuser_on(bus)
    bus.regs[0x04] = 0x0001
    check("busy: a word of 1 (flag in the low byte) reads as busy", f.busy() is True)
    bus.regs[0x04] = 0
    check("…and 0 as idle", f.busy() is False)

    # ---- a lens move waits for the one before ------------------------------
    import time as _time
    class BusyBus(FakeBus):
        """A motor runs after each lens write, until told it has stopped."""
        def write_i2c_block_data(self, addr, reg, data):
            super().write_i2c_block_data(addr, reg, data)
            if reg in (0x00, 0x01):
                self.regs[0x04] = 1

    bus = BusyBus(0x0104)
    f = focuser_on(bus)
    f.queue_lens = True
    check("nothing asked of the lens: idle", f.lens_idle)
    f.set(OPT_ZOOM, 2100)
    f.set(OPT_FOCUS, 1050)
    _time.sleep(0.15)
    check("zoom goes first, and focus waits while the zoom motor runs",
          bus.writes == [(0x01, 2100)] and not f.lens_idle, f"{bus.writes}")
    f.set(OPT_FOCUS, 1260)
    bus.regs[0x04] = 0
    _time.sleep(0.2)
    check("…then focus, at the latest value asked for; still not idle: its motor is running",
          bus.writes == [(0x01, 2100), (0x00, 1260)] and not f.lens_idle, f"{bus.writes}")
    stopped = _time.monotonic()
    bus.regs[0x04] = 0
    check("…idle once that has stopped too, which a waiter is told at once",
          f.wait_lens_idle(1.0) and f.lens_idle and _time.monotonic() - stopped < 0.1)
    check("…with when the last move started and stopped",
          0 < f.lens_started_at < f.lens_stopped_at <= _time.monotonic())

    # ---- a controller whose busy flag never sets: moves are waited out by time,
    # ---- one after the other (a zoom and its refocus take the sum, not the longer)
    bus = FakeBus(0x0104)
    f = focuser_on(bus)
    f.queue_lens = True
    t0 = _time.monotonic()
    f.set(OPT_ZOOM, 1000, expect_s=0.3)
    f.set(OPT_FOCUS, 500, expect_s=0.3)
    _time.sleep(0.4)
    check("no busy flag: after the longer of two moves the lens is still not idle",
          not f.lens_idle and bus.writes == [(0x01, 1000), (0x00, 500)], f"{bus.writes}")
    check("…idle after the two together", f.wait_lens_idle(1.0)
          and 0.55 <= _time.monotonic() - t0 < 0.9, f"{_time.monotonic() - t0:.2f} s")
    p = Ptz()
    p.focuser = f
    travel, config.LENS_TRAVEL_S = config.LENS_TRAVEL_S, 0.5
    config.ZOOM_RATE_LIMIT_S = 0.0
    p.set_zoom_mm(8.0)
    check("Ptz.lens_moving: true from the moment a zoom is asked for…", p.lens_moving)
    t0 = _time.monotonic()
    p.wait_lens()
    check("…and wait_lens returns when zoom and refocus are both done",
          not p.lens_moving and _time.monotonic() - t0 > 0.1, f"{_time.monotonic() - t0:.2f} s")
    config.LENS_TRAVEL_S = travel

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all ptz checks passed")


if __name__ == "__main__":
    main()
