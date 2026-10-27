"""Three-anchor UWB ranging → bearing θ, elevation φ and distance d.

**The anchors are static.** A1 and A2 bolt to the enclosure wall either side
of the pan axis; A3 stands on a mast behind it, 250 mm up. θ is measured from
the *bar's normal* rather than from the lens axis, and φ from the plane of A1
and A2. The tracker turns both into absolute pan and tilt positions; see
docs/04.

θ needs only A1 and A2, so a frame without A3's range still yields a bearing,
and a two-anchor build (``UWB_ANCHORS = 2``) works exactly as before with
``elev_rad`` left as None.

Two radio stacks are supported, selected by `config.UWB_PROTOCOL`, because
they present ranges completely differently:

``ula1``
    Haorutech ULA1 (ESP32 + DWM1000) running the vendor's **RTLS_Tag** and
    **RTLS_Anchor** sketches — not the RangingTag/RangingAnchor pair, which
    completes a single tag-to-anchor exchange and reports only that distance.
    Under RTLS the tag polls each anchor in turn and broadcasts one RangeData
    frame holding every range; an anchor plugged into the Pi forwards that
    frame over USB serial:

        mc 0f 00000663 000005a3 00000512 000004cb 095f c1 0 a0:0
        │  │  └ RANGE0 └ RANGE1 └ RANGE2 └ RANGE3  │   │  │ └ role:tag:anchor
        │  └ mask of valid ranges                  │   │  └ debug
        └ fixed header                             │   └ sequence
                                                   └ frame counter

    Ranges are hexadecimal millimetres. **Every range arrives in one frame**,
    which is strictly better than the alternative below: r₁, r₂ and r₃ are
    then sampled within one ranging cycle, and both formulas assume that.

``dual-serial``
    One serial port per anchor, each running our own DS-TWR sketch and
    printing ``R,<tag_id>,<range_m>``. Kept because it needs no particular
    vendor, but the ranges come from independent streams and are only as
    simultaneous as their loops happen to be.
"""
from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import dataclass

import serial  # pyserial

from . import config


@dataclass
class Fix:
    theta_rad: float   # bearing from the anchor bar's normal (+ = subject to the right)
    dist_m: float
    age_s: float
    # elevation above the A1-A2 plane (+ = up); None without a usable A3 range
    elev_rad: float | None = None


class _KalmanAngle:
    """1-D constant-velocity Kalman filter on the bearing."""

    def __init__(self, baseline_m: float, q: float = 1.0):
        self.x = 0.0
        self.p = 1.0
        # process noise (rad²/s²) — subjects move. 1.0 rather than 4.0: on a
        # simulated subject crossing 5 m out at up to 1.8 m/s it cuts the
        # filtered error at 250 mm from ≈ 12° to ≈ 9° RMS, and the lag it adds
        # is less than the jitter it removes.
        self.q = q
        # measurement noise (rad²): σθ ≈ √2·σr / baseline, ≈ 20° raw at 0.4 m
        self.r = 2.0 * config.UWB_RANGE_SIGMA_M ** 2 / baseline_m ** 2
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


# "mc <mask> <r0> <r1> <r2> <r3> <nranges> <rseq> <debug> <role>"
_MC = re.compile(
    r"^mc\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s",
    re.IGNORECASE)


def parse_mc(line: str) -> tuple[float | None, ...] | None:
    """ULA1 RangeData frame → (r0_m, r1_m, r2_m, r3_m), None where the mask bit is clear.

    Returns None if the line is not a RangeData frame at all. RANGE0..2 are
    our A1..A3; RANGE3 is unused but parsed so the slots stay in step with
    the firmware's anchor numbering.
    """
    m = _MC.match(line.strip())
    if not m:
        return None
    mask = int(m.group(1), 16)
    out: list[float | None] = []
    for i in range(4):
        raw = int(m.group(2 + i), 16)
        out.append(raw / 1000.0 if (mask >> i) & 1 and raw else None)
    return tuple(out)


