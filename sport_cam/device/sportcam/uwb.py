"""Two-anchor UWB ranging → (bearing error θ, distance d).

Each anchor is a Makerfabs-style ESP32+DW1000 running the anchor sketch,
printing one line per completed DS-TWR exchange:  ``R,<tag_id>,<range_m>\n``
"""
from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass

import serial  # pyserial

from . import config


@dataclass
class Fix:
    theta_rad: float   # bearing error from boresight (+ = subject to the right)
    dist_m: float
    age_s: float


class _KalmanAngle:
    """1-D constant-velocity Kalman filter on the bearing."""

    def __init__(self, q: float = 4.0, r: float = 0.12):
        self.x = 0.0
        self.p = 1.0
        self.q = q      # process noise (rad²/s²) — subjects move
        self.r = r      # measurement noise (rad²) — σθ ≈ 20° raw
        self.t = time.monotonic()

    def update(self, z: float) -> float:
        now = time.monotonic()
        dt = min(now - self.t, 0.5)
        self.t = now
        self.p += self.q * dt * dt
        k = self.p / (self.p + self.r)
        self.x += k * (z - self.x)
        self.p *= 1.0 - k
        return self.x


class UwbArray:
    def __init__(self) -> None:
        self._ranges: list[float | None] = [None, None]
        self._stamp = 0.0
        self._kalman = _KalmanAngle()

    def start(self) -> None:
        for idx, port in enumerate(config.UWB_PORTS):
            asyncio.get_event_loop().run_in_executor(None, self._reader, idx, port)

    def _reader(self, idx: int, port: str) -> None:
        while True:
            try:
                with serial.Serial(port, 115200, timeout=1) as ser:
                    while True:
                        line = ser.readline().decode(errors="ignore").strip()
                        if line.startswith("R,"):
                            _, _tag, rng = line.split(",")
                            self._ranges[idx] = float(rng) - config.RANGE_BIAS_M[idx]
                            self._stamp = time.monotonic()
            except (serial.SerialException, ValueError):
                time.sleep(2.0)  # unplugged / booting — retry forever

    def fix(self) -> Fix | None:
        r1, r2 = self._ranges
        if r1 is None or r2 is None:
            return None
        d = (r1 + r2) / 2.0
        if d < 0.3:
            return None
        b = config.UWB_BASELINE_M
        s = max(-1.0, min(1.0, (r1 * r1 - r2 * r2) / (2.0 * b * d)))
        theta = self._kalman.update(math.asin(s))
        return Fix(theta_rad=theta, dist_m=d, age_s=time.monotonic() - self._stamp)
