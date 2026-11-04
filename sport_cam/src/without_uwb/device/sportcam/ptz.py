"""Pan, tilt, zoom and focus: the Arducam PTZ base.

The B0167B12 kit puts all four axes behind a single controller board at
I2C 0x0C (Arducam's `Focuser` register map):

    channel      register   range        axis
    OPT_ZOOM     0x00       3000-20000   zoom motor (wide → tele)
    OPT_FOCUS    0x01       0-20000      focus motor
    OPT_MOTOR_X  0x05       0-180        pan servo, degrees
    OPT_MOTOR_Y  0x06       0-180        tilt servo, degrees
    OPT_IRCUT    0x0C       0/1          IR-cut filter

That is the older controllers' map. The IMX477 kit's controller (firmware
0x0104 on, register 0x40) swaps zoom and focus and runs both 0-2100, from
Arducam's B016712MP/Focuser.py. Everything here, config.py and focuscal keep
the older 3000/0-20000 scale, and `Focuser.set` rescales for the newer one.
It also powers up in mode 0 (register 0x30), in which it acknowledges every
move and ignores it: `Ptz.start` switches it to mode 1 and resets the lens,
as Arducam's tool does on its r and t keys.

The pan and tilt registers take **whole degrees**. Zoomed in (≈ 33° across
the frame at full zoom) one degree is ≈ 3 % of the frame, so a slow pan
visibly steps. With `SERVO_DRIVER = "pigpio"` the two servo signal leads come
off the controller and the Pi drives them itself, through the pigpio daemon's
hardware PWM on GPIO12 / GPIO13 (docs/04, "Servo drive"): pulse widths to a
fraction of a microsecond, so the servo's own deadband (≈ 0.3–0.5°) is the
limit. Zoom and focus stay on the controller either way.

Servos are open-loop: what we command is what we believe. `pan_deg` and
`tilt_deg` therefore report the commanded angle, which is good to a couple of
degrees. The tracker's CV trim and `docs/04` both assume that.
"""
from __future__ import annotations

import math
import threading
import time

try:
    from smbus2 import SMBus
except ImportError:          # dev machine / CI — run headless
    SMBus = None

try:
    import pigpio
except ImportError:          # dev machine / CI, or the Arducam servo driver
    pigpio = None

from . import config
from .motion import accelerate

CHIP_ADDR = 0x0C

OPT_ZOOM = "zoom"
OPT_FOCUS = "focus"
OPT_MOTOR_X = "pan"
OPT_MOTOR_Y = "tilt"

# channel -> (register, min, max)
_CHANNELS = {
    OPT_ZOOM:    (0x00, 3000, 20000),
    OPT_FOCUS:   (0x01, 0, 20000),
    OPT_MOTOR_X: (0x05, 0, 180),
    OPT_MOTOR_Y: (0x06, 0, 180),
}
_REG_BUSY = 0x04
_REG_MODE = 0x30
_REG_VERSION = 0x40
# The controller ignores a write within ~10 ms of the one before (lands at 20 ms:
# scripts/pi/ptz-gap-check.sh), so writes are spaced by this much. Pan then
# tilt in one control tick lost the tilt
_WRITE_GAP_S = 0.025
_IMX477_FIRMWARE = 0x0104
# the IMX477 kit's controller: channel -> (register, min, max, lens reset register)
_IMX477_LENS = {
    OPT_ZOOM:  (0x01, 0, 2100, 0x0B),
    OPT_FOCUS: (0x00, 0, 2100, 0x0A),
}


def _lens_motor(channel: str) -> str:
    """The channel whose register really drives `channel`'s motor."""
    if config.LENS_SWAP_ZOOM_FOCUS and channel in (OPT_ZOOM, OPT_FOCUS):
        return OPT_FOCUS if channel == OPT_ZOOM else OPT_ZOOM
    return channel


