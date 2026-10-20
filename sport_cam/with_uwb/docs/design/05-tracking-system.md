# 05 — Tracking system

## Why UWB (and not BLE, GPS, or vision alone)

| Option | Verdict |
| --- | --- |
| BLE RSSI | ±3–5 m error, multipath-hostile — unusable for aiming |
| GPS on wearable | 2–5 m error, outdoor-only, no bearing without a second GPS |
| Vision only | Works, but can't disambiguate *which* person, loses lock on occlusion/exit |
| **UWB two-way ranging** | **±10–30 cm range accuracy, ~20 Hz, cheap DW1000 modules, gives identity for free** |

We fuse both: UWB supplies identity, bearing, elevation and distance; the
camera trims the residual error in both angles, frames the shot, and
verifies lock-on before a tag-started session records.

## Geometry

![Tracking geometry](../images/tracking-geometry.png)

Two anchors A1, A2 sit on arms bolted to the enclosure, 250 mm apart,
symmetric about the camera's pan axis. A third, A3, stands on a mast directly
behind the lens, **250 mm above them** and about 89 mm back. Both spacings are a
deliberate compromise: the head has to fit a cramped room
(see [constraints](../../../docs/product/01-requirements.md#non-functional-requirements-with-uwb)), and angle noise grows
as the spacing shrinks. All three are
**static** — they do not move with the lens. The tag performs two-way ranging
against each in turn and broadcasts one frame carrying every result, yielding
ranges r₁, r₂ and r₃.

That the ranges share a timestamp matters more than it looks. The formulas
below treat them as simultaneous; sampling them from independent radios a
few tens of milliseconds apart puts the subject's own motion straight into
the angles. One frame removes that error term.

```
d  = (r₁ + r₂) / 2                     # distance to subject
θ  ≈ asin( (r₁² − r₂²) / (2·b·d) )     # bearing from the anchor bar's normal
```

With b = 0.25 m and σ_range ≈ 10 cm, bearing noise σ_θ ≈ √2·σ_range / b ≈ 32°
raw — too noisy per sample, workable after filtering. A 1-D Kalman filter on θ
feeds the pan loop; its measurement noise is computed from the baseline
(`UWB_RANGE_SIGMA_M`), so it smooths harder when the baseline shrinks. On a
simulated subject crossing 5 m out at up to 1.8 m/s the filtered error is
**≈ 9° RMS** (≈ 7° at the old 400 mm). The camera's horizontal FOV at wide is
96°, so the subject stays in frame; CV centring trims the rest.

| Baseline | Raw σ_θ | Filtered, moving subject | Head width |
| --- | --- | --- | --- |
| 400 mm | ≈ 20° | ≈ 7° RMS | ≈ 45 cm |
| **250 mm** | **≈ 32°** | **≈ 9° RMS** | **≈ 30 cm** |
| 200 mm | ≈ 40° | ≈ 11° RMS | ≈ 25 cm |

> **Correction.** Earlier revisions said the filtered noise was ~3–4°. That
> was never true of this filter: re-run, it gave about 8° at 400 mm with the
> old process-noise setting (q = 4). The current q = 1 does better at both
> baselines, which is part of why 250 mm costs so little.

### Elevation from the third anchor

A1 and A2 are level with each other, so their ranges say nothing about
height. A3, straight above them, does. In a frame with its origin midway
between A1 and A2 — x along the bar, y forward, z up — and A3 at
(0, −back, up):

```
R² = (r₁² + r₂²)/2 − b²/4              # squared distance from the bar's midpoint
x  = (r₁² − r₂²) / 2b
r₃² = R² + 2·y·back + back² − 2·z·up + up²
```

The last line is linear in z once y is known, and y² + z² = R² − x², so the
solve is a line meeting a circle: exact, closed-form, no iteration
(`uwb.solve_elevation`). The forward root is the subject; the other is behind
the bar, where the camera cannot point. Then φ = asin(z / R).

A3 sits slightly *behind* the bar rather than exactly over it so the camera
can tilt without hitting the mast. The `back` term accounts for that. It
looks small, but with the mast at 250 mm leaving it out reads **16–20° low**
at every elevation from level to 65° — far more than the whole vision trim
is allowed to correct.

The offset has one blind corner. Three anchors cannot tell a point from its
mirror image in the plane through them, and that plane leans back
atan(86/250) ≈ 19° from vertical. A subject both well below the camera *and*
far to one side can end up behind it, and resolves to the mirror. Inside the
pan and tilt limits the worst case is at pan ±80° and 45° down, where it
reads **5.7°** off (1° at the old 400 mm mast). Everywhere else the solve is
exact.

**Noise.** A Monte Carlo at σ_range = 10 cm and 5 m gives a raw elevation
spread of **27–35° from level to 65°**, no worse than the bearing (≈ 38° in
the same run), because the vertical baseline equals the horizontal one, and
it does not grow on steep shots the way a naïve asin formula would. The
elevation filter takes its noise from `UWB_A3_UP_M` the same way. Noise this
large also biases the raw mean low by up to 8° near level — the clamp in the
solver is one-sided — and the vision trim (±10°) absorbs it. About 1 % of
noisy frames have no consistent solution and are dropped; the filter carries
through them.

If A3's range drops out of a frame — it is the one most likely to be
body-shadowed — the bearing still comes from A1 and A2, and that frame simply
carries no elevation.

### Why the third anchor is vertical

The ULA1's vendor describes a minimum system of **three anchors and one tag**,
because three ranges give a *position* by trilateration. We do not need a
position. We need two angles to point a camera.

A third anchor in the horizontal plane would give (x, y), and the arctangent
of that is the bearing we already had. It would buy nothing the loops use.
Offset vertically it resolves **elevation**, which a horizontal baseline
cannot, and that changes what vision is for.

**Before A3**, the person detector was the only source of tilt. It is OpenCV
HOG, trained on upright pedestrians. Overhangs, full-extension reaches and a
back-facing climber are exactly what it misses, and a miss meant the tilt
axis stopped. **With A3**, tilt works like pan: ranging sets the angle and
vision trims a slow bias. A missed detection now only pauses the trim.

The price: one more C$78 module, a dowel and two small prints, and a longer
ranging cycle. The update rate with three anchors is still to be measured
(see [15 — Verification](../setup/15-verification.md)). Set `UWB_ANCHORS = 2` and the
build runs exactly as before, with tilt from vision alone.

### Static anchors change the loop

On the old rotating-head build the anchors turned with the lens, so θ *was*
the pan error and the loop drove it to zero. Here the bar is bolted to the
tripod, so θ is an angle in the bar's frame and the camera is simply told to
point there:

```
pan_target = θ + bias          # absolute position, commanded to OPT_MOTOR_X
```

That is less machinery, not more: no velocity integration, no windup, and no
dead-reckoned heading to maintain. What it adds is one new error source —
the pan servo is **open-loop**, so the angle we command is the angle we
believe, good to a couple of degrees.

`bias` is how that gets cleaned up. The person detector's horizontal error
feeds a slow integrator (`PAN_CV_BIAS_GAIN`, clamped to ±12°) rather than
jogging the axis directly, so vision never fights the ranging loop: UWB sets
the coarse angle, the camera trims the residual, and a servo that sits 3° off
its commanded position is absorbed within a few seconds.

Front/back ambiguity disappears with this geometry. A two-anchor baseline
cannot tell +91° from 91° behind it, but the camera only reaches ±80° anyway,
so the back hemisphere is not a place the loop can be asked to point.

## Control loops (all run on the Pi, 20 Hz)

```
uwb θ ──► Kalman ──┐
                   ├──► pan target (°) ──► slew limit ──► OPT_MOTOR_X (0x05)
person bbox ──► CV bias (slow integrator, ±12°) ──┘

uwb φ ──► Kalman ──► lens-height correction ──┐
                                              ├──► tilt target ──► slew limit ──► OPT_MOTOR_Y (0x06)
person bbox ──► CV bias (slow integrator, ±10°) ──┘
   (no A3: person bbox ──► tilt PID ──► OPT_MOTOR_Y, as before)

d ─────► zoom setpoint: EFL = frac · sensor_h · d / subject_h × vision scale
                       └─► OPT_ZOOM (0x00), rate-limited
person bbox ──► vision scale: fill the frame to 65 % (guard: zoom out fast near an edge)

d, EFL ──► FOCUS_GRID lookup (in 1/d) ──► OPT_FOCUS (0x01)
```

- **Pan**: absolute positions, not velocities. The target is the UWB bearing
  plus the CV bias; a slew limit of `PAN_MAX_DPS` keeps the servo gliding
  between control ticks instead of snapping. Everything is a local I2C write.
- **Zoom**: distance gives the first setting — an assumed 1.8 m subject at
  45 % of frame height, deliberately loose because it is a guess about the
  body. **Vision then frames the shot.** Each detection measures how much of
  the frame the person actually fills — the larger of their height and width
  fractions, measured on the body rather than the padded HOG box (about 75 %
  of its height and 55 % of its width) — and moves the zoom 35 % of the way
  (in log terms) toward `ZOOM_FILL_TARGET`, **65 %**. That leaves about 17 %
  of the frame as margin on every side for aim error and sudden moves; a
  climber stretched sideways is framed by their span. Two safeguards:
  - **Guard.** If the body comes within 3 % of any edge, or fills more than
    85 %, the zoom steps out by 0.8 at once, whatever the fill loop says.
    HOG cannot see a body that is already clipped, so the guard acts on the
    approach.
  - **Stale relax.** With no detection for 2 s — an overhang, a back-on
    reach — vision has nothing to say, so the zoom eases back to the looser
    distance framing at 30 % per second. Wider is the safe direction.

  The vision scale is limited to 0.5–2.5× the distance zoom and held to what
  the lens can actually do at either end, so it never winds up. Zoom moves
  are still deadbanded and rate-limited so the shot doesn't "breathe".
- **Focus**: from distance *and* focal length. Depth of field is generous
  at the wide end and shallow at the tele end — focused at 10 m at 10.6 mm,
  roughly 6–20 m is sharp — so a curve keyed on focal length alone is soft
  at most distances. `config.FOCUS_GRID` holds measured focus positions per
  focal length per distance, and `ptz.focus_raw` interpolates between them
  in 1/distance, which is how lens extension actually varies. Ranging
  already knows the distance, so this is focus without hunting. A deadband
  of 0.02 dioptres (about ±2 m at 10 m) keeps the motor still on ranging
  noise, and a zoom move refocuses immediately. **The shipped grid is flat
  until you calibrate it**, which reproduces the old behaviour exactly; see
  calibration step 5.
- **Tilt**: with A3, tilt is an absolute position like pan. φ is measured at
  the anchor plane, but the lens is 98 mm higher on the tilt axis, so the
  tracker rebuilds the subject's height and horizontal distance and takes
  the angle from the lens (`Tracker._aim_tilt`). At 5 m that correction is
  about 1°. `TAG_AIM_OFFSET_M` raises the aim point above the tag if you
  wear it low. The detector's vertical error, converted to degrees at the
  current zoom, feeds a bias clamped to ±10°.

  Without A3 — `UWB_ANCHORS = 2`, or a frame where A3 dropped out — tilt is
  CV-driven as before: the bounding-box centre feeds a PID on
  `OPT_MOTOR_Y`.

  > **Correction.** The vision-only tilt path used to drive the wrong way:
  > it applied the PID output with its sign inverted, so a subject low in the
  > frame tilted the camera *up*. `test_tracker.py` now checks both
  > directions.

  Detector = OpenCV HOG on the 720p preview at **3 fps**, dropping to
  0.5 fps when idle; the record stream is untouched 1080p.

  Three frames per second sounds slow and is not. A climber rises at about
  0.3 m/s, which from 10 m is 1.7°/s, and with the subject framed at 40 % of
  frame height there is roughly 0.75 m of headroom — two and a half seconds
  of tolerance. What matters far more than the rate is that each detection is
  integrated **once**: the control loop runs at 20 Hz, so acting on a cached
  box every tick would multiply the tilt gain sevenfold and make the axis
  hunt. `camera.person_bbox()` returns a freshness flag for exactly this.

  The detector also searches only a **vertical strip**. Ranging has already
  settled the horizontal question, so the tracker converts the bearing into a
  pixel column and crops to roughly 40 % of frame width around it.
- **Lost tag**: > 2 s without ranges → hold position, LED flashes; > 5 s →
  drop to `idle` (recording is stopped/saved first). This is also how a
  session ends when the climber switches the tag off.
- **Acquiring and lock-on.** A session starts in the *acquiring* phase. The
  tracker calls it locked once pan (and tilt, with A3) are within
  `ACQUIRE_POINT_TOL_DEG` (4°) of where the tag says the subject is, have
  stayed there `ACQUIRE_SETTLE_S` (0.5 s), and the person detector has seen
  someone near the middle of the frame (box centre within 25 % of the
  frame's width and height of centre) `ACQUIRE_DETECTIONS` (2) times.
  **Vision must verify; ranging alone never locks.** That way a backwards
  sign or a bad calibration shows up as a ring that keeps chasing, not as a
  clip of a wall. It costs little: at the start of a session the climber is
  usually standing upright at the foot of the wall, the pose HOG is best at.
  After `ACQUIRE_STALLED_S` (15 s) without verification the apps say
  "Can't see you — step into view, facing the camera"; **Start recording**
  in the app always works as an override. Once recording, nothing depends on
  vision — HOG losing a climber mid-route never stops a clip. A subject past
  a soft limit is locked onto from the limit. In a session the
  tag started, lock-on starts the recording
  ([01 — Concept of operations](../../../docs/product/01-requirements.md#a-session-with-uwb)).

## Camera placement envelope

How far back can the tripod sit? Three constraints, and they bite at
different distances:

1. **UWB tracking — distance-independent until the radio gives out.** Bearing
   error is σθ ≈ √2·σr / b (range noise over the 25 cm baseline), so it does
   not grow with distance: filtered bearing stays ≈ 9° at 5 m or 30 m. The
   limit is the ranging link itself: in a multipath-heavy gym (steel,
   concrete) reliable 20 Hz DS-TWR holds to **~25–35 m**; outdoors with clear
   line of sight the same DW1000 modules reach 50 m+.
2. **Resolution — the zoom is the binding constraint.** The Arducam PTZ lens
   covers 96° to 33° horizontally, which on the IMX477's 16:9 frame is a
   vertical field of 64° down to 18.9°. At full zoom the frame is 0.333 · d
   tall, so a 1.8 m subject occupies `5.4 / d` of frame height:

   | Distance | Subject height in frame, full zoom | Verdict |
   | --- | --- | --- |
   | 3 m | fills frame — zoom out to fit | close-up work |
   | 6 m | 90 % | tight |
   | 8.3 m | 65 % (the vision framing target) | **last distance at target framing** |
   | 10 m | 54 % | excellent |
   | 13.5 m | 40 % | good |
   | 20 m | 27 % | usable, visibly wider shot |
   | 30 m | 18 % | subject small; CV still locks (it needs ≈ 15 % to see a body) |

   Framing degrades gracefully past ~8 m rather than failing: the lens is at
   full zoom and the person simply fills less of the frame. At the wide
   end a full body fits from about 1.5 m out, so close range is never the
   constraint.

   > **Correction.** Earlier revisions of this document quoted an 8–20 mm lens
   > and a 43 m limit. The Arducam PTZ lens is neither — it is roughly
   > 2.8–10.6 mm on this sensor — and the old numbers were wrong for the old
   > build too. The table above is derived from the published field of view;
   > confirm it in the zoom calibration below.
3. **Geometry — closer isn't better.** Inside ~5 m of a tall wall the tilt
   angle gets steep (foreshortened footage) and pan/tilt angular rates spike
   on fast moves. At 8–12 m, a full 15 m route sweeps a comfortable ~50–60°
   of tilt.

**Rule of thumb: 6–12 m back is the sweet spot; 2 m to ~20 m works.** Past
13.5 m the subject is simply smaller than the framing target. Past ~30 m the
UWB link gives out before the pixels do.

There is a third constraint now: **the camera only pans ±80°.** At 8 m back
that sweep is about 22 m wide, which covers any bouldering wall and most
routes. Aim the lens at the middle of what you are filming and give the far
ends a check before you start.

## Calibration

1. **Antenna delay** (optional): if your anchor firmware exposes the DW1000
   antenna-delay constant, tune each board until its range to a taped 5.00 m
   is close. This is one-time, per board. Step 2 takes whatever is left, so
   with stock ULA1 firmware you can skip straight to it.
2. **Range bias**: centre the pan axis and tape the tag **5.00 m** out on the
   boresight, level with the A1/A2 boards, then run
   `python -m sportcam.rangecal 5`. It samples 300 frames, compares each
   anchor's median range with the true range the geometry gives (A1 and A2
   hypot(d, b/2), A3 hypot(d + back, up)), and prints a `RANGE_BIAS_M` to
   paste into `config.py`. That also covers the old A1–A2 offset check, since
   any r₁ − r₂ imbalance is just the difference of two biases. It prints
   each anchor's noise too; if that is well above `UWB_RANGE_SIGMA_M`, find
   out why before trusting the filters. A3's bias matters most: 5 cm of it
   alone is about 12° of elevation at 10 m, roughly r₃'s error over the mast
   height, so the short mast makes this step matter more.
3. **A3 geometry**: measure the A3 board's height above the A1/A2 boards and
   its distance behind the pan axis, and set `UWB_A3_UP_M` and
   `UWB_A3_BACK_M`. The defaults, 0.250 and 0.089 (kept in step with the CAD by `cad/fit.py`), are what the printed
   mast gives with the dowel cut to 246 mm and pushed fully home. Then stand
   the tag level with the anchors at 5 m: elevation should read about 0°.
4. **Zoom curve**: `ptz.py` interpolates focal length from the measured
   `(mm, raw)` pairs in `config.ZOOM_CURVE`, which ship as a straight line
   between the stops. To measure yours, put a metre rule at a known distance,
   step `OPT_ZOOM` across 3000–20000, and record the visible width at each
   stop — that gives field of view, and focal length follows. The lens is
   open-loop, so `Ptz.home()` drives both motors into their stops at boot
   before any of this means anything.
5. **Focus grid**: tape a high-contrast target at 2 m and run
   `python -m sportcam.focuscal 2`; repeat at 5, 10 and 30 m. At five focal
   lengths it sweeps the focus motor, keeps the sharpest position (variance
   of the Laplacian over the frame centre), and prints a `FOCUS_GRID` to
   paste into `config.py`. Do it after the zoom curve, in the light you will
   film in.
6. **Centre and direction, both axes**: run `python -m sportcam.ptzcheck`.
   It sweeps each axis to its soft limits so you can confirm `PAN_CENTER_RAW`
   and `TILT_CENTER_RAW` really centre the lens (on the bar's normal, and
   level), and that neither `PAN_SIGN` nor `TILT_SIGN` is mirrored. A wrong
   sign makes the camera run away from the subject, which looks like a
   tracking failure and is not one. With A3 fitted this matters for tilt as
   much as pan, since tilt is now commanded from ranging rather than
   corrected step by step from the picture.

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
  ranges keep flowing (diffraction), and A3 — high on its mast — is usually
  the anchor with the clearest path to a tag facing upward. Expect the
  noisiest angles of the session here, not a loss of lock.
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

- The tag is the **initiator**: it polls each anchor in turn and broadcasts
  the collected ranges. It has its own power and is unaffected by the
  camera's; on a 2 500 mAh USB bank it runs well past a full day.
- **Switching the tag on and off is the remote control.** On: the camera
  acquires the subject and starts recording. Off: 5 s later it saves and
  returns to standby. Nothing on the tag needs changing for this — the camera
  just notices ranging start and stop (`device/sportcam/session.py`).
- The old wearable sketch's pair/record button and BLE broadcast are not
  ported to the ULA1, and with the tag's power doing the job they are no
  longer needed.
- LED: blinks green when ranging. The tag runs off a USB power bank and
  cannot read its charge, so the bank's own indicator shows the battery level.
