"""Arducam motorized zoom/focus lens over I2C (controller at 0x0C).

The lens is open-loop steppers: home against the mechanical stop at boot,
then track position in steps. Register map per Arducam's PTZ lens docs.
"""
from __future__ import annotations

try:
    from smbus2 import SMBus
except ImportError:  # dev machine
    SMBus = None

_ADDR = 0x0C
_REG_ZOOM = 0x00
_REG_FOCUS = 0x01
_REG_BUSY = 0x04

_ZOOM_STEPS = 4000  # full travel


class Lens:
    def __init__(self, bus: int = 1):
        self._bus = SMBus(bus) if SMBus else None
        self._zoom_steps = 0

    def home(self) -> None:
        self._write(_REG_ZOOM, -_ZOOM_STEPS)  # drive into the stop
        self._zoom_steps = 0

    def set_zoom_mm(self, efl_mm: float) -> None:
        from . import config
        efl_mm = max(config.ZOOM_MIN_MM, min(config.ZOOM_MAX_MM, efl_mm))
        frac = (efl_mm - config.ZOOM_MIN_MM) / (config.ZOOM_MAX_MM - config.ZOOM_MIN_MM)
        target = int(frac * _ZOOM_STEPS)
        if target != self._zoom_steps:
            self._write(_REG_ZOOM, target - self._zoom_steps)
            self._zoom_steps = target

    def _write(self, reg: int, steps: int) -> None:
        if not self._bus:
            return
        lo, hi = steps & 0xFF, (steps >> 8) & 0xFF
        self._bus.write_i2c_block_data(_ADDR, reg, [hi, lo])
