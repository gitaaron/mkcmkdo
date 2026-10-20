# 05 — Tracking system

![Search and track](../images/search-and-track.png)

SportCam finds and follows a person by **vision alone**. There is no tag, no
radio and no anchor: the user taps **Track & record**, the camera sweeps the
room until its person detector sees someone, centres them, locks on, and from
then on keeps them framed. Pan, tilt, zoom and focus are all register writes
to one I2C controller on the Pi ([03](../../../docs/design/03-mechanical-design.md),
[04](../../../docs/design/04-electronics.md)), so the whole loop runs on the device, 20 times a
second.

## Why camera-only

The other build, [with UWB](../../../with_uwb/docs/design/05-tracking-system.md),
tells the camera where the subject is with ultra-wideband radio: a wearable
tag ranged by three anchors on the camera head. It is precise and works
through a body or a jacket. It also means a tag to wear and charge, three
anchor boards, two printed arms, a mast and range calibration. This build
drops all of it.

<!--compare-->

| | Camera-only (this build) | With UWB (the other build) |
| --- | --- | --- |
| Wearable | none | tag on a harness or armband |
| Who gets filmed | the first person the camera sees | whoever wears the tag, even out of sight |
| Hardware on the head | the camera | camera + 3 radios + arms + mast |
| Calibration | zoom, focus, servo direction | those, plus range bias per anchor |
| Starts when | user taps **Track & record** | tag switched on |
| Distance | estimated from the person's size | measured |
| Fails when | pose or light defeats the detector; person hidden | body shadows the radio; tag switched off or flat |
| Power | ≈ 3 W less at 5 V | |

