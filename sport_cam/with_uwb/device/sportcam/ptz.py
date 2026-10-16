"""Arducam PTZ controller — pan, tilt, zoom and focus on one I2C device.

The B0167B12 kit puts all four axes behind a single controller board at
I2C 0x0C (Arducam's `Focuser` register map):

    channel      register   range        axis
    OPT_ZOOM     0x00       3000-20000   zoom motor (wide → tele)
    OPT_FOCUS    0x01       0-20000      focus motor
    OPT_MOTOR_X  0x05       0-180        pan servo, degrees
    OPT_MOTOR_Y  0x06       0-180        tilt servo, degrees
    OPT_IRCUT    0x0C       0/1          IR-cut filter

This replaces the old `tilt.py` (pigpio PWM) and `lens.py` (bespoke register
writes). There is no pan stepper and no base controller any more — pan is a
**position** command on this bus, not a velocity relayed over the network.

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

from . import config

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


class Focuser:
    """Thin, thread-safe wrapper over the controller's I2C register map."""

    def __init__(self, bus: int = 1) -> None:
        self._bus = SMBus(bus) if SMBus else None
        self._lock = threading.Lock()
        self.available = self._bus is not None

    def set(self, channel: str, value: int, wait: bool = False) -> int:
        reg, lo, hi = _CHANNELS[channel]
        value = int(max(lo, min(hi, value)))
        if self._bus:
            with self._lock:
                self._bus.write_i2c_block_data(
                    CHIP_ADDR, reg, [(value >> 8) & 0xFF, value & 0xFF])
            if wait:
                self._wait_idle()
        return value

    def get(self, channel: str) -> int | None:
        reg, _lo, _hi = _CHANNELS[channel]
        if not self._bus:
            return None
        with self._lock:
            hi, lo = self._bus.read_i2c_block_data(CHIP_ADDR, reg, 2)
        return (hi << 8) | lo

    def _wait_idle(self, timeout_s: float = 3.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                with self._lock:
                    if self._bus.read_i2c_block_data(CHIP_ADDR, _REG_BUSY, 1)[0] == 0:
                        return
            except OSError:
                return
            time.sleep(0.01)


class Ptz:
    """Pan, tilt and zoom in engineering units.

    Angles are **degrees from centre**: pan 0 is the lens pointing along the
    anchor bar's normal, positive to the right; tilt 0 is horizontal, positive
    up. Both are clamped to the soft limits in `config`, which exist because
    the mechanical travel of the metal base is narrower than the servos' 180°.
    """

    def __init__(self, bus: int = 1) -> None:
        self.focuser = Focuser(bus)
        self._pan = 0.0
        self._tilt = 0.0
        self._zoom_mm = config.ZOOM_MIN_MM
        self._last_zoom_at = 0.0
        self._focus_dist_m: float | None = None    # distance the focus was set for
        self._want_dist_m: float | None = None     # latest distance we were told
        self._focus_raw: int | None = None
        self._last_focus_at = 0.0

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
        self.focuser.set(OPT_MOTOR_X, round(config.PAN_CENTER_RAW + deg * config.PAN_SIGN))
        return deg

    def set_tilt(self, deg: float) -> float:
        deg = max(config.TILT_MIN_DEG, min(config.TILT_MAX_DEG, deg))
        self._tilt = deg
        self.focuser.set(OPT_MOTOR_Y, round(config.TILT_CENTER_RAW + deg * config.TILT_SIGN))
        return deg

    def nudge_tilt(self, delta_deg: float) -> float:
        return self.set_tilt(self._tilt + delta_deg)

    def park(self) -> None:
        """Centre both axes and relax the lens. Called on shutdown."""
        self.set_pan(0.0)
        self.set_tilt(0.0)

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
        """Drive zoom and focus to their wide/near stops so step counts agree."""
        self.focuser.set(OPT_ZOOM, _CHANNELS[OPT_ZOOM][1], wait=True)
        self.focuser.set(OPT_FOCUS, _CHANNELS[OPT_FOCUS][1], wait=True)
        self._zoom_mm = config.ZOOM_MIN_MM
        self._focus_raw = None

    def set_zoom_mm(self, efl_mm: float) -> None:
        """Set the zoom motor from a wanted focal length.

        The motor is open-loop with a non-linear relationship between step
        count and focal length; `config.ZOOM_CURVE` holds the measured
        (efl_mm, raw) pairs from the calibration in docs/04 and we interpolate
        between them. The default curve is a straight line between the two
        ends, which is close enough to start filming and wrong enough that you
        should measure it once.
        """
        efl_mm = max(config.ZOOM_MIN_MM, min(config.ZOOM_MAX_MM, efl_mm))
        now = time.monotonic()
        if (abs(efl_mm - self._zoom_mm) < config.ZOOM_MIN_STEP_MM
                or now - self._last_zoom_at < config.ZOOM_RATE_LIMIT_S):
            return
        self._zoom_mm = efl_mm
        self._last_zoom_at = now
        self.focuser.set(OPT_ZOOM, _interp(efl_mm, config.ZOOM_CURVE))
        # A zoom move always throws focus off, so refocus at once for the
        # last known distance, ignoring the focus rate limit.
        self._apply_focus(self._want_dist_m or self._focus_dist_m or 10.0)

    def set_focus(self, dist_m: float) -> None:
        """Focus for a subject `dist_m` away, at the current focal length.

        Rate-limited, and changes smaller than FOCUS_DEADBAND_DIOPTRE in 1/d
        are ignored: at 10 m that is about ±2 m, well inside the depth of
        field at any zoom, so the motor is not chattering on ranging noise.
        """
        dist_m = max(0.5, dist_m)
        self._want_dist_m = dist_m
        now = time.monotonic()
        if self._focus_dist_m is not None:
            if (abs(1.0 / dist_m - 1.0 / self._focus_dist_m) < config.FOCUS_DEADBAND_DIOPTRE
                    or now - self._last_focus_at < config.FOCUS_RATE_LIMIT_S):
                return
        self._apply_focus(dist_m)

    def _apply_focus(self, dist_m: float) -> None:
        self._focus_dist_m = dist_m
        self._last_focus_at = time.monotonic()
        raw = focus_raw(self._zoom_mm, dist_m)
        if raw != self._focus_raw:
            self._focus_raw = raw
            self.focuser.set(OPT_FOCUS, raw)


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
