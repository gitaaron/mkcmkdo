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
| `main.py` | asyncio supervisor: state handling; control, frame and telemetry loops |
| `cloud.py` | Firebase link: Firestore document, app requests, previews ([below](#firebase-link)) |
| `camera.py` | Picamera2: 720p preview (JPEG + person detection); 1080p **hardware** H.264 recording to `/home/pi/recordings` |
| `ptz.py` | PTZ controller at I2C 0x0C: pan, tilt, zoom, focus, soft limits, homing |
| `ptzcheck.py` | bench tool: sweeps both axes to their soft limits |
| `led.py` | WS2812B ring over SPI (no root required) |
| `power.py` | battery gauge (INA260, INA226 or none): Wh integration, runtime estimate, low/critical levels |
| `storage.py` | SD free space in minutes of recording; low/critical levels |
| `focuscal.py` | `python3 -m sportcam.focuscal <metres>`: focus sweep at five focal lengths; prints `FOCUS_GRID` |
| `uploader.py` | background upload to the backend: progress, retry, boot-time backlog drain ([08](08-recordings-and-cloud.md)) |
| `wifi_portal.py` | hotspot and captive setup page when offline ([08](08-recordings-and-cloud.md)) |
| `local_api.py` | camera-hosted copy of the Firebase API for direct connections ([09](09-direct-connection-and-app.md)) |
| `discovery.py` | mDNS advertisement, `_sportcam._tcp` |
| `config.py` | all tunables, including `TRACKING_MODE` (build name, reported to Firebase and phones) and the Firebase settings (`FIREBASE_PROJECT`, `CAMERA_KEY`, `UPLOAD_API_BASE`) |
| `tracker.py`, `session.py` | present in both builds; build-specific implementations |
| `uwb.py`, `rangecal.py` | UWB build only |

| Aspect | Detail |
| --- | --- |
| Installation | 14 — Software setup, step 3 onward ([with UWB](../../with_uwb/docs/setup/14-software-setup.md), [without UWB](../../without_uwb/docs/setup/14-software-setup.md)). Runs from `/home/pi/sportcam/src/<build>/device` |
| Privileges | `sportcam-head` runs as an ordinary user (hence SPI for the LED ring; the PWM/DMA driver needs root). `sportcam-wifi` (portal) runs as root |
| Recording upload | on stop, `main.py` hands the MP4 to `uploader.py` as a background task; tracking and streaming continue. The local copy is deleted after the backend confirms the byte count ([08](08-recordings-and-cloud.md)) |

Live video:

| Path | Mechanism | Latency |
| --- | --- | --- |
| Direct, MJPEG | `camera.py` JPEG-encodes the 720p preview at 15 fps; `local_api.py` serves it | ≈ 250 ms |
| Direct, WebRTC (optional) | [MediaMTX](https://github.com/bluenviron/mediamtx) on the Pi fed H.264 from `rpicam-vid`; set `WHEP_URL` | ≈ 150 ms, no transcode |
| Remote | while an app is watching, `cloud.py` writes 1 frame/s to Firestore | preview only; Cloud Functions can't hold a stream |

### Motion, in one place

`ptz.py` is the only module that drives hardware motion. API in degrees from
centre; hides raw 0–180 servo units, soft limits and the open-loop zoom
calibration:

```python
ptz.set_pan(-12.5)      # degrees from centre (the anchor bar's normal / the enclosure's forward axis)
ptz.set_tilt(18.0)      # degrees above level, at the lens
ptz.set_focus(9.4)      # subject distance in metres; looked up in FOCUS_GRID
ptz.set_zoom_mm(7.4)    # interpolated through config.ZOOM_CURVE, rate-limited
ptz.park()              # centre both axes
```

The tracker commands absolute `set_pan` / `set_tilt` targets every tick,
slew-limited to `PAN_MAX_DPS`.

### Vision, and why it runs slowly

A person detector runs on the preview in both builds and sets the framing;
its other roles are build-specific.

| Property | Value | Rationale |
| --- | --- | --- |
| Rate | 3 fps (`DETECT_FPS_TRACKING`); 0.5 fps idle | subject motion seen from several metres is slow |
| Search area | vertical strip around the expected column (`Camera.set_search_column()`) once the position is known | several-fold speed-up |
| Freshness | the tracker acts only on a **new** detection | loop 20 Hz vs vision 3 Hz: reusing a cached detection applies it ≈ 7 times and causes hunting |

Tests: `src/<build>/device/tests/test_ptz.py` covers the focus lookup. All
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
| **Stale relax:** no detection for | `ZOOM_STALE_S` | 2 s |
| …zoom widens at | `ZOOM_STALE_RELAX` | 30 %/s |
| Rate limit / minimum step (no "breathing") | `ZOOM_RATE_LIMIT_S`, `ZOOM_MIN_STEP_MM` | — |

The guard acts before clipping because the detector can't see a body that
is already clipped. Relaxing wider is the safe failure direction.

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
[01 — State machine](../product/01-requirements.md#state-machine). Overlays:
2 Hz flash for a lost subject; 1 Hz orange blink over the state colour for low
battery or low card space.

## Firebase link

`cloud.py` maintains the Firestore document `cameras/{CAMERA_KEY}`
([07](07-backend-and-app.md#how-the-pieces-talk)). Shared by both
builds<!--with_uwb-->; the UWB build adds `tagPresent` to the telemetry<!--/-->.

```jsonc
// cameras/{CAMERA_KEY} — written by the camera
{ "mode": "with_uwb" | "without_uwb",       // config.TRACKING_MODE
  "state": "off" | "idle" | "tracking" | "recording",
  "stateBy": "device",                       // "app" when the API wrote a request
  "telemetry": { "pan": -12.5, "tilt": 10.0, "zoomMm": 7.4, "dist": 4.2,
                 "phase": "no-person-in-frame" | "person-in-frame"   // idle
                        | "acquiring" | "acquired" | null,          // tracking / recording; off
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
| Camera-initiated changes | lock-on starting a recording, low battery, build-specific events: written immediately |
| Write throttling (free tier) | telemetry on the heartbeat (sooner on a phase change); upload progress every 2 s; previews only while `viewerAt` < 60 s old |
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
| `tracker.py` | control loops from [05](../../with_uwb/docs/design/05-tracking-system.md): pan/tilt from ranging, CV bias trims, framing, focus from distance, lock-on test |
| `session.py` | tag-driven sessions: tag on → tracking (acquiring) → recording on lock-on; tag off → idle ([01](../product/01-requirements.md#state-machine-with-uwb)) |
| `rangecal.py` | `python3 -m sportcam.rangecal <metres>`: per-anchor range bias and noise with the tag on the boresight; prints `RANGE_BIAS_M` |

`config.py` additionally holds the anchor geometry and calibration biases.

Range bias calibration is required with the 250 mm mast (a few cm of A3 bias
≈ 10° of tilt). Run after `ptzcheck`, tag 5.00 m out on the boresight:

```bash
cd ~/sportcam/src/with_uwb/device && python3 -m sportcam.rangecal 5
```

### Vision, with UWB

- `Camera.person_bbox()` returns `(bbox, fresh)`.
- The tracker converts the ranged bearing into the pixel column the detector
  searches around.
- Vision's roles (angle trim, framing, lock-on confirmation) and hold-on-dropout
  behaviour: [05](../../with_uwb/docs/design/05-tracking-system.md#control-loops-all-run-on-the-pi-20-hz).

Tests: `src/with_uwb/device/tests/test_tracker.py` (fresh-only rule, strip
hint, slew limits, tilt from A3, sign of every vertical correction, framing:
fill target, edge guard, stale relax); `test_session.py` (lock-on,
tag-driven sessions).

### Where ranges come from

`config.UWB_PROTOCOL` selects the radio stack:

| Protocol | Hardware | Format | Notes |
| --- | --- | --- | --- |
| **`ula1`** | Haorutech ULA1, vendor RTLS firmware | one anchor on USB forwards each RangeData frame: `mc <mask> <r0> <r1> <r2> <r3> …`, ranges in **hex millimetres** behind a validity mask; RANGE0–2 = A1–A3 | one timestamp per frame (as the maths assumes); one USB data connection. A frame without A3 gives bearing but no elevation |
| **`dual-serial`** | one port per anchor running our DS-TWR sketch ([`src/with_uwb/firmware/uwb_anchor/`](../../src/with_uwb/firmware/uwb_anchor/)) | `R,<tag>,<range_m>` | vendor-agnostic; ranges are independent samples |

`ula1` requires the vendor's **`RTLS_Tag` / `RTLS_Anchor`** sketches; the
`Ranging` pair reports one distance at a time. One range where three are
expected = wrong pair loaded: reflash
([14, step 1](../../with_uwb/docs/setup/14-software-setup.md#1-flash-the-radios-on-your-computer))
or use `dual-serial`.

Tests: `src/with_uwb/device/tests/test_uwb.py` parses the manual's worked
example; checks the mask, hex scaling, bearing geometry and elevation solve
(exact to 0.01° across the envelope, including A3's backward offset).

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
  `LOST_IDLE_S` → idle (clip saved).

---

## Without UWB

Programs: camera service only.

### Modules, without UWB

| Module | Function |
| --- | --- |
| `tracker.py` | SEARCH → CENTRE → TRACK state machine and loops from [05](../../without_uwb/docs/design/05-tracking-system.md): idle person-in-frame watch (`watch_idle()`; a session starts in CENTRE when someone is in frame), sweep, first-person lock-on with gate, pan/tilt goals and slew, vision-only framing, focus from apparent size |
| `session.py` | `AutoSession`: first lock of a session started from idle starts recording; a tracking session with nobody found gives up after 180 s ([01](../product/01-requirements.md#state-machine-without-uwb)) |

`config.py` additionally holds the search and tracking gains, detector
settings, and zoom and focus curves. `camera.py` adds `person_boxes()`.

### Vision, without UWB

- Vision is the only sensor.
- `Camera.person_boxes()` returns `(boxes, fresh)`: every detection as
  `(x, y, w, h)` and whether the list is new.
- Detector isolated in `Camera._detect()`; replacing HOG with MobileNet-SSD
  (`cv2.dnn`) changes only that method.
- Tracker use of the boxes (search, lock-on, following, framing, focus from
  size): [05](../../without_uwb/docs/design/05-tracking-system.md#control-loops-all-run-on-the-pi-20-hz).

Tests: `src/without_uwb/device/tests/test_tracker.py` (idle sub-state and
sweep skip, sweep and turn-arounds, two-detection lock, bystander gate, correction signs, slew
limits, framing: fill target, edge guard, stale relax); `test_session.py`
(auto-record on lock, give-up rule, idle → CENTRE with a person in frame).

### Firebase link, without UWB

| Field / event | Meaning |
| --- | --- |
| `dist` | estimated from the person's size in frame; null while searching |
| `acquireStalled` | search has found nobody for `ACQUIRE_STALLED_S` |
| Camera-initiated changes | first lock-on starting a recording; empty-room give-up |
