# 06 — Device software

The camera runs one Python service on the Raspberry Pi: pan, tilt, zoom and
focus, person detection, status ring, recording and upload. It syncs with
Firebase through a Firestore document ([below](#firebase-link)) and serves
phones on its Wi-Fi directly ([09](09-direct-connection-and-app.md)). No
second microcontroller.

| Build | Code | Tracking |
| --- | --- | --- |
| with UWB | [`src/with_uwb/device/`](../../src/with_uwb/device/) | ranges a tag |
| without UWB | [`src/without_uwb/device/`](../../src/without_uwb/device/) | vision search and tracking |

Shared modules first; build-specific modules in <!--both-->[With UWB](#with-uwb) and
[Without UWB](#without-uwb)<!--/--><!--with_uwb: [With UWB](#with-uwb)--><!--without_uwb: [Without UWB](#without-uwb)-->.<!--with_uwb--> The UWB build also has the wearable
tag's firmware.<!--/-->

## Camera service — Raspberry Pi 4 (`src/<build>/device/`)

Python 3.11+; systemd unit `sportcam-head.service`.

| Module | Function |
| --- | --- |
| `main.py` | asyncio supervisor: state handling (including `awake` → `sleep` after `AWAKE_TIMEOUT_S`, held off while an app watches the live view); control, frame and telemetry loops. On SIGTERM (the power switch going off, through systemd) `power_off()` closes any recording, parks the head and darkens the ring before the Pi halts ([04](04-electronics.md#power-switch)) |
| `cloud.py` | Firebase link: Firestore document, app requests, previews ([below](#firebase-link)) |
| `camera.py` | Picamera2: 720p preview (JPEG + person detection); 1080p **hardware** H.264 recording to `/home/pi/recordings`; sensor stopped in `sleep`, with a `CAMERA_WARMUP_S` settle on waking before the first detection |
| `detector.py` | person detectors: HOG, or MobileNet-SSD on `cv2.dnn` (`DETECTOR`), each falling back to the other; boxes always in HOG's padded convention ([below](#vision-and-why-it-runs-slowly)) |
| `getmodel.py` | `python3 -m sportcam.getmodel`: fetches the MobileNet-SSD weights (checksummed) into `models/` |
| `detectbench.py` | bench tool: runs both detectors on the live picture and prints time per frame and hit rate |
| `ptz.py` | PTZ controller at I2C 0x0C: pan, tilt, zoom, focus, soft limits, homing; `jog()` for the app's joystick ([09](09-direct-connection-and-app.md#aiming-by-hand)) |
| `ptzcheck.py` | bench tool: sweeps both axes to their soft limits |
| `led.py` | WS2812B ring over SPI (no root required) |
| `power.py` | battery gauge (INA260, INA226 or none): Wh integration, runtime estimate, low/critical levels |
| `storage.py` | SD free space in minutes of recording; low/critical levels |
| `focuscal.py` | `python3 -m sportcam.focuscal <metres>`: focus sweep at five focal lengths; prints `FOCUS_GRID` |
| `uploader.py` | background upload to the backend: progress, retry, boot-time backlog drain ([08](08-recordings-and-cloud.md)) |
| `boxlog.py` | while recording, the tracker's labelled person boxes from each detection; written beside the clip as `<clip>.boxes.json` and uploaded with it ([08](08-recordings-and-cloud.md#person-boxes)) |
| `wifi_portal.py` | `sportcam-wifi`: tries the saved networks, else pairing: hotspot, setup page and `/api/join`; writes `/run/sportcam-wifi.json` ([08](08-recordings-and-cloud.md#connecting-the-camera-to-gym-wi-fi-from-your-phone)) |
| `wifi_link.py` | the head's side: boot states `connecting` / `pairing` from the status file, Wi-Fi share QR code parser, join request; both report as `off` to apps |
| `local_api.py` | camera-hosted copy of the Firebase API for direct connections ([09](09-direct-connection-and-app.md)) |
| `discovery.py` | mDNS advertisement, `_sportcam._tcp` |
| `config.py` | all tunables, including `TRACKING_MODE` (build name, reported to Firebase and phones) and the Firebase settings (`FIREBASE_PROJECT`, `CAMERA_KEY`, `UPLOAD_API_BASE`) |
| `tracker.py`, `session.py` | present in both builds; build-specific implementations |
| `uwb.py`, `rangecal.py`, `bearingcal.py` | UWB build only |

| Aspect | Detail |
| --- | --- |
| Installation | 14 — Software setup, step 3 onward ([with UWB](../with_uwb/setup/14-software-setup.md), [without UWB](../without_uwb/setup/14-software-setup.md)). Runs from `/home/pi/sportcam/src/<build>/device` |
| Privileges | `sportcam-head` runs as an ordinary user (hence SPI for the LED ring; the PWM/DMA driver needs root). `sportcam-wifi` (portal) runs as root and is the only thing that changes the network; the head reads its QR codes and asks it to join |
| Sleep | `apply_state("sleep")` stops the sensor (`Camera.set_awake(False)`) and parks the head; the frame loop publishes nothing, so there is no live view on either path. The local API, Firebase link, mDNS<!--with_uwb--> and UWB ranging<!--/--><!--both--> (and, with UWB, ranging)<!--/--> stay up to be woken. Live frames go out only in `awake`, `tracking` and `recording` (`LIVE_STATES`) |
| Recording upload | on stop, `main.py` hands the MP4 and its person boxes to `uploader.py` as a background task; tracking and streaming continue. The local copies are deleted after the backend confirms the byte count ([08](08-recordings-and-cloud.md)) |

Live video:

| Path | Mechanism | Latency |
| --- | --- | --- |
| Direct, MJPEG | `camera.py` JPEG-encodes the 720p preview at 15 fps; `local_api.py` serves it | ≈ 250 ms |
| Direct, WebRTC (optional) | [MediaMTX](https://github.com/bluenviron/mediamtx) on the Pi fed H.264 from `rpicam-vid`; set `WHEP_URL` | ≈ 150 ms, no transcode |
| Remote | while an app is watching, `cloud.py` writes 1 frame/s to Firestore | preview only; Cloud Functions can't hold a stream |

### Motion, in one place

`ptz.py` is the only module that drives hardware motion. API in degrees from
centre; hides raw 0–180 servo units, soft limits, the servo driver and the
open-loop zoom calibration. Pan and tilt go out as pigpio hardware PWM on
GPIO12 / GPIO13 (`SERVO_DRIVER = "pigpio"`, fractional degrees) or as the PTZ
controller's whole-degree registers (`"arducam"`, a head wired as the kit
came) — [04 — Servo drive](04-electronics.md#servo-drive):

```python
ptz.set_pan(-12.5)      # degrees from centre (the anchor bar's normal / the enclosure's forward axis)
ptz.set_tilt(18.0)      # degrees above level, at the lens
ptz.set_focus(9.4)      # subject distance in metres; looked up in FOCUS_GRID
ptz.set_zoom_mm(7.4)    # interpolated through config.ZOOM_CURVE, rate-limited
ptz.park()              # centre both axes
```

The tracker commands absolute `set_pan` / `set_tilt` targets every tick,
eased toward its goal: speed proportional to the distance left
(`TRACK_EASE_S`), acceleration-limited, and at most `PAN_MAX_DPS`, so the
video pans smoothly between the detector's few updates a second.

### Vision, and why it runs slowly

A person detector runs on the preview in both builds and sets the framing;
its other roles are build-specific.

| Property | Value | Rationale |
| --- | --- | --- |
| Detector | `DETECTOR = "hog"` (default) or `"ssd"`; if the chosen one can't load, the other is used ([detectors](#the-two-detectors)) | HOG needs no model; SSD finds climbing poses HOG misses |
| Rate | 3 fps (`DETECT_FPS_TRACKING`); 0.5 fps awake | subject motion seen from several metres is slow |
| Search area | vertical strip around the expected column (`Camera.set_search_column()`) once the position is known | several-fold speed-up |
| Freshness | the tracker acts only on a **new** detection | loop 20 Hz vs vision 3 Hz: reusing a cached detection applies it ≈ 7 times and causes hunting |
| Thread | detection runs on its own thread (`Camera._detect_loop`); `person_boxes()` returns at once with the latest result | run inside the 20 Hz tick, a detection froze the servos for a few hundred ms and the motion then lurched to catch up |
| Capture time | each result carries `captured_at`; the tracker logs its pan/tilt every tick and reads offsets against the pose then (`Tracker._pose_at`) | the head keeps easing during a detection; measured against the current pose, that turn is counted twice and the camera overshoots (≈ 1.8° on a 30° move) |

#### The two detectors

| | HOG | MobileNet-SSD (SSDLite-MobileNetV2, COCO) |
| --- | --- | --- |
| Poses | trained on upright pedestrians: misses overhangs, reaches, crouches, back views | trained on everyday photos: handles them |
| People small in the frame | multi-scale over a 480 px image | the input is squeezed to 300×300, so a whole-frame search runs as two overlapping halves (`SSD_WIDE_TILES`); a person across the seam is joined back into one box |
| Speed, Pi 4 | ≈ 3 fps | to be measured with `detectbench` (≈ 150–250 ms a pass expected; the tiled search is two passes) |
| Boxes | padded around the body | hug the body; padded about their centre to HOG's convention (`PERSON_IN_BOX_W/H`), so zoom, focus, the gate and the overlays need no second set of constants |
| Needs | OpenCV 4 (gone from OpenCV 5's main module) | OpenCV 4 or 5 (`cv2.dnn`), and `models/ssdlite_mobilenet_v2_coco.pb` from `getmodel` (19 MB, not in the repo; its `.pbtxt` is) |
| Knobs | `DETECT_DOWNSCALE_W`, `DETECT_HIT_THRESHOLD` (camera-only build) | `SSD_CONFIDENCE`, `SSD_WIDE_TILES` |

HOG stays the default until `detectbench` on the real wall shows SSD at 3 fps
or better with more frames finding the climber ([15 — Verification](../without_uwb/setup/15-verification.md)).

Tests: `src/<build>/device/tests/test_ptz.py` covers the focus lookup and both
servo drivers (pulse widths, fractional degrees, signs, limits);
`test_detector.py` the detectors (which SSD detections count, tiles, the seam
join, box padding, fallback; the real model too once fetched);
`test_camera.py` the detector thread (never blocks the loop, each result
handed over once, an in-flight result dropped on sleep). All
device tests run on any machine (`python3 tests/test_<name>.py`).

### Framing and focus

Shared by both builds; only the initial zoom guess differs (your build's 05).

**Framing** (per fresh detection):

| Step | Parameter | Default |
| --- | --- | --- |
| Measure fill: larger of height and width fraction, on the body rather than the padded detector box | `PERSON_IN_BOX_H`, `PERSON_IN_BOX_W` | 75 %, 55 % of the box |
| Move zoom toward the target, in log terms, by | `ZOOM_VISION_GAIN` | 35 % |
| Target fill (≈ 17 % margin each side) | `ZOOM_FILL_TARGET` | **65 %** |
| **Guard:** body within this of an edge… | `ZOOM_GUARD_EDGE` | 3 % |
| …or filling more than | `ZOOM_GUARD_FILL` | 85 % |
| …zooms out at once by | `ZOOM_GUARD_STEP` | 0.8× |
| **Lost while recording:** no detection for | `LOST_ZOOM_OUT_S` | 2 s |
| …zooms straight out to | `ZOOM_MIN_MM` (wide), past the rate limit | — |
| **Stale relax** (with UWB, before recording): no detection for | `ZOOM_STALE_S` | 2 s |
| …zoom eases back to the distance framing at | `ZOOM_STALE_RELAX` | 30 %/s |
| Rate limit / minimum step (no "breathing") | `ZOOM_RATE_LIMIT_S`, `ZOOM_MIN_STEP_MM` | — |

The guard acts before clipping because the detector can't see a body that
is already clipped. Wider is the safe failure direction: a person lost from
a tight shot is usually still in a wide one, so losing them while recording
zooms straight out to look.

**Focus** from subject distance *and* focal length:

- Depth of field is wide at the wide end and shallow at full zoom (at
  10.6 mm focused at 10 m: ≈ 6–20 m sharp), so a focal-length-only curve is
  soft at most distances.
- `config.FOCUS_GRID`: measured focus positions per focal length per
  distance. `ptz.focus_raw` interpolates in 1/distance (how lens extension
  varies).
- Deadband 0.02 dioptres (≈ ±2 m at 10 m); a zoom move refocuses at once.
- **Shipped grid is flat**: focus follows zoom only until `focuscal` is run.
  `focuscal` sweeps the focus motor at five focal lengths and keeps the
  sharpest position (variance of the Laplacian over the frame centre).

### Status ring

`led.py`, 16 × WS2812B on SPI0 MOSI. Colours per state:
[01 — State machine](../product/01-requirements.md#state-machine); in `sleep`
only one pixel is lit, dimly (`SLEEP_LED_LEVEL`). Overlays:
2 Hz flash for a lost subject while tracking (recording stays solid red); 1 Hz orange blink over the state colour for low
battery or low card space.

## Firebase link

`cloud.py` maintains the Firestore document `cameras/{CAMERA_KEY}`
([07](07-backend-and-app.md#how-the-pieces-talk)). Shared by both
builds<!--with_uwb-->; the UWB build adds `tagPresent` to the telemetry<!--/-->.

```jsonc
// cameras/{CAMERA_KEY} — written by the camera
{ "mode": "with_uwb" | "without_uwb",       // config.TRACKING_MODE
  "state": "off" | "sleep" | "awake" | "tracking" | "recording",   // "off": booting
  "stateBy": "device",                       // "app" when the API wrote a request
  "telemetry": { "pan": -12.5, "tilt": 10.0, "zoomMm": 7.4, "dist": 4.2,
                 "phase": "no-person-in-frame" | "person-in-frame"   // awake
                        | "search" | "found" | "track" | null,      // tracking / recording; sleep, off
                 "countdown": 0,    // found: seconds left before recording (3, 2, 1); apps beep on each
                 "acquireStalled": false,
                 "battery": 0.82, "batteryWatts": 14.6, "batteryMinutes": 191,
                 "batteryLevel": "ok", "storageMinutes": 212, … },
  "deviceSeenAt": <server time>,             // heartbeat, every HEARTBEAT_S (5 s)
  "whepUrl": null,                           // config.WHEP_URL
  "upload": { "name": "rec_….mp4", "sent": 12345, "total": 99999 } | null }
// written by the API
{ "state": "tracking", "stateBy": "app" }   // an app's request
{ "viewerAt": <server time> }               // an app is watching
// cameras/{CAMERA_KEY}/live/preview — written by the camera while watched
{ "jpeg": <bytes>, "at": <server time> }
```

| Behaviour | Detail |
| --- | --- |
| State ownership | the camera owns its state. On connect it writes its state first, so a recording started offline survives reconnection |
| App requests | the listener adopts any state written with `stateBy: "app"`, applies it via `apply_state()` (same path as a direct command), and writes back the result |
| Camera-initiated changes | found for 3 s starting a recording, low battery, build-specific events: written immediately |
| Write throttling (free tier) | telemetry on the heartbeat (sooner on a phase change, so the apps can ping while searching, and on each second of `countdown` so they can beep on it); upload progress every 2 s; previews only while `viewerAt` < 60 s old |
| Credentials | service account restricted to Firestore (`FIREBASE_CREDENTIALS`) |
| Stand-alone | `CAMERA_KEY` empty: no Firebase connection |
| `pan` | degrees from centre, negative = left; no 0–360 heading (axis range ±80°) |

---

## With UWB

Programs: camera service and wearable tag firmware.

### Modules, with UWB

| Module | Function |
| --- | --- |
| `uwb.py` | range parsing (ULA1 frames, or the `dual-serial` sketch), bearing maths, Kalman → (θ, d) |
| `tracker.py` | SEARCH → FOUND → TRACK state machine and control loops from [05](../with_uwb/design/05-tracking-system.md): awake person-in-frame watch (`watch_awake()`, for the LED and app only: a session always starts in SEARCH), turn to the ranged position, the tag-wearer match (`_match_tag()`: only the person where the tag is counts), pan/tilt from ranging, CV bias trims, framing, focus from distance |
| `session.py` | tag-driven sessions: tag on → tracking (search → found) → recording after 3 s found; tag off → awake ([01](../product/01-requirements.md#state-machine-with-uwb)) |
| `rangecal.py` | `python3 -m sportcam.rangecal <metres>`: per-anchor range bias and noise with the tag on the boresight; prints `RANGE_BIAS_M` |
| `bearingcal.py` | `python3 -m sportcam.bearingcal <metres>`: the filtered bearing's noise and correlation time with the wearer standing on the boresight; prints `TAG_BEARING_SIGMA_DEG` and `TAG_BEARING_CORR_S` |

`config.py` additionally holds the anchor geometry and calibration biases
([05 — Calibration](../with_uwb/design/05-tracking-system.md#calibration)).

### Vision, with UWB

- `Camera.person_boxes()` returns `(boxes, fresh)`: every person the detector sees, so the tracker can pick out the tag wearer. `person_bbox()` returns the largest.
- The tracker converts the ranged bearing into the pixel column the detector
  searches around.
- Vision's roles (angle trim, framing, confirming the person before recording) and hold-on-dropout
  behaviour: [05](../with_uwb/design/05-tracking-system.md#control-loops-all-run-on-the-pi-20-hz).

Tests: `src/with_uwb/device/tests/test_tracker.py` (fresh-only rule, strip
hint, slew limits, tilt from A3, sign of every vertical correction, framing:
fill target, edge guard, stale relax); `test_session.py` (SEARCH →
FOUND → recording after 3 s, always SEARCH first, tag-driven sessions, the
tag wearer picked out from bystanders, someone nearer the lens and a belayer
beside them, each box labelled green, yellow or red, one telemetry push per
countdown second, the boxes saved beside the clip, stop recording → awake).

### Where ranges come from

`config.UWB_PROTOCOL` selects the radio stack:

| Protocol | Hardware | Format | Notes |
| --- | --- | --- | --- |
| **`ula1`** | Haorutech ULA1, vendor RTLS firmware | one anchor on USB forwards each RangeData frame: `mc <mask> <r0> <r1> <r2> <r3> …`, ranges in **hex millimetres** behind a validity mask; RANGE0–2 = A1–A3 | one timestamp per frame (as the maths assumes); one USB data connection. A frame without A3 gives bearing but no elevation |
| **`dual-serial`** | one port per anchor running our DS-TWR sketch ([`src/with_uwb/firmware/uwb_anchor/`](../../src/with_uwb/firmware/uwb_anchor/)) | `R,<tag>,<range_m>` | vendor-agnostic; ranges are independent samples |

`ula1` requires the vendor's **`RTLS_Tag` / `RTLS_Anchor`** sketches; the
`Ranging` pair reports one distance at a time. One range where three are
expected = wrong pair loaded: reflash
([14, step 1](../with_uwb/setup/14-software-setup.md#1-flash-the-radios-on-your-computer))
or use `dual-serial`.

Tests: `src/with_uwb/device/tests/test_uwb.py` parses the manual's worked
example; checks the mask, hex scaling, bearing geometry and elevation solve
(exact to 0.01° across the envelope, including A3's backward offset),
`rangecal`'s bias, and `bearingcal`'s σ and τ, including that the
`TAG_BEARING_*` defaults match what the Kalman filter does at this baseline.

### Wearable tag — ULA1 (`src/with_uwb/wearable/`)

| Item | Detail |
| --- | --- |
| Hardware | ULA1, vendor `RTLS_Tag` firmware, USB bank power |
| Function | ranges each anchor in turn; broadcasts the results |
| Controls | none; power on/off is the session control |
| Optional sketch | `src/with_uwb/wearable/tag_firmware/`: Makerfabs ESP32-UWB board with a pair/record button, sent over BLE as `SPORTCAM-BTN:<kind>` and relayed as `tagButton`. Not ported to the ULA1 (needs the free pins from the vendor schematic) |

### Firebase link, with UWB

- `tagPresent` (telemetry): tag on and ranging.
- Camera-initiated state changes: tag on → session start; tag absent >
  `LOST_END_S` → awake (clip saved).

---

## Without UWB

Programs: camera service only.

### Modules, without UWB

| Module | Function |
| --- | --- |
| `tracker.py` | SEARCH → FOUND → TRACK state machine and loops from [05](../without_uwb/design/05-tracking-system.md): awake person-in-frame watch (`watch_awake()`; a session starts in FOUND when someone is in frame), sweep, first person found, followed with a gate, pan/tilt goals and slew, vision-only framing, focus from apparent size |
| `session.py` | `AutoSession`: found for 3 s starts recording; a tracking session sweeping 180 s without finding anyone gives up ([01](../product/01-requirements.md#state-machine-without-uwb)) |

`config.py` additionally holds the search and tracking gains, detector
settings, and zoom and focus curves. `camera.py` adds `person_boxes()`.

### Vision, without UWB

- Vision is the only sensor.
- `Camera.person_boxes()` returns `(boxes, fresh)`: every detection as
  `(x, y, w, h)` and whether the list is new.
- Detector isolated in `Camera._detect()`; replacing HOG with MobileNet-SSD
  (`cv2.dnn`) changes only that method.
- Tracker use of the boxes (search, found, following, framing, focus from
  size): [05](../without_uwb/design/05-tracking-system.md#control-loops-all-run-on-the-pi-20-hz).

Tests: `src/without_uwb/device/tests/test_tracker.py` (awake sub-state and
sweep skip, sweep and turn-arounds, found → ready after 3 s, bystander gate, correction signs, slew
limits, framing: fill target, edge guard, stale relax); `test_session.py`
(recording after 3 s found, give-up rule, awake → FOUND with a person in frame,
one telemetry push per countdown second, stop recording → awake).

### Firebase link, without UWB

| Field / event | Meaning |
| --- | --- |
| `dist` | estimated from the person's size in frame; null while searching |
| `acquireStalled` | search has found nobody for `ACQUIRE_STALLED_S` |
| Camera-initiated changes | found for 3 s starting a recording; empty-room give-up |
