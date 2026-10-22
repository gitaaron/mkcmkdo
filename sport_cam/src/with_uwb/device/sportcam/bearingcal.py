"""Measure `TAG_BEARING_SIGMA_DEG` and `TAG_BEARING_CORR_S` — the filtered
bearing's noise and how quickly it wanders.

    python -m sportcam.bearingcal 10        # wearer standing 10 m out on the boresight
    python -m sportcam.bearingcal 10 120    # ...sampled for 120 s instead of 60

The tag-wearer match (docs 05, "Telling the tag wearer from everyone else")
decides how long to average before trusting which of two people the tag is
on, from these two numbers. Both were estimated, not measured; this measures
them on your hardware.

Do `rangecal` first. Centre the pan axis (`python -m sportcam.ptzcheck`
leaves it centred), then have someone wear the tag as they will in use and
stand still on the boresight at the given distance, facing the camera. Their
body is part of the measurement: it shadows the antennas the same way it will
at the crag. Keep everyone else out of the line between them while it samples.

It reads the bearing exactly as the tracker does (through the same Kalman
filter, one fix per radio frame) and reports:

  mean    the bearing's offset from straight ahead. Over 3° means the wearer
          is off the boresight or the range bias is off; fix that first, as
          the match compares people against this bearing.
  σ       the RMS wander about that mean → TAG_BEARING_SIGMA_DEG
  τ       how long the wander takes to forget itself (its autocorrelation
          falling to 1/e) → TAG_BEARING_CORR_S

Run it at the distances you shoot from (5 m and 10 m, say) and paste the
larger σ and the longer τ: both errors make the match wait longer, never
pick the wrong person.
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

DEFAULT_S = 60.0
MIN_FRAMES = 200
MEAN_SANITY_DEG = 3.0


def bearing_stats(series: list[float], dt: float) -> tuple[float, float, float]:
    """(mean, σ, τ) of a bearing series in degrees sampled every `dt` s.

    τ is the lag at which the autocorrelation first falls to 1/e, linearly
    interpolated between samples; the series' length if it never does.
    """
    mean = statistics.fmean(series)
    dev = [x - mean for x in series]
    var = statistics.fmean(d * d for d in dev)
    sigma = math.sqrt(var)
    if var == 0.0:
        return mean, 0.0, 0.0
    n, target, prev = len(dev), 1.0 / math.e, 1.0
    for lag in range(1, n // 2):
        rho = sum(dev[i] * dev[i + lag] for i in range(n - lag)) / ((n - lag) * var)
        if rho <= target:
            frac = (prev - target) / (prev - rho) if prev != rho else 0.0
            return mean, sigma, (lag - 1 + frac) * dt
        prev = rho
    return mean, sigma, n * dt


def collect(seconds: float) -> tuple[list[float], float]:
    """Filtered bearings in degrees, one per fresh frame, and the mean frame interval."""
    arr = UwbArray()
    if config.UWB_PROTOCOL == "ula1":
        readers = [(arr._reader_ula1, (config.UWB_PORT,))]
    else:
        readers = [(arr._reader_pair, (i, p)) for i, p in enumerate(config.UWB_PORTS[:3])]
    for fn, args in readers:
        threading.Thread(target=fn, args=args, daemon=True).start()

    out: list[float] = []
    seen, start, first = 0.0, time.monotonic(), None
    settle = 3.0                      # let the filter forget its start at 0
    while time.monotonic() - start < seconds + settle:
        time.sleep(0.005)
        if arr._stamp == seen:
            continue
        seen = arr._stamp
        fix = arr.fix()
        if fix is None or time.monotonic() - start < settle:
            continue
        first = first or time.monotonic()
        out.append(math.degrees(fix.theta_rad))
        left = seconds + settle - (time.monotonic() - start)
        print(f"  {len(out):5d} frames, {left:4.0f} s left", end="\r", flush=True)
    print()
    span = time.monotonic() - first if first else 0.0
    return out, (span / max(1, len(out) - 1))


def main() -> None:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit(2)
    dist = float(sys.argv[1])
    seconds = float(sys.argv[2]) if len(sys.argv) == 3 else DEFAULT_S
    ports = [config.UWB_PORT] if config.UWB_PROTOCOL == "ula1" else list(config.UWB_PORTS[:3])
    missing = [p for p in ports if not os.path.exists(p)]
    if missing:
        print(f"No anchor on {', '.join(missing)} — is the data anchor plugged into the Pi?")
        sys.exit(1)

    print(f"Sampling the bearing for {seconds:.0f} s with the wearer {dist:g} m out "
          "on the boresight. Stand still…")
    series, dt = collect(seconds)
    if len(series) < MIN_FRAMES:
        print(f"Only {len(series)} frames in {seconds:.0f} s. Check the anchors are on the "
              "RTLS firmware and the mask reads 07 (docs/10, row 7).")
        sys.exit(1)

    mean, sigma, tau = bearing_stats(series, dt)
    print(f"\n{len(series)} frames, one every {dt * 1000:.0f} ms\n")
    print("            measured   config.py")
    print(f"  mean      {mean:+6.1f}°")
    print(f"  σ         {sigma:6.1f}°    {config.TAG_BEARING_SIGMA_DEG:5.1f}°  TAG_BEARING_SIGMA_DEG")
    print(f"  τ         {tau:6.2f} s   {config.TAG_BEARING_CORR_S:5.2f} s  TAG_BEARING_CORR_S")

    if abs(mean) > MEAN_SANITY_DEG:
        print(f"\nThe bearing sits {mean:+.1f}° off straight ahead. Check the wearer is on the "
              "boresight, the pan axis is centred and rangecal has been run, then measure "
              "again: the match compares people with this bearing.")
    if sigma < config.TAG_BEARING_SIGMA_DEG and tau < config.TAG_BEARING_CORR_S:
        print("\nBoth are within what config.py assumes; the match is if anything "
              "cautious. Lowering them makes it decide sooner.")
    else:
        print("\nAbove what config.py assumes: the match may decide on too little "
              "evidence beside someone standing close. Raise them.")

    print("\nPaste into config.py (the larger σ and longer τ if you measured at several distances):\n")
    stamp = f"bearingcal at {dist:g} m, {time.strftime('%Y-%m-%d')}"
    print(f"TAG_BEARING_SIGMA_DEG = {sigma:.1f}    # {stamp}")
    print(f"TAG_BEARING_CORR_S = {tau:.2f}      # {stamp}")


if __name__ == "__main__":
    main()
