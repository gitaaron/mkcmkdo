"""270° tilt servo on GPIO18 via pigpio hardware PWM."""
from __future__ import annotations

try:
    import pigpio
except ImportError:  # dev machine
    pigpio = None

from . import config


class Tilt:
    def __init__(self) -> None:
        self._pi = pigpio.pi() if pigpio else None
        self._deg = 0.0

    @property
    def degrees(self) -> float:
        return self._deg

    def set(self, deg: float) -> None:
        deg = max(config.TILT_MIN_DEG, min(config.TILT_MAX_DEG, deg))
        self._deg = deg
        span = config.TILT_MAX_DEG - config.TILT_MIN_DEG
        us = config.TILT_US_AT_MIN + (deg - config.TILT_MIN_DEG) / span * (
            config.TILT_US_AT_MAX - config.TILT_US_AT_MIN
        )
        if self._pi:
            self._pi.set_servo_pulsewidth(config.TILT_GPIO, int(us))

    def nudge(self, delta_deg: float) -> None:
        self.set(self._deg + delta_deg)

    def park(self) -> None:
        self.set(0.0)
        if self._pi:
            self._pi.set_servo_pulsewidth(config.TILT_GPIO, 0)  # relax
