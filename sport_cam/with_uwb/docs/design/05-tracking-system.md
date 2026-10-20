# 05 — Tracking system

The subject wears a UWB (ultra-wideband radio) tag. Three anchors on the
camera head measure their distance to it 20 times a second, and from those
three distances the camera works out the subject's **bearing, elevation and
distance**. Vision then does three smaller jobs: it trims what's left of the
aim error, frames the shot with the zoom, and confirms there really is a
person in view before a session records.

This doc covers why UWB, the geometry, the control loops, where to put the
camera, calibration, and how to wear the tag.

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
**≈ 9° RMS** (≈ 7° with a 400 mm baseline). The camera's horizontal FOV at wide is
96°, so the subject stays in frame; CV centring trims the rest.

| Baseline | Raw σ_θ | Filtered, moving subject | Head width |
| --- | --- | --- | --- |
| 400 mm | ≈ 20° | ≈ 7° RMS | ≈ 45 cm |
| **250 mm** | **≈ 32°** | **≈ 9° RMS** | **≈ 30 cm** |
| 200 mm | ≈ 40° | ≈ 11° RMS | ≈ 25 cm |

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
atan(89/250) ≈ 20° from vertical. A subject both well below the camera *and*
far to one side can end up behind it, and resolves to the mirror. Inside the
pan and tilt limits the worst case is at pan ±80° and 45° down, where it
reads **5.7°** off (1° with a 400 mm mast). Everywhere else the solve is
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

**Without A3**, the person detector is the only source of tilt. It is
OpenCV HOG, trained on upright pedestrians. Overhangs, full-extension reaches
and a back-facing climber are exactly what it misses, and a miss stops the
tilt axis. **With A3**, tilt works like pan: ranging sets the angle and
vision trims a slow bias, so a missed detection only pauses the trim.

The price: one more C$78 module, a dowel and two small prints, and a longer
ranging cycle. The update rate with three anchors is still to be measured
(see [15 — Verification](../setup/15-verification.md)). Set `UWB_ANCHORS = 2` to
build without it; tilt then comes from vision alone.

### Static anchors change the loop

The anchors don't turn with the lens: the arms are bolted to the enclosure.
So θ is an angle in the bar's frame, and the camera is simply told to point
there:

```
pan_target = θ + bias          # absolute position, commanded to OPT_MOTOR_X
```