class Focuser:
    """Thin, thread-safe wrapper over the controller's I2C register map."""

    def __init__(self, bus: int = 1) -> None:
        self._bus = SMBus(bus) if SMBus else None
        self._lock = threading.Lock()
        self._wrote_at = 0.0
        self.available = self._bus is not None
        self.firmware = self._read(_REG_VERSION) if self._bus else None

    @property
    def imx477(self) -> bool:
        return (self.firmware or 0) >= _IMX477_FIRMWARE

    def _register(self, channel: str, value: int) -> tuple[int, int]:
        """The register and value to write for a value on the older scale.

        With LENS_SWAP_ZOOM_FOCUS the zoom goes to the focus register and the
        focus to the zoom one; the value is still scaled as its own channel.
        """
        motor = _lens_motor(channel)
        reg, lo, hi = _CHANNELS[channel]
        if self.imx477 and channel in _IMX477_LENS:
            _reg, lo2, hi2, _reset = _IMX477_LENS[channel]
            reg = _IMX477_LENS[motor][0]
            value = round(lo2 + (value - lo) * (hi2 - lo2) / (hi - lo))
        else:
            reg = _CHANNELS[motor][0]
        return reg, value

    def _read(self, reg: int) -> int | None:
        try:
            with self._lock:
                hi, lo = self._bus.read_i2c_block_data(CHIP_ADDR, reg, 2)
        except OSError:
            return None
        return (hi << 8) | lo

    def _write(self, reg: int, value: int) -> None:
        with self._lock:
            # sooner than this after the last write, the controller ignores it
            wait = self._wrote_at + _WRITE_GAP_S - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._bus.write_i2c_block_data(CHIP_ADDR, reg, [(value >> 8) & 0xFF, value & 0xFF])
            self._wrote_at = time.monotonic()

    def set(self, channel: str, value: int, wait: bool = False) -> int:
        _reg, lo, hi = _CHANNELS[channel]
        value = int(max(lo, min(hi, value)))
        if self._bus:
            self._write(*self._register(channel, value))
            if wait:
                self._wait_idle()
        return value

    def get(self, channel: str) -> int | None:
        if not self._bus:
            return None
        reg, lo, hi = _CHANNELS[channel]
        raw = self._read(self._register(channel, lo)[0])
        if raw is not None and self.imx477 and channel in _IMX477_LENS:
            _reg, lo2, hi2, _reset = _IMX477_LENS[channel]
            raw = round(lo + (raw - lo2) * (hi - lo) / (hi2 - lo2))
        return raw

    def wake(self) -> None:
        """The IMX477 kit's controller: lens reset, then out of mode 0."""
        if not (self._bus and self.imx477):
            return
        for _reg, _lo, _hi, reset in _IMX477_LENS.values():
            self._write(reset, 0)
            self._wait_idle(15.0)
        if self._read(_REG_MODE) == 0:
            self._write(_REG_MODE, 1)
            time.sleep(0.05)
            self._wait_idle(20.0)

    def busy(self) -> bool | None:
        """A lens motor is moving; None if the controller doesn't answer.

        The busy register is a 16-bit word like the others, read whole, as
        Arducam's Focuser.py does: its flag is in the low byte, so reading
        only the first (high) byte, as this once did, never saw it set.
        """
        try:
            with self._lock:
                hi, lo = self._bus.read_i2c_block_data(CHIP_ADDR, _REG_BUSY, 2)
        except OSError:
            return None
        return ((hi << 8) | lo) != 0

    def _wait_idle(self, timeout_s: float = 3.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if not self.busy():
                return
            time.sleep(0.01)


class ArducamServos:
    """Pan and tilt through the controller's registers: whole degrees only."""

    def __init__(self, focuser: Focuser) -> None:
        self.focuser = focuser
        self._sent: dict[str, int] = {}

    @property
    def available(self) -> bool:
        return self.focuser.available

    def write(self, channel: str, raw_deg: float) -> None:
        # Only a changed degree: each write waits out _WRITE_GAP_S, so
        # an unchanged axis re-sent every tick would only hold up the other
        raw = round(raw_deg)
        if self._sent.get(channel) != raw:
            self._sent[channel] = self.focuser.set(channel, raw)


class PigpioServos:
    """Pan and tilt driven by the Pi: pigpio hardware PWM, sub-degree steps.

    GPIO12 and GPIO13 are the Pi 4's two hardware PWM channels (PWM0, PWM1),
    so the pulses come from the PWM block itself, without CPU or DMA jitter.
    Both run at SERVO_PWM_HZ. A raw angle maps linearly onto the pulse width
    between SERVO_US_AT_0 and SERVO_US_AT_180, as the controller's registers
    did, so the centre and sign calibration carries over unchanged.

    Needs the pigpio daemon (`sudo systemctl enable --now pigpiod`); the
    service talks to it over a local socket and does not run as root.
    """

    def __init__(self, pi=None) -> None:
        self._pi = pi
        if self._pi is None and pigpio is not None:
            self._pi = pigpio.pi()
            if not self._pi.connected:
                print("[ptz] pigpiod is not running — pan and tilt will not move "
                      "(sudo systemctl enable --now pigpiod)")
                self._pi = None
        self._gpio = {OPT_MOTOR_X: config.PAN_GPIO, OPT_MOTOR_Y: config.TILT_GPIO}

    @property
    def available(self) -> bool:
        return self._pi is not None

    def write(self, channel: str, raw_deg: float) -> None:
        if self._pi is None:
            return
        raw_deg = max(0.0, min(180.0, raw_deg))
        us = config.SERVO_US_AT_0 + raw_deg / 180.0 * (config.SERVO_US_AT_180 - config.SERVO_US_AT_0)
        # duty is in millionths of the period: us / (1e6 / hz) × 1e6
        self._pi.hardware_PWM(self._gpio[channel], config.SERVO_PWM_HZ,
                              round(us * config.SERVO_PWM_HZ))


class Ptz:
    """Pan, tilt and zoom in engineering units.

    Angles are **degrees from centre**: pan 0 is the lens pointing along the
    the enclosure's front, positive to the right; tilt 0 is horizontal, positive
    up. Both are clamped to the soft limits in `config`, which exist because
    the mechanical travel of the metal base is narrower than the servos' 180°.
    """

    def __init__(self, bus: int = 1) -> None:
        self.focuser = Focuser(bus)
        self.servos = (PigpioServos() if config.SERVO_DRIVER == "pigpio"
                       else ArducamServos(self.focuser))
        self._pan = 0.0
        self._tilt = 0.0
        self._jog_vel = (0.0, 0.0)             # deg/s: the joystick's eased speed
        self._jog_at = 0.0
        self._zoom_mm = config.ZOOM_MIN_MM
        self._last_zoom_at = 0.0
        self._focus_dist_m: float | None = None    # distance the focus was set for
        self._want_dist_m: float | None = None     # latest distance we were told
        self._focus_raw: int | None = None
        self._last_focus_at = 0.0
        self._lens_raw: dict[str, int] = {}        # last sent to each lens motor
        self._lens_until = 0.0                     # when the last lens move should be done
        self._lens_written_at = 0.0                # when the last lens move was sent
        self._busy_seen = False                    # the controller's busy flag has been seen set
        # What the last autofocus taught: how far (raw focus steps) the sharp
        # position was from FOCUS_GRID's for that zoom. Added to every grid
        # lookup after, so zoom changes and sweeps stay near focus.
        self._focus_trim = 0
        # Autofocus is sweeping the focus motor: everyone else's zoom and
        # focus requests wait (they would spoil the sweep, and it them).
        self.af_active = False

    # ---- pan / tilt -------------------------------------------------------
    @property
    def pan_deg(self) -> float:
        return self._pan

    @property
    def tilt_deg(self) -> float:
        return self._tilt

    def set_pan(self, deg: float) -> float:
        deg = max(config.PAN_MIN_DEG, min(config.PAN_MAX_DEG, deg))
        self._pan = deg
        self.servos.write(OPT_MOTOR_X, config.PAN_CENTER_RAW + deg * config.PAN_SIGN)
        return deg

    def set_tilt(self, deg: float) -> float:
        deg = max(config.TILT_MIN_DEG, min(config.TILT_MAX_DEG, deg))
        self._tilt = deg
        self.servos.write(OPT_MOTOR_Y, config.TILT_CENTER_RAW + deg * config.TILT_SIGN)
        return deg

    def nudge_tilt(self, delta_deg: float) -> float:
        return self.set_tilt(self._tilt + delta_deg)

    def jog(self, x: float, y: float, dt: float) -> None:
        """Turn for `dt` seconds at a speed set by the app's joystick.

        `x` (right +) and `y` (up +) are the app's pan and tilt sticks, each
        its knob's offset as a fraction of its travel. Each axis's speed grows
        with the square of its own stick, so a small pull aims finely and a
        full one turns at JOG_PAN_MAX_DPS / JOG_TILT_MAX_DPS, whatever the
        other stick does. It gets there, and back to a stop at (0, 0), no
        faster than JOG_*_ACCEL_DPS2. The soft limits still apply.
        """
        now = time.monotonic()
        if now - self._jog_at > 0.25:          # not a continuing jog: from rest
            self._jog_vel = (0.0, 0.0)
        self._jog_at = now
        x, y = max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y))
        vp, vt = self._jog_vel
        vp = accelerate(vp, x * abs(x) * config.JOG_PAN_MAX_DPS, config.JOG_PAN_ACCEL_DPS2, dt)
        vt = accelerate(vt, y * abs(y) * config.JOG_TILT_MAX_DPS, config.JOG_TILT_ACCEL_DPS2, dt)
        if vp:
            want = self._pan + vp * dt
            if self.set_pan(want) != want:    # at a soft limit
                vp = 0.0
        if vt:
            want = self._tilt + vt * dt
            if self.set_tilt(want) != want:
                vt = 0.0
        self._jog_vel = (vp, vt)

    @property
    def jogging(self) -> bool:
        """Still turning from the joystick: easing to a stop after it let go."""
        return self._jog_vel != (0.0, 0.0)

    def start(self) -> None:
        """Wake the controller, centre the head and home the lens. On startup."""
        self.focuser.wake()
        self.park()
        self.home()

    def park(self) -> None:
        """Centre both axes and relax the lens. Called on shutdown."""
        self.set_pan(0.0)
        self.set_tilt(0.0)
        self._jog_vel = (0.0, 0.0)

    # ---- zoom / focus -----------------------------------------------------
    @property
    def zoom_mm(self) -> float:
        return self._zoom_mm

    @property
    def hfov_deg(self) -> float:
        """Horizontal field of view at the current zoom.

        The tracker uses this to turn a bearing into a pixel column, so the
        detector can search a strip instead of the whole frame. The sensor's
        half-width is derived from the published wide-end field of view rather
        than hard-coded, so correcting `HFOV_WIDE_DEG` after the zoom
        calibration fixes this too.
        """
        half_w = config.ZOOM_MIN_MM * math.tan(math.radians(config.HFOV_WIDE_DEG / 2))
        return math.degrees(2 * math.atan(half_w / max(0.1, self._zoom_mm)))

    def home(self) -> None:
        """Zoom to wide (ZOOM_CURVE's wide end, whichever way the motor runs)
        and focus to its low stop — far out of focus: refocus() after."""
        self._lens_set(OPT_ZOOM, _interp(config.ZOOM_MIN_MM, config.ZOOM_CURVE))
        self._lens_set(OPT_FOCUS, _CHANNELS[OPT_FOCUS][1])
        self._zoom_mm = config.ZOOM_MIN_MM
        self._focus_raw = None
        # Forget the distance focused for: the motor is not there any more,
        # and set_focus's deadband would otherwise skip the next request.
        self._focus_dist_m = None

    def refocus(self, dist_m: float | None = None) -> None:
        """Focus now, whatever the deadband and rate limit say: for `dist_m`,
        or the last distance asked for (AWAKE_FOCUS_M before any)."""
        if self.af_active:
            return
        self._apply_focus(dist_m or self._want_dist_m or self._focus_dist_m
                          or config.AWAKE_FOCUS_M)

    def learn_focus(self, pos: float) -> None:
        """Autofocus found the focus motor sharp at `pos` (0…1): keep how far
        that is from FOCUS_GRID's position for this zoom, and apply it to
        every lookup from now on."""
        _reg, lo, hi = _CHANNELS[OPT_FOCUS]
        raw = round(lo + max(0.0, min(1.0, pos)) * (hi - lo))
        dist = self._want_dist_m or self._focus_dist_m or config.AWAKE_FOCUS_M
        self._focus_trim = raw - focus_raw(self._zoom_mm, dist)

    @property
    def lens_moving(self) -> bool:
        """A zoom or focus move is under way (or autofocus is sweeping): the
        picture is blurred for a while, and a missed detection means little."""
        return self.af_active or time.monotonic() < self._lens_until

    def lens_busy(self) -> bool:
        """The lens motors are moving now: the controller's busy flag, or, from
        a controller that never sets it, the time a move should take."""
        b = self.focuser.busy() if self.focuser.available else None
        if b is None or not self._busy_seen:
            if b:
                self._busy_seen = True
                return True
            return time.monotonic() < self._lens_until
        return b

    def _lens_set(self, channel: str, raw: int) -> None:
        """Move a lens motor, noting when it should have arrived (wait_lens):
        the controller won't say."""
        _reg, lo, hi = _CHANNELS[channel]
        last = self._lens_raw.get(channel)
        share = 1.0 if last is None else abs(raw - last) / (hi - lo)
        self._lens_raw[channel] = raw
        self._lens_until = max(self._lens_until, time.monotonic() + config.LENS_SETTLE_S
                               + share * config.LENS_TRAVEL_S)
        self._lens_written_at = time.monotonic()
        self.focuser.set(channel, raw)

    def set_zoom_mm(self, efl_mm: float, urgent: bool = False) -> None:
        """Set the zoom motor from a wanted focal length.

        `urgent` skips ZOOM_RATE_LIMIT_S: zooming out to look for a person
        lost while recording can't wait for the lens's next turn.

        The motor is open-loop with a non-linear relationship between step
        count and focal length; `config.ZOOM_CURVE` holds the measured
        (efl_mm, raw) pairs from the calibration in docs/04 and we interpolate
        between them. The default curve is a straight line between the two
        ends, which is close enough to start filming and wrong enough that you
        should measure it once.
        """
        if self.af_active:
            return                          # the sweep's picture must hold still
        efl_mm = max(config.ZOOM_MIN_MM, min(config.ZOOM_MAX_MM, efl_mm))
        now = time.monotonic()
        if (abs(efl_mm - self._zoom_mm) < config.ZOOM_MIN_STEP_MM
                or (not urgent and now - self._last_zoom_at < config.ZOOM_RATE_LIMIT_S)):
            return
        self._zoom_mm = efl_mm
        self._last_zoom_at = now
        self._lens_set(OPT_ZOOM, _interp(efl_mm, config.ZOOM_CURVE))
        # A zoom move always throws focus off, so refocus at once for the
        # last known distance, ignoring the focus rate limit.
        self._apply_focus(self._want_dist_m or self._focus_dist_m or 10.0)

    @property
    def focus_m(self) -> float | None:
        """The subject distance the focus is set for; None until first set."""
        return self._focus_dist_m

    def wait_lens(self, timeout_s: float | None = None) -> None:
        """Until the zoom and focus motors have stopped, or `timeout_s`.

        The controller's busy flag says so. Until it has been seen set once
        (a controller that never sets it), a move is waited out by time
        instead: LENS_SETTLE_S plus its share of LENS_TRAVEL_S.
        """
        if not self.focuser.available:
            return
        if timeout_s is None:
            timeout_s = config.LENS_SETTLE_S + config.LENS_TRAVEL_S + 1.0
        deadline = time.monotonic() + timeout_s
        seen = False
        while time.monotonic() < deadline:
            b = self.focuser.busy()
            if b is None:
                break                                   # no answer: by time
            since = time.monotonic() - self._lens_written_at
            if b:
                seen = self._busy_seen = True
            elif seen or (self._busy_seen and since > 0.05):
                time.sleep(config.LENS_SETTLE_S)        # stopped; let the picture settle
                return
            elif since > 0.3:
                break                                   # never set: by time
            time.sleep(0.01)
        time.sleep(min(max(0.0, deadline - time.monotonic()),
                       max(0.0, self._lens_until - time.monotonic())))

    @property
    def focus_pos(self) -> float | None:
        """Where the focus motor was last sent, as a fraction of its travel
        (0 at its low stop, 1 at its high); None until it has been."""
        if self._focus_raw is None:
            return None
        _reg, lo, hi = _CHANNELS[OPT_FOCUS]
        return (self._focus_raw - lo) / (hi - lo)

    def set_focus_pos(self, pos: float) -> None:
        """Send the focus motor to `pos` of its travel (0…1): the app's focus
        slider, focusing by eye.

        Straight to the motor, not through FOCUS_GRID, which until it is
        calibrated maps every distance to the same position. Forgets the
        distance it was focused for, so the tracker's next set_focus moves
        the motor whatever it asks for.
        """
        _reg, lo, hi = _CHANNELS[OPT_FOCUS]
        raw = round(lo + max(0.0, min(1.0, pos)) * (hi - lo))
        self._focus_dist_m = None
        self._last_focus_at = time.monotonic()
        if raw != self._focus_raw:
            self._focus_raw = raw
            self._lens_set(OPT_FOCUS, raw)

    def set_focus(self, dist_m: float, urgent: bool = False) -> None:
        """Focus for a subject `dist_m` away, at the current focal length.

        `urgent` skips FOCUS_RATE_LIMIT_S, as for zoom: the app's focus
        slider is a person waiting to see the picture sharpen.

        Rate-limited, and changes smaller than FOCUS_DEADBAND_DIOPTRE in 1/d
        are ignored: at 10 m that is about ±2 m, well inside the depth of
        field at any zoom, so the motor is not chattering on distance-estimate noise.
        """
        dist_m = max(0.5, dist_m)
        self._want_dist_m = dist_m
        if self.af_active:
            return                          # autofocus decides, for now
        now = time.monotonic()
        if self._focus_dist_m is not None:
            if (abs(1.0 / dist_m - 1.0 / self._focus_dist_m) < config.FOCUS_DEADBAND_DIOPTRE
                    or (not urgent and now - self._last_focus_at < config.FOCUS_RATE_LIMIT_S)):
                return
        self._apply_focus(dist_m)

    def _apply_focus(self, dist_m: float) -> None:
        self._focus_dist_m = dist_m
        self._last_focus_at = time.monotonic()
        _reg, lo, hi = _CHANNELS[OPT_FOCUS]
        raw = int(max(lo, min(hi, focus_raw(self._zoom_mm, dist_m) + self._focus_trim)))
        if raw != self._focus_raw:
            self._focus_raw = raw
            self._lens_set(OPT_FOCUS, raw)