What you gain is a build with nothing to wear and half the parts. What you
give up is identity: vision cannot tell one person from another, so the camera
films whoever it finds first. See [limitations](#limitations); they are the
price of the simplification and the rest of this document is about making the
best of them.

## The state machine

```
                       Track & record
   idle ────────────────────────────────────────►  SEARCH
                                                    │  sweep pan ±80° at 25°/s,
                                                    │  step tilt row at each turn,
                                                    │  zoom wide, focus 5 m
                          person seen               ▼
                        ┌───────────────────────  CENTRE
     nobody seen again  │   turn to put them        │
     for 2 s ──► SEARCH │   in the middle           │ 2 consecutive centred detections
                        └──────────────────────────►▼
                                                   TRACK ── first lock starts recording
                                                    │
                          missing 2 s: hold, ring flashes
                          missing 6 s: ─────────────► SEARCH (toward the side they left)
```

| Mode | Camera does | Leaves when |
| --- | --- | --- |
| **SEARCH** | zooms wide, focuses at `SEARCH_FOCUS_M` (5 m), sweeps pan end to end at `SEARCH_PAN_DPS` (25°/s), and at each turn-around steps to the next of `SEARCH_TILT_ROWS_DEG` (5°, 22°) | the detector sees a person → CENTRE. If tracking only (not recording), nobody was ever found and `SEARCH_GIVE_UP_S` (180 s) pass → app state `idle` |
| **CENTRE** | stops sweeping, turns toward the largest person in view until their box centre is within `ACQUIRE_CENTRE_FRACTION` (20 %) of the middle of the frame | `ACQUIRE_DETECTIONS` (2) consecutive centred detections → TRACK; nobody seen for `CENTRE_TIMEOUT_S` (2 s) → SEARCH |
| **TRACK** | follows the person (below), frames them, estimates distance for focus | missing for `RESEARCH_AFTER_S` (6 s) → SEARCH |

The state the app sees is the usual `idle → tracking → recording`; SEARCH and
CENTRE are the `acquiring` phase, TRACK is `acquired`. The sweep is slow on
purpose. At the wide end the frame is 96° across, so 25°/s moves a quarter of
the frame per second: a person is in view for several detections as the frame
goes past, and does not smear. A full pass is 160° ÷ 25°/s ≈ 6.4 s, so both
tilt rows are covered in about 13 s. The app's "can't see anyone" pill appears
after `ACQUIRE_STALLED_S` (15 s), a little more than one full cycle.

### Lock-on rules

- **The first person found wins.** At first sighting, if several people are
  in view, the largest detection is taken.
- **Two centred detections to lock.** A single-frame false positive — a coat
  stand, a chair — costs a short pause: the camera turns toward it, doesn't
  see it again, and after 2 s resumes the sweep. It cannot start a recording
  of furniture.
- **Recording starts on the first lock** (`AUTO_RECORD_ON_LOCK`), so the clip
  is of the person, not of an empty room being swept. The user can stop
  recording and tracking continues; the camera does not start a second
  recording in the same session. Set `AUTO_RECORD_ON_LOCK = False` to make
  recording a separate tap (**Record now**).
- **Follow the nearest, not the biggest.** Once someone is being followed,
  each detection is matched to the one nearest the last position, within a
  gate of `TRACK_GATE_FRACTION` (45 % of frame width). Further away than that
  is "not the same person" and is ignored, so a bystander walking past does
  not steal the lock.
- **Missing target.** After `LOST_HOLD_S` (2 s) the LED ring flashes at 2 Hz and
  the camera holds still; recording is unaffected. After `RESEARCH_AFTER_S`
  (6 s) it sweeps again, starting toward the side the person was last heading,
  while recording continues. Zoom has been easing wide in the meantime.
- **An empty room.** A tracking session (not recording) that has never found
  anyone gives up after 180 s and returns to idle. A recording is never
  abandoned this way.

## Control loops (all run on the Pi, 20 Hz)

```
person boxes (3 fps, fresh only) ──► nearest-to-last (gate) ──► offset from centre (px)
      │                                                            │ × degrees-per-pixel at current FOV
      │                                                            ▼
      │                                         goal += gain × offset   (pan 0.6, tilt 0.5, deadband 4 %)
      │                                                            ▼
      │                                         slew limit (PAN_MAX_DPS 120, TILT_MAX_DPS 90) ──► OPT_MOTOR_X / _Y
      │
      ├──► fill = person size / frame ──► zoom loop (target 65 %, guard, stale relax) ──► OPT_ZOOM
      └──► apparent height, thin lens ──► distance (smoothed) ──► FOCUS_GRID lookup ──► OPT_FOCUS
```

- **Pan and tilt.** The camera is steered by the person's offset from the
  middle of the frame. On each **fresh** detection the pan goal moves by
  `TRACK_PAN_GAIN` (0.6) times the offset converted to degrees through the
  current field of view, and the tilt goal by `TRACK_TILT_GAIN` (0.5) times
  its offset (pixel y grows downward, so a person low in the frame tilts the
  camera down). Offsets under `TRACK_DEADBAND_FRACTION` (4 % of the frame) are
  ignored. Between detections the servos *slew* toward the goals at no more
  than `PAN_MAX_DPS` / `TILT_MAX_DPS`, so they glide instead of snapping.
  Goals are clamped to the soft limits.
- **Why the gains are under 1.** The detector is slow (about 3 fps) and each
  measurement is already a few hundred milliseconds old when it arrives, by
  which time the person has moved and the camera too. Correcting the full
  error each time would overshoot and hunt. Under-correcting settles in a few
  detections and costs a little lag on a fast mover.
- **Each detection counts once.** The loop runs at 20 Hz and vision at 3, so
  the tracker moves the goals only on a fresh detection
  ([06 — Vision](../../../docs/design/06-device-software.md#vision-and-why-it-runs-slowly)).
- **Zoom (framing).** The camera starts wide; vision then frames the shot,
  filling 65 % of the frame, with a fast zoom-out guard near the edges and a
  slow relax back to wide when the person isn't seen
  ([06 — Framing and focus](../../../docs/design/06-device-software.md#framing-and-focus)).
- **Focus from size.** There is no distance sensor, so distance is
  *estimated* from how tall the person looks. By the thin lens, a body of
  height H at distance d is f·H/d tall on the sensor; the tracker solves for d
  using the current focal length f, the body's apparent height on the IMX477
  (`SENSOR_H_MM`) and `SUBJECT_HEIGHT_M` = 1.7 m, clamps it to 1–30 m and
  smooths it (`DIST_SMOOTHING` 0.3 per detection), because a person's pose
  changes their apparent height from frame to frame. That `dist` is what the
  app's telemetry shows. It is deliberately a guess about the body: a child or
  a crouching climber reads as farther away than they are. Focus has depth of
  field to spare at the wide end, where the camera spends most of its time, and
  the error matters mainly at full tele. While searching, focus is held at
  `SEARCH_FOCUS_M` (5 m), a room-sized guess.

  Focus then comes from that distance and the focal length, through
  `FOCUS_GRID` ([06](../../../docs/design/06-device-software.md#framing-and-focus)).
- **Detection.** OpenCV HOG on the 720p preview, downscaled to
  `DETECT_DOWNSCALE_W` (480 px) wide, at `DETECT_FPS_TRACKING` (3 fps) while a
  session runs and `DETECT_FPS_IDLE` (0.5) when not. The record stream is
  untouched 1080p. `DETECT_HIT_THRESHOLD` (0.3) is the SVM margin: higher
  gives fewer false people and misses more real ones. **While locked, the
  detector searches only a vertical strip** of `DETECT_STRIP_FRACTION` (60 %)
  of the frame width around the person, which cuts its time several-fold;
  while searching it uses the whole frame.

  Three frames per second sounds slow and is not for a climber, who rises
  at about 1.7°/s seen from 10 m. A runner is another matter.

  **Upgrade path:** if HOG is not good enough, a MobileNet-SSD person detector
  through `cv2.dnn` fits in the same place. Only `Camera._detect()` changes;
  it still returns a list of `(x, y, w, h)`.

## Limitations

Stated plainly, because they decide whether this build suits your use:

- **It cannot tell people apart.** The first person found is the one
  followed; a bystander already in view at that moment may be the one it picks
  (the largest detection wins at first sighting). After a loss and re-search
  the same rule applies, so a person walking between the camera and the subject
  can take the lock. Clear the field of view when you press the button, and
  start from the person you want filmed standing in front.
- **HOG has blind spots.** It is best at upright, side- or front-on people in
  decent light. It struggles with unusual poses (climbing overhangs, a
  horizontal body, crouching), a person seen from behind in a bulky jacket,
  partial occlusion, and poor or contrasty light. It can also false-positive
  on coat stands and similar shapes, which the two-detection lock turns into
  a brief pause, not a recording. Raising `DETECT_HIT_THRESHOLD` trades some
  of one for the other.
- **±80° of pan.** The camera cannot look behind itself and the sweep never
  covers more than the front 160°. Aim the tripod at the area of interest.
- **Distance is an estimate.** Zoom is framed from the person's size on the
  sensor and focus from an assumed 1.7 m body; there is no ranging. Children,
  crouching and long reaches all bias it.
- **Recording starts on the first lock.** If the first person found is not the
  one you wanted, stop recording and tracking from the app and start again.
  With `AUTO_RECORD_ON_LOCK = False` you decide when it starts.
- **Latency.** At 3 fps the camera lags a fast mover. Gains are tuned to avoid
  oscillation rather than to follow a sprinter.

## Camera placement envelope

How far back can the tripod sit? Three constraints, and they bite at
different distances:

1. **Resolution — the zoom is the binding constraint.** At full zoom a 1.8 m
   subject fills the 65 % framing target out to about 8.3 m, 40 % at 13.5 m
   and 18 % at 30 m; full-body framing works from about 1.5 m. The full table
   is in [03 — How far the zoom reaches](../../../docs/design/03-mechanical-design.md#how-far-the-zoom-reaches).
2. **Geometry — closer isn't better.** Inside ~5 m of a tall wall the tilt
   angle gets steep (foreshortened footage) and pan/tilt angular rates spike
   on fast moves. At 8–12 m, a full 15 m route sweeps a comfortable ~50–60°
   of tilt.

3. **Pan range and the search.** The camera only pans ±80°, and it searches
   zoomed all the way out. At 8 m back the sweep is about 22 m wide, which
   covers any bouldering wall and most routes. But at the wide end the frame
   is about 12.5 m tall at 10 m, so a 1.7 m person is only about 14 % of it,
   right at the edge of what HOG finds. **Expect searching to work reliably
   out to roughly 8–10 m**; beyond that, start the person closer (or walk in
   from the side) and let the zoom follow them back out. Aim the lens at the
   middle of what you are filming and give the far ends a check before you
   start.

**Rule of thumb: 6–12 m back is the sweet spot; 2 m to ~20 m works.** Past
13.5 m the subject is simply smaller than the framing target. Past ~30 m the
person is too small for the detector at any zoom.

## Calibration

Nothing about the tracker itself needs calibrating; the lens and the servos
it drives do. The zoom curve, the focus grid, and the centre and direction of
both axes are calibrated the same way in both builds;
[14 — Software setup](../setup/14-software-setup.md#5-calibrate) has the steps.
A wrong `PAN_SIGN` or `TILT_SIGN` makes the camera run away from the subject,
which looks like a tracking failure and isn't one.

## Tuning

Change one parameter at a time and film a short walk or climb after each.
Defaults are in `src/without_uwb/device/sportcam/config.py`.

| Symptom | Likely cause | Adjust |
| --- | --- | --- |
| Camera sweeps past a person, or never stops | detector missing them; sweep too fast; light | lower `DETECT_HIT_THRESHOLD` (0.3 → 0.2), lower `SEARCH_PAN_DPS`; check the preview |
| Locks on to furniture or empty wall | false positives | raise `DETECT_HIT_THRESHOLD`; raise `ACQUIRE_DETECTIONS` to 3 |
| Camera oscillates around the person | gain too high for the detection rate | lower `TRACK_PAN_GAIN` / `TRACK_TILT_GAIN` (0.6 → 0.45); widen `TRACK_DEADBAND_FRACTION` |
| Camera lags a mover and the person drifts out of frame | gain too low | raise the gains toward 0.8; raise `PAN_MAX_DPS`; widen `ZOOM_FILL_TARGET` margin (lower it) |
| Shot "breathes" in and out | zoom too reactive | lower `ZOOM_VISION_GAIN`; raise `ZOOM_MIN_STEP_MM` |
| Person clipped at the edge | fill target too high or guard too late | lower `ZOOM_FILL_TARGET` (0.65 → 0.55); raise `ZOOM_GUARD_EDGE` |
| Bystanders steal the lock | gate too wide | lower `TRACK_GATE_FRACTION` (0.45 → 0.3) |
| Tracking jumps to someone else after a short loss | re-search too eager | raise `RESEARCH_AFTER_S`; lower `TRACK_GATE_FRACTION` |
| Gives up on an empty room too soon, or never | give-up timer | `SEARCH_GIVE_UP_S` |
| Person seen late or missed at the sweep's ends | tilt rows miss them | edit `SEARCH_TILT_ROWS_DEG` for your lens height and room |
| Detector too slow on the Pi | strip too wide | lower `DETECT_STRIP_FRACTION`; lower `DETECT_DOWNSCALE_W` (hurts small, far people) |

## Parameter reference

All in `src/without_uwb/device/sportcam/config.py`.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `CONTROL_RATE_HZ` | 20 | tracker / state-machine tick |
| `DETECT_FPS_TRACKING` / `_IDLE` | 3.0 / 0.5 | detector rate |
| `DETECT_HIT_THRESHOLD` | 0.3 | HOG margin; higher = fewer false people |
| `DETECT_STRIP_FRACTION` | 0.6 | width searched around the person once locked (0 = whole frame) |
| `DETECT_DOWNSCALE_W` | 480 | detector input width, px |
| `PAN_MIN_DEG` / `PAN_MAX_DEG` | −80 / 80 | pan soft limits |
| `TILT_MIN_DEG` / `TILT_MAX_DEG` | −45 / 85 | tilt soft limits |
| `PAN_MAX_DPS` / `TILT_MAX_DPS` | 120 / 90 | servo slew limits |
| `SEARCH_PAN_DPS` | 25 | sweep speed |
| `SEARCH_TILT_ROWS_DEG` | (5, 22) | tilt for each sweep pass |
| `SEARCH_TILT_DPS` | 40 | speed of the step between rows |
| `SEARCH_FOCUS_M` | 5 | focus distance while sweeping |
| `SEARCH_GIVE_UP_S` | 180 | tracking, never found anyone → idle |
| `ACQUIRE_DETECTIONS` | 2 | consecutive centred detections to lock |
| `ACQUIRE_CENTRE_FRACTION` | 0.2 | how close to centre counts as centred |
| `CENTRE_TIMEOUT_S` | 2 | nobody seen while centring → resume sweep |
| `ACQUIRE_STALLED_S` | 15 | searching this long → app says it can't see anyone |
| `TRACK_PAN_GAIN` / `TRACK_TILT_GAIN` | 0.6 / 0.5 | share of the pixel offset corrected per detection |
| `TRACK_DEADBAND_FRACTION` | 0.04 | offsets below this share of the frame are ignored |
| `TRACK_GATE_FRACTION` | 0.45 | max jump (share of frame width) still "the same person" |
| `LOST_HOLD_S` | 2 | target missing → hold and flash the ring |
| `RESEARCH_AFTER_S` | 6 | target missing → sweep again |
| `AUTO_RECORD_ON_LOCK` | True | first lock of a session starts recording |
| `ZOOM_FILL_TARGET` | 0.65 | fraction of the frame the person should fill |
| `ZOOM_VISION_GAIN` | 0.35 | share of the log error corrected per detection |
| `ZOOM_GUARD_FILL` / `_EDGE` / `_STEP` | 0.85 / 0.03 / 0.8 | fast zoom-out guard |
| `ZOOM_STALE_S` / `_RELAX` | 2 / 0.3 | ease back to wide with no detection |
| `SUBJECT_HEIGHT_M` | 1.7 | body height assumed for the distance estimate |
| `DIST_SMOOTHING` | 0.3 | share of each new distance estimate taken |
| `DIST_MIN_M` / `DIST_MAX_M` | 1 / 30 | clamp on the estimate |

The control code is in [`src/without_uwb/device/sportcam/tracker.py`](../../../src/without_uwb/device/sportcam/tracker.py);
session rules in [`session.py`](../../../src/without_uwb/device/sportcam/session.py).
