# 06 — Device software

Everything the camera does runs as one Python service on the Raspberry Pi:
pan, tilt, zoom and focus, the person detector, the status ring, recording
and upload. It talks to Firebase through its own Firestore document
([below](#firebase-link)) and serves phones on its Wi-Fi directly
([09](09-direct-connection-and-app.md)). There is no second microcontroller.

The Pi software is **per build**, because it drives different hardware: <!--with_uwb-->[`src/with_uwb/device/`](../../src/with_uwb/device/) ranges a tag<!--/--><!--both-->;<!--/--> <!--without_uwb-->[`src/without_uwb/device/`](../../src/without_uwb/device/) sweeps and tracks by vision<!--/-->.
Most modules are the same in both; this doc covers those first, then <!--both-->each
build's own modules in its section ([With UWB](#with-uwb),
[Without UWB](#without-uwb))<!--/--><!--with_uwb: the build's own modules in [With UWB](#with-uwb)--><!--without_uwb: the build's own modules in [Without UWB](#without-uwb)-->.<!--with_uwb--> The UWB build also runs a second program, on the
wearable tag.<!--/-->

## Camera service — Raspberry Pi 4 (`src/<build>/device/`)

Python 3.11+, systemd unit `sportcam-head.service`. Modules common to both
builds:

| Module | Job |
| --- | --- |
| `main.py` | asyncio supervisor: state handling, control/frame/telemetry loops |
| `cloud.py` | the Firebase link: the camera's Firestore document, app requests, previews ([below](#firebase-link)) |
| `camera.py` | Picamera2: 720p preview (JPEG + person-detect) and 1080p **hardware** H.264 recording to `/home/pi/recordings` |
| `ptz.py` | the whole PTZ controller at I2C 0x0C: pan, tilt, zoom, focus, soft limits, homing |
| `ptzcheck.py` | bench tool — sweeps both axes to their limits so you can set `config` before filming |
| `led.py` | WS2812B status ring over SPI, so nothing needs to run as root |
| `power.py` | battery gauge (INA260 or INA226, or none): watt-hour integration, runtime estimate, low/critical levels |
| `storage.py` | SD-card space in minutes of recording left, with the same low/critical treatment |
| `focuscal.py` | `python -m sportcam.focuscal <metres>` — sweeps the focus motor at five focal lengths and prints a `FOCUS_GRID` |
| `uploader.py` | background recording upload → backend, with progress, retry, and a boot-time drain of anything stranded ([08](08-recordings-and-cloud.md)) |
| `wifi_portal.py` | hotspot + captive setup page when offline, for gym Wi-Fi ([08](08-recordings-and-cloud.md)) |
| `local_api.py` | the camera-hosted copy of the Firebase API, for phones connecting directly ([09](09-direct-connection-and-app.md)) |
| `discovery.py` | mDNS advertisement as `_sportcam._tcp` |
| `config.py` | all tunables, including `TRACKING_MODE` (this build's name, reported to Firebase and phones) and the Firebase settings (`FIREBASE_PROJECT`, `CAMERA_KEY`, `UPLOAD_API_BASE`) |

`tracker.py` and `session.py` exist in both but differ completely<!--with_uwb-->, and the UWB
build adds `uwb.py` and `rangecal.py`<!--/--> — see <!--both-->the build sections<!--/--><!--with_uwb: [With UWB](#with-uwb)--><!--without_uwb: [Without UWB](#without-uwb)-->.

**Installing it** is step 3 onward of your build's 14 — Software setup
([with UWB](../../with_uwb/docs/setup/14-software-setup.md),
[without UWB](../../without_uwb/docs/setup/14-software-setup.md)). The Pi
clones the whole repo and runs the service from
`/home/pi/sportcam/src/<build>/device`. The service runs as an ordinary
user, which is why the LED ring is driven over SPI rather than the PWM/DMA
driver (that one needs root). The Wi-Fi portal is a separate service that
runs as root.

**After a recording stops**, `main.py` hands the finished MP4 to
`uploader.py` as a background task, so tracking and live streaming carry on.
The uploader sends it to Firebase (`UPLOAD_API_BASE`) and deletes the local
copy once the backend confirms the byte count
([08](08-recordings-and-cloud.md)).

**Live video** goes out two ways:

- **On the camera's Wi-Fi**: `camera.py` JPEG-encodes the 720p preview at
  15 fps and `local_api.py` serves it as MJPEG to phones connected directly.
  ~250 ms latency. Or run [MediaMTX](https://github.com/bluenviron/mediamtx)
  on the Pi, feed it H.264 via `rpicam-vid`, and set `WHEP_URL`: the app
  plays WebRTC from the Pi, ~150 ms, no transcode.
- **From anywhere**: while an app is watching, `cloud.py` posts one frame a
  second to Firestore. A preview, not a stream — Cloud Functions can't hold
  a video connection open, and nothing else runs in the cloud.

### Motion, in one place

`ptz.py` is the only module that moves anything. It exposes angles in degrees
from centre and hides the controller's raw 0–180 servo units, the soft limits,
and the open-loop zoom calibration:

```python
ptz.set_pan(-12.5)      # degrees from centre (the anchor bar's normal / the enclosure's forward axis)
ptz.set_tilt(18.0)      # degrees above level, at the lens
ptz.set_focus(9.4)      # subject distance in metres; looked up in FOCUS_GRID
ptz.set_zoom_mm(7.4)    # interpolated through config.ZOOM_CURVE, rate-limited
ptz.park()              # centre both axes
```

The tracker calls `set_pan` / `set_tilt` with an absolute target each tick,
slew-limited to `PAN_MAX_DPS` so the servo glides between frames instead of
snapping.

### Vision, and why it runs slowly

Both builds run a person detector on the preview, and in both it frames the
shot (zooming until the person fills 65 % of the frame, and out fast if they
near an edge). What else it does depends on the build. None of it needs to be
fast, but it needs to be steady:

- **It runs at 3 fps**, dropping to 0.5 when idle. A person moves slowly
  seen from several metres.
- **It searches a vertical strip, not the frame,** once the tracker knows
  roughly where the subject is: the tracker hands a pixel column to
  `Camera.set_search_column()`, a several-fold saving.

The control loop runs at 20 Hz and vision at 3, so acting on a cached
detection every tick would apply one measurement about seven times over and
make the camera hunt. The tracker acts only on a **fresh** detection.
`src/<build>/device/tests/test_ptz.py` covers the focus lookup in both builds; all device
tests run on any machine (`python3 tests/test_<name>.py`).

### Framing and focus

Both builds frame the shot and focus the same way; only the first guess
differs (see your build's 05).

- **Framing.** Each fresh detection measures how much of the frame the person
  fills: the larger of their height and width fractions, measured on the body
  rather than the padded detector box (`PERSON_IN_BOX_H` 75 % of its height,
  `PERSON_IN_BOX_W` 55 % of its width). The zoom then moves `ZOOM_VISION_GAIN`
  (35 %) of the way, in log terms, toward `ZOOM_FILL_TARGET` (**65 %**). That
  leaves about 17 % of the frame as margin on every side for aim error and
  sudden moves; a climber stretched sideways is framed by their span.
  - **Guard.** If the body comes within `ZOOM_GUARD_EDGE` (3 %) of any edge,
    or fills more than `ZOOM_GUARD_FILL` (85 %), the zoom steps out by
    `ZOOM_GUARD_STEP` (0.8) at once, whatever the fill loop says. The
    detector can't see a body that is already clipped, so the guard acts on
    the approach.
  - **Stale relax.** With no detection for `ZOOM_STALE_S` (2 s) — an
    overhang, a turned back — the zoom eases wider at `ZOOM_STALE_RELAX`
    (30 %) per second. Wider is the safe direction.

  Zoom moves are rate-limited (`ZOOM_RATE_LIMIT_S`) and ignore changes under
  `ZOOM_MIN_STEP_MM`, so the shot doesn't "breathe".
- **Focus** comes from the subject's distance *and* the focal length. Depth
  of field is generous at the wide end and shallow at full zoom (focused at
  10 m at 10.6 mm, roughly 6–20 m is sharp), so a curve keyed on focal length
  alone is soft at most distances. `config.FOCUS_GRID` holds measured focus
  positions per focal length per distance, and `ptz.focus_raw` interpolates
  between them in 1/distance, which is how lens extension actually varies. A
  deadband of 0.02 dioptres (about ±2 m at 10 m) keeps the motor still on
  distance noise, and a zoom move refocuses at once. **The shipped grid is
  flat**, so focus follows zoom alone until you run `focuscal`, which sweeps
  the focus motor at five focal lengths and keeps the sharpest position
  (variance of the Laplacian over the frame centre).

### Status ring

`led.py` drives the 16 × WS2812B ring over SPI0 MOSI, showing the colours in
[01 — State machine](../product/01-requirements.md#state-machine): a 2 Hz
flash for a lost subject, and an orange blink once a second over the state's
colour for low battery or a nearly full card.

## Firebase link

`cloud.py` keeps one Firestore document current, `cameras/{CAMERA_KEY}`
([07](07-backend-and-app.md#how-the-pieces-talk)). It is common to both
builds<!--with_uwb-->; the UWB build adds `tagPresent` to the telemetry<!--/-->.

```jsonc
// cameras/{CAMERA_KEY} — written by the camera
{ "mode": "with_uwb" | "without_uwb",       // config.TRACKING_MODE
  "state": "off" | "idle" | "tracking" | "recording",
  "stateBy": "device",                       // "app" when the API wrote a request
  "telemetry": { "pan": -12.5, "tilt": 10.0, "zoomMm": 7.4, "dist": 4.2,
                 "phase": "acquiring" | "acquired" | null, "acquireStalled": false,
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

The camera owns its state. On connecting it writes its state first, so a
recording started at the gym with no internet survives the link coming back.
Its listener adopts any state written with `stateBy: "app"`, runs it through
`apply_state()` like a command from a phone connected directly, and writes
back what it did. Its own changes — a lock-on starting a recording, low
battery, and the build-specific ones below — are written straight away.

Writes are throttled to stay inside the free tier: telemetry rides on the
heartbeat (sooner on a phase change), upload progress every 2 s, previews
only while `viewerAt` is under a minute old. The camera signs in with a
service account that may only use Firestore (`FIREBASE_CREDENTIALS`); with no
`CAMERA_KEY` set it doesn't connect at all and runs stand-alone.

`pan` is degrees from centre (negative is left). The axis turns ±80°, so
there is no 0–360 heading.

---

## With UWB

Two programs run on the hardware: the camera and the wearable.

### Modules, with UWB

| Module | Job |
| --- | --- |
| `uwb.py` | parses ranges from the radio (ULA1 frames, or our own two-serial sketch), bearing maths + Kalman → (θ, d) |
| `tracker.py` | loops from [05](../../with_uwb/docs/design/05-tracking-system.md): pan and tilt positions from ranging, CV bias trims, vision framing (zoom to fill 65 % of the frame), focus from distance, and the lock-on test |
| `session.py` | tag-driven sessions: tag on → tracking (acquiring) → recording on lock-on; tag off → idle ([01](../product/01-requirements.md#a-session-with-uwb)) |
| `rangecal.py` | `python -m sportcam.rangecal <metres>` — with the tag taped on the boresight, measures each anchor's range bias and noise and prints a `RANGE_BIAS_M` |

`config.py` also carries the anchor geometry and calibration biases.

After `ptzcheck`, with the tag taped 5.00 m out on the boresight, measure each
anchor's range bias. With the 250 mm mast this is not optional: a few
centimetres on A3 is ten degrees of tilt.

```bash
cd ~/sportcam/src/with_uwb/device && python3 -m sportcam.rangecal 5
```

### Vision, with UWB

`Camera.person_bbox()` returns `(bbox, fresh)`, and the tracker turns the
ranged bearing into the pixel column the detector searches around. What
vision does in this build — trimming the ranged angles, framing, and
confirming lock-on — and why the camera holds rather than chasing a
bystander when ranging drops out, is in
[05](../../with_uwb/docs/design/05-tracking-system.md#control-loops-all-run-on-the-pi-20-hz).

`src/with_uwb/device/tests/test_tracker.py` covers the fresh-only rule, the
strip hint, the slew limits, tilt from the third anchor, the sign of every
vertical correction, and vision framing (fill target, edge guard, stale
relax). `test_session.py` covers lock-on and the tag-driven session flow.

### Where ranges come from

`config.UWB_PROTOCOL` picks the radio stack, and the two differ in shape:

- **`ula1`** — Haorutech ULA1. The tag polls each anchor and broadcasts one
  RangeData frame; a single anchor plugged into the Pi forwards it as
  `mc <mask> <r0> <r1> <r2> <r3> …`, ranges in **hexadecimal millimetres**
  behind a validity mask. RANGE0–2 are A1–A3. They share a timestamp, which
  is what the angle maths assumes. One USB data connection, not three. A
  frame missing only A3 still gives a bearing; it just carries no elevation.

  Only the vendor's **`RTLS_Tag` / `RTLS_Anchor`** sketches produce that
  frame; the `Ranging` pair reports one distance at a time. A stream carrying
  one range where three are expected means the wrong pair is loaded: reflash
  ([14 — Software setup, step 1](../../with_uwb/docs/setup/14-software-setup.md#1-flash-the-radios-on-your-computer))
  or switch to `dual-serial`.
- **`dual-serial`** — one port per anchor running our own DS-TWR sketch
  ([`src/with_uwb/firmware/uwb_anchor/`](../../src/with_uwb/firmware/uwb_anchor/)),
  printing `R,<tag>,<range_m>`. Vendor-agnostic, but the ranges are
  independent samples.

`src/with_uwb/device/tests/test_uwb.py` parses the manual's own worked example and
checks the mask, the hex scaling, the bearing geometry, and the elevation
solve — exact to 0.01° across the whole envelope with A3's backward offset
in. It runs anywhere.

### Wearable tag — ULA1 (`src/with_uwb/wearable/`)

The tag is a ULA1 module running the vendor's `RTLS_Tag` firmware, powered
by a small USB bank. It ranges against each anchor in turn and broadcasts the
results. It has no buttons: switching it on and off is the remote control.

`src/with_uwb/wearable/tag_firmware/` is an optional sketch for a Makerfabs
ESP32-UWB board that adds a pair/record button, sent over BLE as
`SPORTCAM-BTN:<kind>` and relayed by the camera as `tagButton`. It isn't
ported to the ULA1; that needs the free pins from the vendor's schematic.

### Firebase link, with UWB

`tagPresent` in the telemetry says the wearable is switched on and ranging.
The tag switching on (a session starts) or staying gone past `LOST_IDLE_S`
(back to idle, saving the clip) are state changes the camera makes itself and
writes like any other.

---

## Without UWB

One program runs on the hardware: the camera service. There is no wearable.

### Modules, without UWB

| Module | Job |
| --- | --- |
| `tracker.py` | the SEARCH → CENTRE → TRACK state machine and control loops from [05](../../without_uwb/docs/design/05-tracking-system.md): sweep, first-person lock-on with a gate, pan/tilt goals and slew, vision-only zoom framing, focus from apparent size |
| `session.py` | `AutoSession`: the first lock of a session that began in idle starts recording; a tracking session that never found anyone gives up after 180 s ([01](../product/01-requirements.md#a-session-without-uwb)) |

`config.py` also carries the search and tracking gains, the detector settings,
and the zoom and focus curves. `camera.py` adds `person_boxes()`, which
returns every detected person.

### Vision, without UWB

Vision is the only sensor. `Camera.person_boxes()` returns `(boxes, fresh)`:
every detected person as `(x, y, w, h)`, and whether this list is a new
measurement. The detector itself is isolated in `Camera._detect()`, so
swapping HOG for a MobileNet-SSD through `cv2.dnn` changes that method and
nothing else. How the tracker uses the boxes — search, lock-on, following,
framing and focus from size — is in
[05](../../without_uwb/docs/design/05-tracking-system.md#control-loops-all-run-on-the-pi-20-hz).

`src/without_uwb/device/tests/test_tracker.py` covers the sweep and its
turn-arounds, the two-detection lock, the gate against bystanders, the sign
of every correction, the slew limits, and vision framing (fill target, edge
guard, stale relax). `test_session.py` covers auto-record on lock and the
give-up rule.

### Firebase link, without UWB

No additions. `dist` in the telemetry is estimated from the person's size in
frame (null while searching), and `acquireStalled` means the search has found
nobody for a while. The head's own state changes are the first lock-on
starting a recording and an empty-room give-up.