def solve_elevation(r1: float, r2: float, r3: float, b: float,
                    back: float, up: float) -> float | None:
    """Elevation of the tag above the A1-A2 plane, in radians.

    Frame: origin midway between A1 and A2, x along the bar, y forward along
    its normal, z up. A3 sits at (0, −back, up). Then, exactly,

        R² = (r₁² + r₂²)/2 − b²/4           squared distance from the origin
        x  = (r₁² − r₂²) / 2b
        r₃² = R² + 2·y·back + back² − 2·z·up + up²

    which is linear in z once y is known: z = α + β·y, with β = back/up.
    Together with y² + z² = R² − x² that is a line meeting a circle, so it
    solves exactly; of the two roots the larger y is the subject in front of
    the bar, the side the camera can see.

    Range noise can push the line just clear of the circle. That is clamped
    to the tangent point rather than rejected — it happens most on steep
    shots, which is exactly when the camera most needs an answer. Ranges
    inconsistent even with each other give None.
    """
    R2 = (r1 * r1 + r2 * r2) / 2.0 - b * b / 4.0
    if R2 <= 0.09:                       # inside 0.3 m: meaningless
        return None
    x = (r1 * r1 - r2 * r2) / (2.0 * b)
    rho2 = R2 - x * x                    # y² + z²
    if rho2 <= 0.0:
        return None
    alpha = (R2 + back * back + up * up - r3 * r3) / (2.0 * up)
    beta = back / up
    qa, qb, qc = 1.0 + beta * beta, 2.0 * alpha * beta, alpha * alpha - rho2
    disc = max(0.0, qb * qb - 4.0 * qa * qc)
    y = max(0.0, (-qb + math.sqrt(disc)) / (2.0 * qa))
    z = alpha + beta * y
    R = math.sqrt(R2)
    return math.asin(max(-1.0, min(1.0, z / R)))


class UwbArray:
    def __init__(self) -> None:
        self._ranges: list[float | None] = [None, None, None]
        self._stamp = 0.0
        self._kalman = _KalmanAngle(config.UWB_BASELINE_M)
        self._kalman_elev = _KalmanAngle(config.UWB_A3_UP_M)

    def start(self) -> None:
        # Daemon threads of their own, not the event loop's default executor:
        # the readers never return, and asyncio.run() waits for that
        # executor's threads on exit, so shutdown (the power switch) would
        # hang. They would also hold workers asyncio.to_thread() needs.
        if config.UWB_PROTOCOL == "ula1":
            readers = [(self._reader_ula1, (config.UWB_PORT,))]
        else:
            readers = [(self._reader_pair, (idx, port))
                       for idx, port in enumerate(config.UWB_PORTS[:config.UWB_ANCHORS])]
        for fn, args in readers:
            threading.Thread(target=fn, args=args, name="uwb-reader", daemon=True).start()

    # ---- readers ----------------------------------------------------------
    def _reader_ula1(self, port: str) -> None:
        """One port carries every range, already time-aligned."""
        while True:
            try:
                with serial.Serial(port, config.UWB_BAUD, timeout=1) as ser:
                    while True:
                        line = ser.readline().decode(errors="ignore")
                        got = parse_mc(line)
                        if got is None:
                            continue
                        r0, r1, r2, _ = got
                        if r0 is None or r1 is None:
                            continue        # no bearing without both of A1 and A2
                        # A3 may drop a cycle on its own (it is the one most
                        # likely to be body-shadowed); keep the bearing and
                        # simply report no elevation for that frame.
                        bias = config.RANGE_BIAS_M
                        self._ranges = [r0 - bias[0], r1 - bias[1],
                                        r2 - bias[2] if r2 is not None else None]
                        self._stamp = time.monotonic()
            except (serial.SerialException, ValueError):
                time.sleep(2.0)             # unplugged / booting — retry forever

    def _reader_pair(self, idx: int, port: str) -> None:
        """One port per anchor, our own sketch's ``R,<tag>,<range_m>`` lines."""
        while True:
            try:
                with serial.Serial(port, config.UWB_BAUD, timeout=1) as ser:
                    while True:
                        line = ser.readline().decode(errors="ignore").strip()
                        if line.startswith("R,"):
                            _, _tag, rng = line.split(",")
                            self._ranges[idx] = float(rng) - config.RANGE_BIAS_M[idx]
                            self._stamp = time.monotonic()
            except (serial.SerialException, ValueError):
                time.sleep(2.0)

    def frame_age(self) -> float:
        """Seconds since the last frame carrying A1 and A2 — is the tag on?"""
        return time.monotonic() - self._stamp if self._stamp else float("inf")

    # ---- fix --------------------------------------------------------------
    def fix(self) -> Fix | None:
        r1, r2, r3 = self._ranges
        if r1 is None or r2 is None:
            return None
        d = (r1 + r2) / 2.0
        if d < 0.3:
            return None
        b = config.UWB_BASELINE_M
        s = max(-1.0, min(1.0, (r1 * r1 - r2 * r2) / (2.0 * b * d)))
        theta = self._kalman.update(math.asin(s) * config.UWB_THETA_SIGN)
        elev = None
        if config.UWB_ANCHORS >= 3 and r3 is not None:
            raw = solve_elevation(r1, r2, r3, b, config.UWB_A3_BACK_M, config.UWB_A3_UP_M)
            if raw is not None:
                elev = self._kalman_elev.update(raw)
        return Fix(theta_rad=theta, dist_m=d, age_s=time.monotonic() - self._stamp,
                   elev_rad=elev)
