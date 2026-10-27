"""Range parsing, bearing and elevation geometry, with no radio attached.

The ULA1 frame is the one worth testing: ranges arrive as hexadecimal
millimetres behind a validity mask, and misreading either would produce a
bearing that looks plausible and points the camera at nothing.

    python3 device/tests/test_uwb.py
"""
from __future__ import annotations

import math
import random
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config
from sportcam.bearingcal import bearing_stats
from sportcam.rangecal import biases as rangecal_biases, expected_ranges
from sportcam import uwb as uwb_mod
from sportcam.uwb import UwbArray, _KalmanAngle, parse_mc, parse_mc_tag, solve_elevation

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def main() -> None:
    print("uwb checks\n")

    # ---- 1. the frame from the ULA1 manual --------------------------------
    line = "mc 0f 00000663 000005a3 00000512 000004cb 095f c1 0 a0:0"
    got = parse_mc(line)
    check("manual's example frame parses", got is not None)
    r0, r1, r2, r3 = got
    # 0x663 = 1635 mm, the manual states 1.635 m
    check("RANGE0 is hex millimetres", abs(r0 - 1.635) < 1e-6, f"{r0}")
    check("RANGE1 is hex millimetres", abs(r1 - 1.443) < 1e-6, f"{r1}")
    check("RANGE2 (A3) is hex millimetres", abs(r2 - 1.298) < 1e-6, f"{r2}")
    check("RANGE3 is parsed too", abs(r3 - 1.227) < 1e-6, f"{r3}")

    # ---- 2. the validity mask is honoured ---------------------------------
    check("mask 0x02 hides range 0", parse_mc("mc 02 00000663 000005a3 0 0 1 1 0 a0:0")[:2] == (None, 1.443))
    check("mask 0x01 hides range 1", parse_mc("mc 01 00000663 000005a3 0 0 1 1 0 a0:0")[:2] == (1.635, None))
    check("mask 0x00 hides all", parse_mc("mc 00 00000663 000005a3 00000512 0 1 1 0 a0:0") == (None,) * 4)
    check("mask 0x03 hides A3 only",
          parse_mc("mc 03 00000663 000005a3 00000512 0 1 1 0 a0:0") == (1.635, 1.443, None, None))
    check("a zero range is treated as absent",
          parse_mc("mc 0f 00000000 000005a3 0 0 1 1 0 a0:0")[:2] == (None, 1.443))

    # ---- 3. junk is rejected rather than guessed --------------------------
    for junk in ("", "garbage", "R,1,4.2", "mc", "mcx 0f 1 2 3 4 5 6 7 a0:0"):
        check(f"rejects {junk!r}", parse_mc(junk) is None)
    check("uppercase hex still parses", parse_mc("MC 0F 00000663 000005A3 0 0 1 1 0 a0:0") is not None)

    # ---- 4. bearing geometry ----------------------------------------------
    arr = UwbArray()
    config.RANGE_BIAS_M = (0.0, 0.0, 0.0)

    arr._ranges, arr._stamp = [10.0, 10.0, None], 1e9
    arr._kalman.p = 1e6                       # let the filter trust one sample
    f = arr.fix()
    check("equal ranges → straight ahead", abs(math.degrees(f.theta_rad)) < 0.5,
          f"{math.degrees(f.theta_rad):.2f} deg")
    check("distance is the mean of the two", abs(f.dist_m - 10.0) < 1e-6)

    arr2 = UwbArray(); arr2._kalman.p = 1e6
    arr2._ranges, arr2._stamp = [10.2, 9.8, None], 1e9
    right = arr2.fix()
    check("nearer the second anchor → one sign",
          math.degrees(right.theta_rad) != 0, f"{math.degrees(right.theta_rad):.1f}")

    arr3 = UwbArray(); arr3._kalman.p = 1e6
    arr3._ranges, arr3._stamp = [9.8, 10.2, None], 1e9
    left = arr3.fix()
    check("swapping the ranges mirrors the bearing",
          abs(math.degrees(left.theta_rad) + math.degrees(right.theta_rad)) < 0.5,
          f"{math.degrees(left.theta_rad):.1f} vs {math.degrees(right.theta_rad):.1f}")

    # a 0.25 m baseline cannot resolve more than asin(1); the formula clamps
    arr4 = UwbArray(); arr4._kalman.p = 1e6
    arr4._ranges, arr4._stamp = [12.0, 2.0, None], 1e9
    check("an impossible pair clamps instead of raising",
          abs(math.degrees(arr4.fix().theta_rad)) <= 90.0 + 1e-6)

    arr5 = UwbArray()
    arr5._ranges = [None, 10.0, 10.0]
    check("one missing range → no fix", arr5.fix() is None)
    arr6 = UwbArray(); arr6._ranges = [0.1, 0.1, 0.5]
    check("a subject on top of the camera → no fix", arr6.fix() is None)

    # ---- 5. elevation from the third anchor -------------------------------
    b, back, up = config.UWB_BASELINE_M, config.UWB_A3_BACK_M, config.UWB_A3_UP_M
    anchors = [(-b / 2, 0.0, 0.0), (b / 2, 0.0, 0.0), (0.0, -back, up)]

    def ranges_to(az_deg: float, el_deg: float, dist: float) -> list[float]:
        az, el = math.radians(az_deg), math.radians(el_deg)
        p = (dist * math.cos(el) * math.sin(az), dist * math.cos(el) * math.cos(az),
             dist * math.sin(el))
        return [math.dist(p, a) for a in anchors]

    # A3's backward offset is exactly the case a naive formula gets wrong,
    # and steep shots are where it matters: check across the whole envelope.
    # Three anchors cannot tell a point from its mirror in the plane through
    # them, which leans back atan(back/up) from vertical. A subject on the
    # far side of that plane — well below the camera *and* far to one side —
    # resolves to the mirror. Exact everywhere in front of it; in the corner
    # behind it the solver must return exactly the mirror image's elevation.
    # How far that is from the truth depends on the geometry (pan ±80°, 45°
    # down: ≈ 6.3° with A3 89 mm back and 250 mm up), so the check is against
    # the mirror, not a fixed bound.
    norm = math.hypot(up, back)
    normal = (0.0, -up / norm, -back / norm)   # the anchor plane passes through the origin

    def mirror_elevation(p: tuple[float, float, float]) -> float:
        k = 2 * sum(pi * ni for pi, ni in zip(p, normal))
        q = [pi - k * ni for pi, ni in zip(p, normal)]
        return math.degrees(math.asin(q[2] / math.dist(q, (0.0, 0.0, 0.0))))

    worst = worst_mirror = worst_corner = 0.0
    for az in (-80, -75, -30, 0, 30, 75, 80):
        for el in (-45, -40, -10, 0, 20, 45, 65, 80):
            for dist in (2.0, 8.0, 25.0):
                got = math.degrees(solve_elevation(*ranges_to(az, el, dist), b, back, up))
                a, e = math.radians(az), math.radians(el)
                in_front = math.cos(e) * math.cos(a) * up + math.sin(e) * back > 0
                if in_front:
                    worst = max(worst, abs(got - el))
                else:
                    p = (dist * math.cos(e) * math.sin(a), dist * math.cos(e) * math.cos(a),
                         dist * math.sin(e))
                    worst_mirror = max(worst_mirror, abs(got - mirror_elevation(p)))
                    worst_corner = max(worst_corner, abs(got - el))
    check("elevation exact in front of the anchor plane (noise-free)", worst < 0.01,
          f"worst error {worst:.3f} deg")
    check("mirrored corner resolves to the mirror image exactly", worst_mirror < 0.01,
          f"worst error {worst_mirror:.3f} deg (true error there: {worst_corner:.1f} deg)")

    r1, r2, r3 = ranges_to(0, 30, 10)
    check("tag above the bar → positive elevation",
          solve_elevation(r1, r2, r3, b, back, up) > 0)
    r1, r2, r3 = ranges_to(0, -20, 10)
    check("tag below the bar → negative elevation",
          solve_elevation(r1, r2, r3, b, back, up) < 0)

    # noisy ranges can leave no exact solution; that clamps, it does not raise
    r1, r2, r3 = ranges_to(0, 80, 6)
    noisy = solve_elevation(r1, r2, r3 - 0.3, b, back, up)
    check("inconsistent A3 range clamps instead of raising",
          noisy is not None and -90.0 <= math.degrees(noisy) <= 90.0,
          f"{noisy}")

    arr7 = UwbArray(); arr7._kalman_elev.p = 1e6
    arr7._ranges, arr7._stamp = ranges_to(10, 35, 9), 1e9
    f7 = arr7.fix()
    check("fix carries filtered elevation",
          f7.elev_rad is not None and abs(math.degrees(f7.elev_rad) - 35) < 1.0,
          f"{f7.elev_rad}")

    arr8 = UwbArray()
    r1, r2, _ = ranges_to(10, 35, 9)
    arr8._ranges, arr8._stamp = [r1, r2, None], 1e9
    f8 = arr8.fix()
    check("A3 missing → bearing still reported", f8 is not None)
    check("A3 missing → no elevation", f8.elev_rad is None)

    config.UWB_ANCHORS = 2
    arr9 = UwbArray()
    arr9._ranges, arr9._stamp = ranges_to(10, 35, 9), 1e9
    check("two-anchor build ignores A3", arr9.fix().elev_rad is None)
    config.UWB_ANCHORS = 3

    # ---- 6. range-bias calibration (rangecal) -----------------------------
    # The geometry rangecal assumes must be the one the solver uses: a tag
    # on the boresight, level with A1/A2, is at 0° bearing and 0° elevation.
    truth = expected_ranges(5.0, b, back, up)
    check("rangecal's true ranges match the solver's geometry",
          all(abs(t - r) < 1e-9 for t, r in zip(truth, ranges_to(0, 0, 5.0))))

    rnd = random.Random(7)
    planted = (0.04, -0.03, 0.07)
    samples = [tuple(t + p + rnd.gauss(0, 0.10) for t, p in zip(truth, planted))
               for _ in range(300)]
    got, spread = rangecal_biases(samples, 5.0, b, back, up)
    check("rangecal recovers each anchor's bias within 2 cm",
          all(abs(g - p) < 0.02 for g, p in zip(got, planted)), f"{got}")
    check("rangecal reports the noise", all(0.08 < s < 0.12 for s in spread), f"{spread}")

    # Why it matters: A3's 7 cm alone throws a level tag's elevation well
    # off at this mast height, and subtracting the measured bias undoes it.
    r_b = [t + p for t, p in zip(ranges_to(0, 0, 10.0), planted)]
    off = math.degrees(solve_elevation(*r_b, b, back, up))
    fixed = math.degrees(solve_elevation(*[r - g for r, g in zip(r_b, got)], b, back, up))
    check("uncorrected bias skews elevation by degrees", abs(off) > 5.0, f"{off:.1f}")
    check("corrected, a level tag reads level", abs(fixed) < 3.0, f"{fixed:.1f}")

    # ---- 7. bearing noise (bearingcal) -------------------------------------
    # It must recover a known wander: σ 7°, τ 0.35 s, sampled at 20 Hz.
    dt, tau, sigma = 0.05, 0.35, 7.0
    k = math.exp(-dt / tau)
    rnd, e, series = random.Random(3), 0.0, []
    for _ in range(4000):
        e = k * e + sigma * math.sqrt(1 - k * k) * rnd.gauss(0, 1)
        series.append(2.0 + e)
    m, s_got, t_got = bearing_stats(series, dt)
    check("bearingcal recovers the mean, σ and τ",
          abs(m - 2.0) < 1.0 and abs(s_got - sigma) < 1.0 and abs(t_got - tau) < 0.1,
          f"{m:.1f} {s_got:.1f} {t_got:.2f}")

    # And config.py's assumed values must match what the Kalman filter does to
    # the raw bearing noise at this baseline, for a tag standing still.
    clock = [0.0]
    real = uwb_mod.time.monotonic
    uwb_mod.time.monotonic = lambda: clock[0]
    try:
        kf = _KalmanAngle(b)
        raw = math.sqrt(2.0) * config.UWB_RANGE_SIGMA_M / b
        out = []
        for _ in range(6000):
            clock[0] += 1.0 / config.UWB_RATE_HZ
            out.append(math.degrees(kf.update(rnd.gauss(0, raw))))
    finally:
        uwb_mod.time.monotonic = real
    _, s_kf, t_kf = bearing_stats(out[200:], 1.0 / config.UWB_RATE_HZ)
    check("the filtered bearing's σ is within TAG_BEARING_SIGMA_DEG",
          s_kf <= config.TAG_BEARING_SIGMA_DEG, f"{s_kf:.1f}°")
    check("…and its τ is close to TAG_BEARING_CORR_S",
          abs(t_kf - config.TAG_BEARING_CORR_S) < 0.1, f"{t_kf:.2f} s")

    print("\nseveral tags")
    check("a frame names its tag", parse_mc_tag("mc 0f 00000663 000005a3 00000512 000004cb 095f c1 0 a3:0") == 3)
    check("…tag 0 when the field is missing", parse_mc_tag("mc 0f 00000663 000005a3 0 0 1 1 0") == 0)
    arr = UwbArray()
    arr._store(2, [5.0, 5.0, None])
    arr._store(5, [3.0, 3.0, None])
    check("each tag's ranges are kept apart", sorted(arr.tag_ages()) == [2, 5])
    check("following none: whichever tag ranged last", abs(arr.fix().dist_m - 3.0) < 1e-9)
    arr.follow(2)
    check("following a tag: only its ranges", abs(arr.fix().dist_m - 5.0) < 1e-9)
    arr._store(5, [1.0, 1.0, None])
    check("…another tag ranging changes nothing", abs(arr.fix().dist_m - 5.0) < 1e-9 and arr.following == 2)
    arr.follow(7)
    check("following a tag never heard: no fix, never on", arr.fix() is None and arr.frame_age() == float("inf"))

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all uwb checks passed")


if __name__ == "__main__":
    main()
