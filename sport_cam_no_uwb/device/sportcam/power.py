"""Battery monitoring — a current/voltage sensor on the pack side of the buck.

SportCam runs off a USB-C PD power bank, so there is no gauge to interrogate:
a bank reports nothing about its own charge over the PD trigger. Instead we
measure what we draw and integrate it.

The sensor sits on the **12 V** side, between the PD trigger board and the
buck, so it sees true pack power including conversion losses.

Two parts are supported, chosen by `config.POWER_MONITOR`, because the INA226
module is hard to source in some markets (docs/07):

  * **ina226** — external shunt. Bus and shunt voltage are read directly
    rather than through the calibration register, which keeps the maths
    obvious and independent of the shunt fitted:
    ``I = V_shunt / R_shunt`` with a 2.5 µV LSB, ``V = bus × 1.25 mV``.
  * **ina260** — shunt integrated on the die, so there is nothing to
    calibrate and nothing to get wrong: ``I = current × 1.25 mA``,
    ``V = bus × 1.25 mV``. Same I2C address, so only the register map and
    the scaling differ. This is the easier part to buy and the easier part
    to wire; prefer it unless you already own an INA226.

Set `POWER_MONITOR = "none"` to build without a gauge. Everything still runs;
you lose the low-battery warning and the automatic save-and-park, so you are
watching the clock yourself.

Charge is tracked in watt-hours consumed since the gauge was last reset.
Because that assumes a full pack at reset, `reset()` is exposed as a callable
so the app can zero it when a fresh bank is clipped on.
"""
from __future__ import annotations

import asyncio
import time

try:
    from smbus2 import SMBus
except ImportError:          # dev machine
    SMBus = None

from . import config

_REG_CONFIG = 0x00
_REG_SHUNT = 0x01          # INA226: shunt voltage. INA260: current.
_REG_BUS = 0x02

_SHUNT_LSB_V = 2.5e-6      # INA226 shunt-voltage LSB
_CURRENT_LSB_A = 1.25e-3   # INA260 current LSB
_BUS_LSB_V = 1.25e-3       # both parts

# 16 averages, 1.1 ms conversions, continuous. The two parts differ only in
# the fixed bits at [14:12], which identify the device family.
_CONFIG = {"ina226": 0x4527, "ina260": 0x6527}


class PowerMonitor:
    def __init__(self, bus: int = None) -> None:
        self._bus = None
        self.part = (config.POWER_MONITOR or "none").lower()
        if SMBus is not None and self.part in _CONFIG:
            try:
                self._bus = SMBus(config.I2C_BUS if bus is None else bus)
                cfg = _CONFIG[self.part]
                self._bus.write_i2c_block_data(
                    config.POWER_MONITOR_ADDR, _REG_CONFIG,
                    [(cfg >> 8) & 0xFF, cfg & 0xFF])
            except OSError as exc:
                print(f"[power] {self.part} not found ({exc}) — running without a gauge")
                self._bus = None
        elif self.part not in _CONFIG:
            print("[power] no gauge configured — no low-battery warning or auto-save")

        self.volts = 0.0
        self.amps = 0.0
        self.watts = 0.0
        self.wh_used = 0.0
        self._avg_watts = 0.0
        self._t = time.monotonic()

    @property
    def available(self) -> bool:
        return self._bus is not None

    def reset(self) -> None:
        """Zero the fuel gauge — call when a freshly charged bank goes on."""
        self.wh_used = 0.0

    # ---- derived ----------------------------------------------------------
    @property
    def fraction_left(self) -> float | None:
        if not self.available or not config.BATTERY_WH:
            return None
        return max(0.0, min(1.0, 1.0 - self.wh_used / config.BATTERY_WH))

    @property
    def minutes_left(self) -> float | None:
        frac = self.fraction_left
        if frac is None or self._avg_watts < 0.5:
            return None
        return (config.BATTERY_WH * frac) / self._avg_watts * 60.0

    def level(self) -> str:
        """`ok`, `low` or `critical` — drives the LED ring and auto-shutdown."""
        frac = self.fraction_left
        if frac is None:
            return "ok"
        if frac <= config.BATTERY_CRITICAL_FRAC:
            return "critical"
        if frac <= config.BATTERY_LOW_FRAC:
            return "low"
        return "ok"

    def telemetry(self) -> dict:
        return {
            "battery": round(self.fraction_left, 3) if self.fraction_left is not None else None,
            "batteryWatts": round(self.watts, 1),
            "batteryMinutes": round(self.minutes_left) if self.minutes_left else None,
            "batteryLevel": self.level(),
        }

    # ---- sampling ---------------------------------------------------------
    def sample(self) -> None:
        if not self._bus:
            return
        try:
            addr = config.POWER_MONITOR_ADDR
            self.volts = _u16(self._bus.read_i2c_block_data(
                addr, _REG_BUS, 2)) * _BUS_LSB_V
            raw = _s16(self._bus.read_i2c_block_data(addr, _REG_SHUNT, 2))
        except OSError:
            return
        if self.part == "ina260":
            self.amps = raw * _CURRENT_LSB_A          # shunt is on the die
        else:
            self.amps = raw * _SHUNT_LSB_V / config.INA226_SHUNT_OHMS
        self.watts = max(0.0, self.volts * self.amps)

        now = time.monotonic()
        dt, self._t = now - self._t, now
        self.wh_used += self.watts * dt / 3600.0
        # 60 s time constant, so the runtime estimate doesn't jump on a servo move
        alpha = min(1.0, dt / 60.0)
        self._avg_watts += alpha * (self.watts - self._avg_watts)

    async def run(self) -> None:
        while True:
            self.sample()
            await asyncio.sleep(1.0)


def _u16(b: list[int]) -> int:
    return (b[0] << 8) | b[1]


def _s16(b: list[int]) -> int:
    v = _u16(b)
    return v - 0x10000 if v & 0x8000 else v
