# 05 — Tracking system

The subject wears a UWB (ultra-wideband) tag. Three anchors on the camera
head range it at 20 Hz. The ranges give the subject's **bearing, elevation
and distance**. Vision (person detector) has three secondary roles: trim the
residual aim error, set the zoom framing, and confirm a person is in view
before a session records.

Contents: sensor choice, geometry, control loops, placement envelope,
what calibration corrects, tag placement.

## Why UWB (and not BLE, GPS, or vision alone)

| Option | Accuracy / behaviour | Verdict |
| --- | --- | --- |
| BLE RSSI | ±3–5 m; poor under multipath | unusable for aiming |
| GPS on the wearable | 2–5 m; outdoor only; no bearing without a second receiver | unusable |
| Vision only | can't identify *which* person; loses lock on occlusion or exit | used as a secondary sensor |
| **UWB two-way ranging** | **±10–30 cm range, ≈ 20 Hz, low-cost DW1000 modules, identity from the tag** | **primary sensor** |

Fusion: UWB provides identity, bearing, elevation and distance. Vision trims
both angles, frames the shot, and confirms the person before recording.

## Geometry

![Tracking geometry](../images/tracking-geometry.png)

| Anchor | Position | Purpose |
| --- | --- | --- |
| A1, A2 | on arms bolted to the enclosure; **400 mm apart** (baseline b), symmetric about the pan axis | bearing, distance |
| A3 | on a mast behind the lens; **250 mm above** A1/A2, ≈ 89 mm back | elevation |

