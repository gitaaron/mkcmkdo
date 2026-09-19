# 04 — Tracking system

## Why UWB (and not BLE, GPS, or vision alone)

| Option | Verdict |
| --- | --- |
| BLE RSSI | ±3–5 m error, multipath-hostile — unusable for aiming |
| GPS on wearable | 2–5 m error, outdoor-only, no bearing without a second GPS |
| Vision only | Works, but can't disambiguate *which* person, loses lock on occlusion/exit |
| **UWB two-way ranging** | **±10–30 cm range accuracy, ~20 Hz, cheap DW1000 modules, gives identity for free** |

We fuse both: UWB supplies identity, bearing, and distance; the camera supplies
fine centring and tilt.

## Geometry

![Tracking geometry](images/tracking-geometry.png)

Two anchors A1, A2 ride on the rotating head, 400 mm apart, symmetric about
the lens axis. Each performs asymmetric double-sided two-way ranging (DS-TWR)
with the tag, yielding ranges r₁ and r₂.

```
d  = (r₁ + r₂) / 2                     # distance to subject
θ  ≈ asin( (r₁² − r₂²) / (2·b·d) )     # bearing error from boresight
```

With b = 0.4 m and σ_range ≈ 10 cm, bearing noise σ_θ ≈ 20° raw — too noisy
per-sample, fine after filtering (we run a 1-D Kalman filter on θ and feed the
pan loop the filtered value; at 20 Hz the effective noise is ~3–4°, and the
camera's horizontal FOV at wide is ~65°, so the subject stays comfortably in
frame; CV centring does the rest).

Because the anchors rotate **with** the head, θ is directly the pan error —
no coordinate transforms, no absolute heading needed. The pan loop simply
drives θ → 0.

