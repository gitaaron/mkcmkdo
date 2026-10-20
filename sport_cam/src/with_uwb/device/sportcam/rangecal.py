"""Measure `config.RANGE_BIAS_M` — each anchor's constant range error.

    python -m sportcam.rangecal 5.0        # tag taped 5.00 m out on the boresight

Centre the pan axis (`python -m sportcam.ptzcheck` leaves it centred), then
put the tag on the lens's boresight at the given distance from the pan axis,
held at the height of the A1/A2 boards, antenna facing the camera. Tape the
distance; a 2 cm taping error is a 2 cm bias in every anchor. Keep people and
metal out of the line between them while it samples.

With the tag there, every true range follows from the geometry in config.py:
A1 and A2 are each hypot(d, b/2) away, A3 hypot(d + back, up). Each anchor's
bias is its median reading minus that. It also reports the spread of each
anchor's readings, which is the σ that `UWB_RANGE_SIGMA_M` should hold.

Tune each board's DW1000 antenna delay first if your firmware exposes it
(docs/04, calibration 2); this takes the residual. With the short 250 mm mast,
A3's bias matters most: 5 cm of it is about 11° of elevation.
"""
from __future__ import annotations

import math
import os
import statistics
import sys
import threading
import time

from . import config
from .uwb import UwbArray

SAMPLES = 300
TIMEOUT_S = 60.0
BIAS_SANITY_M = 0.30


def expected_ranges(dist_m: float, b: float, back: float, up: float) -> tuple[float, float, float]:
    """True A1, A2, A3 ranges to a tag on the boresight, level with A1/A2."""
    side = math.hypot(dist_m, b / 2.0)
    return side, side, math.hypot(dist_m + back, up)


def biases(samples: list[tuple[float, float, float]], dist_m: float, b: float,
           back: float, up: float) -> tuple[list[float], list[float]]:
    """Per-anchor (median − true range) and standard deviation, in metres."""
    truth = expected_ranges(dist_m, b, back, up)
    cols = list(zip(*samples))
    bias = [statistics.median(c) - t for c, t in zip(cols, truth)]
    spread = [statistics.pstdev(c) for c in cols]
    return bias, spread


def collect(n: int) -> list[tuple[float, float, float]]:
    """Raw (uncorrected) A1, A2, A3 ranges, one tuple per fresh frame."""
    config.RANGE_BIAS_M = (0.0, 0.0, 0.0)         # we are measuring it
    arr = UwbArray()
    if config.UWB_PROTOCOL == "ula1":
        readers = [(arr._reader_ula1, (config.UWB_PORT,))]
    else:
        readers = [(arr._reader_pair, (i, p)) for i, p in enumerate(config.UWB_PORTS[:3])]
    for fn, args in readers:
        threading.Thread(target=fn, args=args, daemon=True).start()

    out: list[tuple[float, float, float]] = []
    seen, start = 0.0, time.monotonic()
    while len(out) < n and time.monotonic() - start < TIMEOUT_S:
        time.sleep(0.005)
        if arr._stamp == seen:
            continue
        seen = arr._stamp
        r1, r2, r3 = arr._ranges
        if None not in (r1, r2, r3):
            out.append((r1, r2, r3))
            print(f"  {len(out):4d}/{n}", end="\r", flush=True)
    print()
    return out


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    dist = float(sys.argv[1])
    b, back, up = config.UWB_BASELINE_M, config.UWB_A3_BACK_M, config.UWB_A3_UP_M
    ports = [config.UWB_PORT] if config.UWB_PROTOCOL == "ula1" else list(config.UWB_PORTS[:3])
    missing = [p for p in ports if not os.path.exists(p)]
    if missing:
        print(f"No anchor on {', '.join(missing)} — is the data anchor plugged into the Pi?")
        sys.exit(1)

    print(f"Sampling {SAMPLES} frames with the tag {dist:.2f} m out on the boresight…")
    samples = collect(SAMPLES)
    if len(samples) < SAMPLES // 3:
        print(f"Only {len(samples)} frames with all three ranges in {TIMEOUT_S:.0f} s. "
              "Check the anchors are on the RTLS firmware and the mask reads 07 (docs/10, row 7).")
        sys.exit(1)

    bias, spread = biases(samples, dist, b, back, up)
    truth = expected_ranges(dist, b, back, up)
    print(f"\n{len(samples)} frames\n")
    print("  anchor   true      median    bias      σ")
    for name, t, bi, sd in zip(("A1", "A2", "A3"), truth, bias, spread):
        print(f"  {name}      {t:6.3f} m  {t + bi:6.3f} m  {bi * 100:+5.1f} cm  {sd * 100:4.1f} cm")

    if any(abs(x) > BIAS_SANITY_M for x in bias):
        print(f"\nA bias over {BIAS_SANITY_M * 100:.0f} cm is a setup error, not a calibration: "
              "check the taped distance, that the tag is on the boresight, and that the "
              "anchor order (A1, A2, A3) matches the boards.")
    if max(spread) > 1.5 * config.UWB_RANGE_SIGMA_M:
        print(f"\nNoise is above the {config.UWB_RANGE_SIGMA_M * 100:.0f} cm the filters assume. "
              "Look for metal near an antenna or a body in the path; if it is real, raise "
              "UWB_RANGE_SIGMA_M to match.")

    print("\nPaste into config.py:\n")
    print("RANGE_BIAS_M = (" + ", ".join(f"{x:.3f}" for x in bias) + ")   # rangecal "
          f"at {dist:g} m, {time.strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    main()