That needs no velocity integration, no windup and no dead-reckoned heading.
It does have one error source: the pan servo is **open-loop**, so the angle
we command is the angle we believe, good to a couple of degrees.

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
   (no A3: person bbox ──► tilt PID ──► OPT_MOTOR_Y)

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
  body. **Vision then frames the shot**, filling 65 % of the frame, with a
  fast zoom-out guard near the edges
  ([06 — Framing and focus](../../../docs/design/06-device-software.md#framing-and-focus)).
  The vision correction is limited to 0.5–2.5× the distance zoom and to what
  the lens can do at either end, so it never winds up.
- **Focus**: from the ranged distance and the focal length, through
  `FOCUS_GRID` ([06](../../../docs/design/06-device-software.md#framing-and-focus)).
  Ranging already knows the distance, so this is focus without hunting.
- **Tilt**: with A3, tilt is an absolute position like pan. φ is measured at
  the anchor plane, but the lens is 98 mm higher on the tilt axis, so the
  tracker rebuilds the subject's height and horizontal distance and takes
  the angle from the lens (`Tracker._aim_tilt`). At 5 m that correction is
  about 1°. `TAG_AIM_OFFSET_M` raises the aim point above the tag if you
  wear it low. The detector's vertical error, converted to degrees at the
  current zoom, feeds a bias clamped to ±10°.

  Without A3 — `UWB_ANCHORS = 2`, or a frame where A3 dropped out — tilt
  comes from vision: the bounding-box centre feeds a PID on `OPT_MOTOR_Y`.

  Detector = OpenCV HOG on the 720p preview at **3 fps**, dropping to
  0.5 fps when idle; the record stream is untouched 1080p. That is plenty: a
  climber rises at about 0.3 m/s, which from 10 m is 1.7°/s, and the 17 %
  framing margin gives several seconds of tolerance. Each detection is used
  **once**, and only a vertical strip about 40 % of the frame wide around the
  ranged bearing is searched
  ([06 — Vision](../../../docs/design/06-device-software.md#vision-and-why-it-runs-slowly)).
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

How far back can the tripod sit? Four constraints, and they bite at
different distances:

1. **UWB tracking — distance-independent until the radio gives out.** Bearing
   error is σθ ≈ √2·σr / b (range noise over the 25 cm baseline), so it does
   not grow with distance: filtered bearing stays ≈ 9° at 5 m or 30 m. The
   limit is the ranging link itself: in a multipath-heavy gym (steel,
   concrete) reliable 20 Hz DS-TWR holds to **~25–35 m**; outdoors with clear
   line of sight the same DW1000 modules reach 50 m+.
2. **Resolution — the zoom is the binding constraint.** At full zoom a 1.8 m
   subject fills the 65 % framing target out to about 8.3 m, 40 % at 13.5 m
   and 18 % at 30 m; full-body framing works from about 1.5 m. The full table
   is in [03 — How far the zoom reaches](../../../docs/design/03-mechanical-design.md#how-far-the-zoom-reaches).
3. **Geometry — closer isn't better.** Inside ~5 m of a tall wall the tilt
   angle gets steep (foreshortened footage) and pan/tilt angular rates spike
   on fast moves. At 8–12 m, a full 15 m route sweeps a comfortable ~50–60°
   of tilt.
4. **Pan range — the camera only pans ±80°.** At 8 m back that sweep is
   about 22 m wide, which covers any bouldering wall and most routes. Aim the
   lens at the middle of what you are filming and give the far ends a check
   before you start.

**Rule of thumb: 6–12 m back is the sweet spot; 2 m to ~20 m works.** Past
13.5 m the subject is simply smaller than the framing target. Past ~30 m the
UWB link gives out before the pixels do.

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
   paste into `config.py`. That also covers any A1–A2 imbalance, since
   r₁ − r₂ is just the difference of two biases. It prints
   each anchor's noise too; if that is well above `UWB_RANGE_SIGMA_M`, find
   out why before trusting the filters. A3's bias matters most: 5 cm of it
   alone is about 12° of elevation at 10 m, roughly r₃'s error over the mast
   height, so the short mast makes this step matter more.
3. **A3 geometry**: measure the A3 board's height above the A1/A2 boards and
   its distance behind the pan axis, and set `UWB_A3_UP_M` and
   `UWB_A3_BACK_M`. The defaults, 0.250 and 0.089 (kept in step with the CAD by `cad/fit.py`), are what the printed
   mast gives with the dowel cut to 246 mm and pushed fully home. Then stand
   the tag level with the anchors at 5 m: elevation should read about 0°.
4. **Lens and servos**: the zoom curve, the focus grid, and the centre and
   direction of both axes are calibrated the same way in both builds;
   [14 — Software setup](../setup/14-software-setup.md#6-calibrate) has the
   steps. With A3 fitted, the servo direction matters for tilt as much as
   pan, since tilt is commanded from ranging: a wrong `TILT_SIGN` makes the
   camera run away from the subject, which looks like a tracking failure and
   isn't one.

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
- **Camera placement in the gym**: 8–12 m back from the wall base (it works
  from about 2 m to 20 m — see the [placement envelope](#camera-placement-envelope)).
  Tilt runs from −45° to +85°, so even a top-out 15 m up seen from 7 m away
  (~65° elevation) is comfortably in range.
- **Jumpy bearing indoors**: gyms are full of steel and concrete, which
  reflect the radio. The Kalman filters assume ranges good to about 10 cm
  (`UWB_RANGE_SIGMA_M = 0.10` in `config.py`). If the bearing looks jumpy,
  raise it toward 0.15 before touching any gains.
- **Sweat and chalk**: the pod's USB-C slot faces down when worn; wipe the
  case, not the board. Chalk dust is non-conductive and harmless; sweat
  ingress is the reason the case has no top vents.

## Wearable behaviour

- The tag is the **initiator**: it polls each anchor in turn and broadcasts
  the collected ranges. It has its own power and is unaffected by the
  camera's; on a 2 500 mAh USB bank it runs well past a full day.
- **Switching the tag on and off is the remote control**, and it has no
  buttons. The camera just notices ranging start and stop
  ([01 — A session](../../../docs/product/01-requirements.md#a-session-with-uwb),
  `src/with_uwb/device/sportcam/session.py`).
- LED: blinks green when ranging. The tag runs off a USB power bank and
  cannot read its charge, so the bank's own indicator shows the battery level.