Front/back ambiguity (a two-anchor baseline can't tell +90° from +91° behind):
resolved by motion — if θ commands drive the error *up*, the controller flips
180°. In practice the CV check ("is there a person in frame?") settles it in
one step.

## Control loops (all run on the Pi, 20 Hz)

```
uwb θ ──► Kalman ──► PID(kp=2.2, ki=0.1, kd=0.15) ──► pan velocity (°/s)
                                                        └─► server ─► base ESP32 ─► TMC2209
d ─────► zoom setpoint: EFL = clamp(k_frame · d, lens_min, lens_max)
                       └─► lens I2C (rate-limited, deadband ±0.3 m)

person bbox (CV) ──► tilt PID ──► GPIO18 PWM  (and ±3° pan trim)
```

- **Pan**: velocity commands, not positions — the base ESP32 integrates them
  with the TMC2209 in StealthChop; slew limit 180°/s, accel 360°/s².
- **Zoom**: hold the subject at ~40 % of frame height. Deadband + 2 s
  rate-limit so zoom doesn't "breathe".
- **Tilt**: UWB gives no elevation (horizontal baseline), so tilt is CV-driven:
  the person-detector bounding-box centre feeds a PID on GPIO18. Detector =
  YOLOv8n (or MobileNet-SSD) on the Pi 5 at 10 Fps on the 720p preview stream;
  the record stream is untouched 1080p.
- **Lost tag**: > 5 s without ranges → hold position, LED flashes; > 30 s →
  drop to `idle` (recording is stopped/saved first).

## Camera placement envelope

How far back can the tripod sit? Three constraints, and they bite at
different distances:

1. **UWB tracking — distance-independent until the radio gives out.** Bearing
   error is σθ ≈ √2·σr / b (range noise over the 40 cm baseline), so it does
   not grow with distance: filtered bearing stays ~3–4° at 5 m or 30 m. The
   limit is the ranging link itself: in a multipath-heavy gym (steel,
   concrete) reliable 20 Hz DS-TWR holds to **~25–35 m**; outdoors with clear
   line of sight the same DW1000 modules reach 50 m+.
2. **Resolution — the 8–20 mm zoom is the binding constraint.** A 1.8 m
   subject's height on the 1080p (16:9) record stream is ≈
   `940 · f(mm) / d(m)` pixels:

   | Distance | Lens | Subject height in frame | Verdict |
   | --- | --- | --- | --- |
   | 7 m | 8 mm (widest) | ~1080 px (fills frame) | **minimum full-body distance** |
   | 10 m | 8–9 mm | ~750 px (70 %) | excellent |
   | 15–30 m | 7–14 mm (auto) | ~430 px (40 % target) | zoom loop holds framing |
   | 43 m | 20 mm (maxed) | ~430 px (40 %) | last distance at target framing |
   | 60 m | 20 mm | ~310 px (29 %) | usable, visibly wider shot |
   | 100 m | 20 mm | ~190 px (17 %) | subject small in frame; CV still locks |

   Framing degrades gracefully past ~43 m rather than failing — but indoors
   the UWB link gives out first.
3. **Geometry — closer isn't better.** Inside ~5 m of a tall wall the tilt
   angle gets steep (foreshortened footage) and pan/tilt angular rates spike
   on fast moves. At 8–12 m, a full 15 m route sweeps a comfortable ~50–60°
   of tilt.

**Rule of thumb: 8–12 m back is the sweet spot; anywhere from 7 m to ~30 m
indoors works with no quality cliff.** Below 7 m expect partial-body framing;
past ~30 m indoors expect UWB dropouts before you run out of pixels. At long
range, remember the head also needs Wi-Fi back to the server — past ~20 m,
put the AP (or the hotspot running the server) near the midpoint, not in a
back room.

## Calibration

1. **Anchor offset**: with the tag on the boresight 3 m away, record
   (r₁ − r₂); store as bias.
2. **Range bias**: tag at a taped 5.00 m; DW1000 antenna-delay constant tuned
   until reported range matches (one-time, per board).
3. **Zoom curve**: step the lens through its range, note EFL vs. step count
   (Arducam lens is open-loop steppers — home it against the mechanical stop
   at boot).

## Wearing the tag

UWB passes through fabric with essentially no loss — the pod can live **under
clothing, in a pocket, or inside a pouch**; no optical line of sight is
needed. What attenuates it is the human body (water), so placement is about
keeping the wearer's torso out of the tag→camera path most of the time, and
the printed pod (`cad/wearable_case.scad`) keeps a foam pad between the
ceramic antenna and skin — pressing the antenna directly against the body
detunes it more than any garment would.

General placement ranking: upper-arm band > back of cap/collar >
chest/back pocket; avoid the wrist (arm swing wobbles the bearing) and
anywhere below the waist.

### Indoor climbing (bouldering / top-rope / lead)

Climbing is actually a *favourable* case: the climber faces the wall, and the
camera sits back on the mat/floor area — so the climber's **back faces the
camera** for nearly the whole climb. Put the tag on the back and body
shadowing almost never happens:

| Discipline | Recommended spot | Why |
| --- | --- | --- |
| Top-rope / lead | **Rear of the harness waist belt, offset 5–10 cm off-spine** (thread the strap bars through the belt webbing, or clip beside the haul loop) | Stable, always camera-facing, clear of the belay loop and rope path, nothing between chest and wall |
| Bouldering | **Low back, offset off-spine, under the shirt** on an elastic waistband — or the upper-arm band if falls worry you | No harness available; off-spine placement keeps the pod away from the spine when flat-back landing on mats |
| Either | Chalk-bag belt as a quick-and-dirty mount | Works (chalk bags sit rear-centre), but bags get spun around and repositioned mid-session — bearing jitters when it dangles |

Climbing-specific notes:

- **Never front-of-torso**: it's compressed against the wall on slabs and
  mantles (impact + full body occlusion at once).
- **Off-spine, always**: a 45 g pod is harmless to land on with mats — except
  directly on the spine. 5–10 cm lateral offset removes the concern.
- **Overhangs**: body goes horizontal, so the tag may face the ceiling;
  ranges keep flowing (diffraction) and the CV tilt loop carries framing
  through the crux. Expect the noisiest bearing of the session here, not a
  loss of lock.
- **Camera placement in the gym**: 8–12 m back from the wall base (full
  envelope: 7–30 m — see [placement envelope](#camera-placement-envelope)).
  The tilt axis (−45°…+225°) covers ground-to-past-vertical, so even a
  top-out 15 m up at 7 m horizontal distance (~65° elevation) is comfortably
  in range. Gyms are
  multipath-rich (steel structure, concrete) — the Kalman filter settings in
  `device/sportcam/uwb.py` already assume σ ≈ 10 cm ranges; if bearing looks
  jumpy indoors, raise `r` (measurement noise) toward 0.2 before touching
  the PID gains.
- **Sweat and chalk**: the pod's USB-C slot faces down when worn; wipe the
  case, not the board. Chalk dust is non-conductive and harmless; sweat
  ingress is the reason the case has no top vents.

## Wearable behaviour

- Ranges as DS-TWR responder at 20 Hz; deep-sleeps between sessions
  (woken by any anchor poll).
- Button: short press = "hey camera, find me" (forces re-acquire); long
  press = start/stop recording remotely.
- LED: blinks green when ranging, orange when charging, red at < 15 % battery.