- All anchors are **static**: they don't move with the lens.
- Spacing is a compromise between head size
  ([C1, C2](../../product/01-requirements.md#non-functional-requirements))
  and angle noise, which grows as spacing shrinks.
- The tag ranges each anchor in turn and broadcasts one frame with r₁, r₂, r₃.
  A single frame means one timestamp: the formulas below assume simultaneous
  ranges. Ranges sampled tens of ms apart from independent radios would add
  the subject's motion to the angle error.

```
d  = (r₁ + r₂) / 2                     # distance to subject
θ  ≈ asin( (r₁² − r₂²) / (2·b·d) )     # bearing from the anchor bar's normal
```

**Bearing noise.** σ_θ ≈ √2·σ_range / b. With b = 0.40 m and σ_range ≈ 10 cm:
≈ 20° raw per sample. A 1-D Kalman filter on θ feeds the pan loop; its
measurement noise is derived from the baseline and `UWB_RANGE_SIGMA_M`, so
it smooths more on shorter baselines. Simulated subject crossing at 5 m, up
to 1.8 m/s: **≈ 7° RMS** filtered (≈ 5.4° for a subject standing still,
wandering with a ≈ 0.35 s correlation time; `bearingcal` measures both on
your hardware). 400 mm rather than the earlier 250 mm because the
[tag-wearer match](#telling-the-tag-wearer-from-everyone-else) waits on this
noise: beside a belayer it decides in about half the time. Wide-end horizontal FOV is 96°, so the
subject stays in frame; the vision trim removes the remainder.

| Baseline | Raw σ_θ | Filtered, moving subject | Head width |
| --- | --- | --- | --- |
| **400 mm** | **≈ 20°** | **≈ 7° RMS** | **≈ 42 cm** |
| 250 mm | ≈ 32° | ≈ 9° RMS | ≈ 30 cm |
| 200 mm | ≈ 40° | ≈ 11° RMS | ≈ 25 cm |

### Elevation from the third anchor

A1 and A2 are level, so r₁ and r₂ carry no height information; A3 does.
Frame: origin midway between A1 and A2, x along the bar, y forward, z up;
A3 at (0, −back, up).

```
R² = (r₁² + r₂²)/2 − b²/4              # squared distance from the bar's midpoint
x  = (r₁² − r₂²) / 2b
r₃² = R² + 2·y·back + back² − 2·z·up + up²
```

- Solve: the last equation is linear in z given y, and y² + z² = R² − x², so
  it is a line–circle intersection. Closed form, no iteration
  (`uwb.solve_elevation`). The forward root is the subject; the rear root is
  behind the bar. φ = asin(z / R).
- **`back` offset:** A3 sits behind the bar so the camera can tilt without
  hitting the mast. Omitting the `back` term reads **16–20° low** from level
  to 65° with a 250 mm mast, beyond the vision trim's range.
- **Blind corner:** three anchors can't distinguish a point from its mirror
  image in their plane, which leans back atan(89/250) ≈ 20° from vertical. A
  subject well below *and* far to the side of the camera can fall behind that
  plane and resolve to the mirror. Worst case within the pan/tilt limits:
  pan ±80°, 45° down, **≈ 6.3°** error with A3 89 mm back (≈ 1.2° with a 400 mm
  mast); the solver returns the mirror image exactly. Exact elsewhere.
- **Noise** (Monte Carlo, σ_range = 10 cm, 5 m): raw elevation spread
  **27–35° from level to 65°**, comparable to bearing (≈ 38° in the same run)
  because the vertical baseline equals the horizontal one; it does not grow
  at steep angles. The elevation filter derives its noise from `UWB_A3_UP_M`.
  The solver's one-sided clamp biases the raw mean low by up to 8° near
  level; the vision trim (±10°) absorbs it. ≈ 1 % of noisy frames have no
  consistent solution and are dropped; the filter coasts through them.
- **A3 dropout** (most likely to be body-shadowed): bearing still comes from
  A1/A2; that frame has no elevation.

### Why the third anchor is vertical

The vendor's minimum system (three anchors, one tag) is for trilateration of
a *position*. The camera needs two *angles*.

| A3 placement | Adds | Value to the loops |
| --- | --- | --- |
| Horizontal plane | (x, y) position | none: atan(x, y) is the existing bearing |
| **Vertical offset** | **elevation** | tilt from ranging |

| | Tilt source | Effect of a missed detection |
| --- | --- | --- |
| Without A3 (`UWB_ANCHORS = 2`) | person detector only (OpenCV HOG, trained on upright pedestrians; misses overhangs, extended reaches, back-facing climbers) | tilt axis stops |
| **With A3** | ranging, with a slow vision bias trim | only the trim pauses |

Cost: one C$78 module, a dowel, two small prints, and a longer ranging cycle.
Measure the three-anchor update rate during bench checks
([15 — Verification](../setup/15-verification.md)).

### Static anchors change the loop

The anchors are fixed to the enclosure, so θ is an angle in the bar's frame
and is commanded directly as an absolute position:

```
pan_target = θ + bias          # absolute position, commanded as the pan servo's pulse
```

- No velocity integration, windup or dead-reckoned heading.
- Error source: the pan servo is **open-loop**; the commanded angle is
  assumed, accurate to ≈ 2°.
- `bias` corrects it: the detector's horizontal error feeds a slow
  integrator (`PAN_CV_BIAS_GAIN`, clamped ±12°). Vision never drives the
  axis directly, so it can't fight the ranging loop. A 3° servo offset is
  absorbed within seconds.
- Front/back ambiguity of a two-anchor baseline (+91° vs 91° behind) is
  irrelevant: pan is limited to ±80°.

## Control loops (all run on the Pi, 20 Hz)

```
uwb θ ──► Kalman ──┐
                   ├──► pan target (°) ──► ease ──► pan PWM (GPIO12)
person bbox ──► CV bias (slow integrator, ±12°) ──┘

uwb φ ──► Kalman ──► lens-height correction ──┐
                                              ├──► tilt target ──► ease ──► tilt PWM (GPIO13)
person bbox ──► CV bias (slow integrator, ±10°) ──┘
   (no A3: person bbox ──► tilt PID ──► tilt PWM)

d ─────► zoom setpoint: EFL = frac · sensor_h · d / subject_h × vision scale
                       └─► OPT_ZOOM (0x00), rate-limited
person bbox ──► vision scale: fill the frame to 65 % (guard: zoom out fast near an edge)

d, EFL ──► FOCUS_GRID lookup (in 1/d) ──► OPT_FOCUS (0x01)
```

| Loop | Behaviour |
| --- | --- |
| **Pan** | absolute position = UWB bearing + CV bias, eased toward it: speed = distance left / `TRACK_EASE_S` (0.4 s), capped at `PAN_MAX_DPS` and at the speed that can still stop there, changed by at most `PAN_MAX_ACCEL_DPS2` (60 °/s²) per second. Ranging noise and each vision bias update bend the motion rather than jerking it; the turn to the tag at session start takes ≈ 1.5 s for 40° |
| **Tilt (with A3)** | absolute position. φ is measured at the anchor plane; the lens is 98 mm higher, so `Tracker._aim_tilt` recomputes the angle from the lens (≈ 1° at 5 m). `TAG_AIM_OFFSET_M` raises the aim point above a low-worn tag. Vision bias clamped ±10° |
| **Tilt (no A3)** | `UWB_ANCHORS = 2`, or a frame without A3: box centre → PID → tilt servo |
| **Zoom** | initial setting from distance (1.8 m subject at 45 % of frame height); vision then frames to 65 % with an edge guard ([06](../../design/06-device-software.md#framing-and-focus)). Vision scale limited to 0.5–2.5× the distance zoom and to the lens range (no windup) |
| **Focus** | ranged distance + focal length → `FOCUS_GRID` ([06](../../design/06-device-software.md#framing-and-focus)); no hunting |
| **Detector** | `DETECTOR`: OpenCV HOG (default) or MobileNet-SSD ([06 — The two detectors](../../design/06-device-software.md#the-two-detectors)) on the 720p preview, 3 fps (0.5 awake); record stream untouched 1080p. Each detection used once; search strip ≈ 40 % of frame width around the ranged bearing ([06](../../design/06-device-software.md#vision-and-why-it-runs-slowly)). Sufficient: a climber at 0.3 m/s seen from 10 m moves 1.7°/s, and the 17 % framing margin gives several seconds of tolerance |
| **Wearer out of sight** | recording, tag still ranging, no detection of the wearer for `LOST_ZOOM_OUT_S` (2 s): zoom straight out to wide (past the zoom rate limit), still turning with the tag, and search the whole frame. Vision sees them again: the framing closes back in from wide. Mostly a climber above or beside a tight shot, which is also when tilt without A3 needs vision most |
| **Lost tag** | > 2 s without ranges: hold, LED flashes (solid red while recording). > 5 s: `awake` (recording saved first). Same path as a tag switched off |

### Search, found and recording

The same state machine as the camera-only build
([without UWB, 05](../../without_uwb/design/05-tracking-system.md#the-state-machine)).
The difference is SEARCH: the tag gives the subject's location at once, so
there is no sweep. The head still has to pan and tilt to bring the person
into frame. Every session starts in SEARCH: awake's person in frame could be
anyone, so unlike the camera-only build it never skips straight to FOUND.

```
   awake ──tag on / Start tracking──►  SEARCH   turn to the ranged position
   sleep ──tag on / Record─────────►    (the sensor starts; vision is ready
                                         after CAMERA_WARMUP_S)
                                        │
                                        │ on target 0.5 s, tag wearer seen
                                        ▼
                                      FOUND    track and frame as when recording
                                        │      (tag wearer unseen for 1 s → SEARCH)
                                        │ still in frame 3 s later,
                                        │ and clearly the tag wearer
                                        ▼
                                      TRACK ── recording
```

| Mode | Behaviour | Exit |
| --- | --- | --- |
| **awake**, no person in frame / person in frame | head parked (centred), zoom wide; detector at `DETECT_FPS_AWAKE` (0.5 fps). Person in frame from a detection of anyone until `AWAKE_PERSON_HOLD_S` (4 s) pass without one; it drives the LED and app only | session start (tag on, or **Start tracking**) → SEARCH; `AWAKE_TIMEOUT_S` with no session and no live viewer → sleep |
| **sleep** | sensor off, head parked; the radios keep ranging. `AWAKE_TIMEOUT_S` (30 s) in awake with no session and nobody watching the live view → sleep | **Wake up** → awake; tag on, or **Record** → SEARCH |
| **SEARCH** | pan (and tilt, with A3) eases to the ranged position | within `ACQUIRE_POINT_TOL_DEG` (4°) for `ACQUIRE_SETTLE_S` (0.5 s) and the tag wearer detected (below) → FOUND |
| **FOUND** | the full tracking loop, as in recording: ranged pan and tilt, vision trim, zoom and focus, all from the tag wearer's box. The person need not be centred | seen throughout `FOUND_CONFIRM_S` (3 s) and nobody else as near the tag → recording (TRACK); tag wearer unseen for `FOUND_LOST_S` (1 s) → SEARCH |
| **TRACK** | recording, for the rest of the session; a hidden tag or a missed detection is ordinary tracking. Wearer unseen 2 s: zoom out to wide until seen again | session end |

Mapping to app states (telemetry `phase`): awake = `awake`/`no-person-in-frame`
or `awake`/`person-in-frame`; SEARCH = `tracking`/`search` (the app pings
every 3 s); FOUND = `tracking`/`found`; TRACK = `recording`/`track`.
Telemetry `countdown` carries the seconds left in FOUND (3, 2, 1); the app
beeps on each, then chimes when recording starts. Not recording after
`ACQUIRE_STALLED_S` (15 s): the app reports "Can't pick you out — step
into view, away from anyone else".

- **Ranging alone never records.** A sign or calibration error shows as a
  ring that keeps chasing, not a recording of a wall. Session start is
  usually an upright climber at the wall base, HOG's best case.
- **Vision alone never records either**: a person only counts if they are
  where the tag is (next section).
- Once recording, nothing depends on vision; detector loss mid-route doesn't
  stop the clip.
- A subject beyond a soft limit is found from the limit.
- Every session records after found, whether the tag or **Start tracking**
  started it ([01](../../product/01-requirements.md#state-machine-with-uwb)).
  **Stop recording** ends the session.

### Telling the tag wearer from everyone else

The detector finds people, not *the* person. A belayer, a spotter or
someone walking past can be in frame too, and is often the bigger box.
So in SEARCH and FOUND a detection only counts if it is the tag wearer,
decided in `Tracker._match_tag` in three steps:

| Step | Rule | Rejects |
| --- | --- | --- |
| **Gate** | a new box is admitted only if its bearing (pan angle + its position in the frame at the current zoom) is within `TAG_MATCH_BEARING_DEG` (14°, ≈ 2σ of the filtered bearing) of the tag's, and the distance its height implies (thin lens, `SUBJECT_HEIGHT_M`) is within ×/÷ `TAG_MATCH_RANGE_RATIO` (2) of the ranged distance. A box clipped at the top or bottom can only fail as too near | anyone off to the side; anyone much nearer or farther than the tag, such as a person walking past the lens |
| **Follow** | the gate only admits. Each person admitted is followed from detection to detection by bearing (moved < `TAG_FOLLOW_DEG`, 6°), averaged on every detection, and forgotten only after `TAG_FORGET_S` (5 s) out of view | a second person taking over between detections; a rival dropping out of the comparison because bearing noise briefly pushed them outside the gate |
| **Average** | each person keeps the running mean of (box bearing − tag bearing). SEARCH takes whoever is nearest on average. FOUND records only once everyone else is further from the tag by `TAG_MATCH_Z` (3) standard errors of those averages, and at least `TAG_MATCH_MARGIN_DEG` (4°). The standard error is `TAG_BEARING_SIGMA_DEG` (7°) over √(seconds watched / `TAG_BEARING_CORR_S`), where 0.35 s is the Kalman filter's memory. Both are estimates until `bearingcal` measures them ([Calibration](#calibration)). Until then the countdown holds at 1. If someone else earns that lead instead, FOUND switches to them and the countdown starts again | someone standing beside the wearer |

The average is what makes this work. One bearing is ≈ 7° RMS, too noisy to
split a climber from a belayer standing 1 m away at 10 m (≈ 6°). But the
noise averages down over time and the two people don't. The lead it asks
for shrinks as the averages firm up. The test is repeated on every
detection, which raises the chance of a lucky wrong call. Z = 3 was chosen
by simulation for that reason: 2 and 2.5 each made the occasional wrong
call. Simulated with the bearing noise above (`NoisyUwb` in
`test_session.py`):

| Second person, 10 m out | Records the climber | Wrong person |
| --- | --- | --- |
| alone in the gate | after the usual 3 s | — |
| 2.5 m away (14°) | in ≈ 4–10 s | 0 of 12 |
| 1.5 m away (8.6°) | in ≈ 8 s on average, all within 18 s | 0 of 12 |
| 1 m away (5.7°) | in ≈ 12 s on average, all within 30 s | 0 of 12 |
| 0.5 m away (2.9°) | not within 30 s | 0 of 12 |

With the earlier 250 mm baseline (9°, 0.6 s) 1.5 m took ≈ 17 s and 1 m
never resolved.

Too close to tell apart, the camera never records. After
`ACQUIRE_STALLED_S` (15 s) the app asks the climber to step away from
others. The anchor baseline is the hardware lever: the bearing noise
falls with spacing ([C2](../../product/01-requirements.md#non-functional-requirements)).

While more than one person is being compared, the vision pan bias stands
still until recording. Otherwise it would lean toward whoever was picked
first, and the averages are measured against it. Bystanders never move
tilt, zoom or focus. In TRACK the chosen person is followed and others in
frame are ignored. During a tag dropout mid-climb they are followed by
position alone.

This relies on the range bias calibration below. A bearing off by
more than about half the gap between two people can favour the wrong one.
The single-person case, which is most sessions, is unaffected: one box in
the gate is the wearer.

### Boxes in the recording

Each detection while recording is saved with a label per box
(`Tracker._label`), and the players draw them over the clip in colour
([08](../../design/08-recordings-and-cloud.md#person-boxes)). The
live view shows the same labels as they are made; in awake, before anyone is
picked, every box is `unsure`. While recording:

| Label | Colour | When |
| --- | --- | --- |
| `climber` | green | the tag wearer, once they can be told from everyone else: in TRACK, or chosen and clear of the rest of the gate |
| `other` | yellow | everyone else at that point. Also every box when none of them passed the gate: none is where the tag is |
| `unsure` | red | every box, while two people in the gate are still being told apart, while the wearer is out of sight but someone in the gate is not, or with no ranging to judge by |

Recording starts only once the wearer is clear, so red in a clip mostly
means the wearer went out of view beside someone else.

## Camera placement envelope

| # | Constraint | Limit |
| --- | --- | --- |
| 1 | **UWB link** | bearing error is independent of distance (σ_θ ≈ √2·σ_r / b; ≈ 7° filtered at 5 m or 30 m). Reliable 20 Hz DS-TWR to **≈ 25–35 m** in a gym (steel, concrete); 50 m+ outdoors line-of-sight |
| 2 | **Resolution (zoom)** — binding | 1.8 m subject at full zoom: 65 % of frame to ≈ 8.3 m, 40 % at 13.5 m, 18 % at 30 m; full body from ≈ 1.5 m ([03](../../design/03-mechanical-design.md#how-far-the-zoom-reaches)) |
| 3 | **Geometry** | < 5 m from a tall wall: steep tilt (foreshortening) and high angular rates. At 8–12 m a 15 m route spans ≈ 50–60° of tilt |
| 4 | **Pan range ±80°** | at 8 m the sweep is ≈ 22 m wide (any bouldering wall, most routes). Aim at the centre of the area; check both ends before starting |

**Recommended: 6–12 m. Working range: 2–20 m.** Beyond 13.5 m the subject is
below the framing target; beyond ≈ 30 m the UWB link fails first.

## Calibration

What has to be measured on your hardware, and why. The procedure is
[14 — Software setup, step 6](../setup/14-software-setup.md#6-calibrate).

| Quantity | Why it matters |
| --- | --- |
| **Range bias** per anchor (`RANGE_BIAS_M`) | every angle comes from differences between ranges, so a constant offset on one anchor is an angle error. It also corrects A1–A2 imbalance. A3 is critical: 5 cm of A3 bias ≈ 12° of elevation at 10 m. Tuning each board's DW1000 antenna delay would do the same job, but stock ULA1 firmware doesn't expose it, and the bias absorbs it |
| **A3 geometry** (`UWB_A3_UP_M`, `UWB_A3_BACK_M`) | the [elevation solve](#elevation-from-the-third-anchor) uses both. The defaults (0.250 / 0.089) match the printed mast with the dowel cut to 246 mm, kept in step with the CAD by `cad/fit.py` |
| **Bearing noise** (`TAG_BEARING_SIGMA_DEG`, `TAG_BEARING_CORR_S`) | sets how long the [tag-wearer match](#telling-the-tag-wearer-from-everyone-else) averages. Overestimates only make it slower; underestimates can let it pick the wrong person |
| **Lens and servos** | zoom curve, focus grid, axis centre and direction, as in the camera-only build. With A3, `TILT_SIGN` matters as much as `PAN_SIGN`: a wrong sign drives the camera away from the subject |

## Wearing the tag

Propagation: UWB passes through fabric with negligible loss; no optical line
of sight is needed. The body (water) attenuates it. Placement goal: keep the
torso out of the tag → camera path. The pod (`cad/wearable_case.scad`) keeps
a foam pad between the ceramic antenna and skin; direct skin contact detunes
the antenna.

Where to wear it for each discipline, and what to do about a jumpy
bearing: [14 — Wearing the tag](../setup/14-software-setup.md#10-wearing-the-tag).

## Wearable behaviour

| Item | Behaviour |
| --- | --- |
| Role | ranging **initiator**: polls each anchor, broadcasts the collected ranges |
| Power | independent USB bank; 2 500 mAh lasts > 1 day |
| Control | power switch only. On starts a session, off ends it; the camera detects ranging start and stop ([01](../../product/01-requirements.md#state-machine-with-uwb), `src/with_uwb/device/sportcam/session.py`) |
| LED | blinks green while ranging. Battery level: the bank's own indicator |