def focus_raw(efl_mm: float, dist_m: float,
              grid: dict[float, list[tuple[float, int]]] | None = None) -> int:
    """Focus motor position for a focal length and subject distance.

    Bilinear over `config.FOCUS_GRID`: linear in focal length between rows,
    and within a row linear in 1/distance, which is how lens extension
    actually varies. Clamped at the edges of the measured grid rather than
    extrapolated — an extrapolated focus motor position is a guess with a
    motor attached.
    """
    grid = grid if grid is not None else config.FOCUS_GRID
    rows = sorted(grid)
    inv_d = 1.0 / max(0.1, dist_m)

    def row_at(efl: float) -> float:
        # rows are (distance, raw); in 1/d they run far → near, so sort by it
        pts = sorted((1.0 / d, raw) for d, raw in grid[efl])
        return float(_interp(inv_d, pts, as_int=False))

    if efl_mm <= rows[0]:
        return int(round(row_at(rows[0])))
    if efl_mm >= rows[-1]:
        return int(round(row_at(rows[-1])))
    for e0, e1 in zip(rows, rows[1:]):
        if efl_mm <= e1:
            t = (efl_mm - e0) / (e1 - e0)
            return int(round(row_at(e0) + t * (row_at(e1) - row_at(e0))))
    return int(round(row_at(rows[-1])))


def _interp(x: float, curve: list[tuple[float, float]], as_int: bool = True) -> float:
    """Piecewise-linear lookup over a sorted (x, raw) calibration curve."""
    def out(v: float) -> float:
        return int(round(v)) if as_int else v
    if x <= curve[0][0]:
        return out(curve[0][1])
    for (x0, y0), (x1, y1) in zip(curve, curve[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
            return out(y0 + t * (y1 - y0))
    return out(curve[-1][1])
