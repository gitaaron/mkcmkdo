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

## Calibration

1. **Anchor offset**: with the tag on the boresight 3 m away, record
   (r₁ − r₂); store as bias.
2. **Range bias**: tag at a taped 5.00 m; DW1000 antenna-delay constant tuned
   until reported range matches (one-time, per board).
3. **Zoom curve**: step the lens through its range, note EFL vs. step count
   (Arducam lens is open-loop steppers — home it against the mechanical stop
   at boot).

## Wearable behaviour

- Ranges as DS-TWR responder at 20 Hz; deep-sleeps between sessions
  (woken by any anchor poll).
- Button: short press = "hey camera, find me" (forces re-acquire); long
  press = start/stop recording remotely.
- LED: blinks green when ranging, orange when charging, red at < 15 % battery.
