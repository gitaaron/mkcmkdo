# 05 — Device software

The base controller is gone: with no pan stepper there is nothing for a
second microcontroller to do, so pan, tilt, zoom, focus, the status ring and
the person detector all live on the Pi. The camera speaks the WebSocket
protocol to the server (`/ws/device`), documented below and in
[06 — Server & app](06-server-and-app.md).

The Pi software is **per build**, because it drives different hardware:
[`with_uwb/device/`](../with_uwb/device/) ranges a tag;
[`without_uwb/device/`](../without_uwb/device/) sweeps and tracks by vision.
Most modules are the same in both; this doc covers those first, then each
build's own modules in its section ([With UWB](#with-uwb),
[Without UWB](#without-uwb)). The UWB build also runs a second program, on the
wearable tag.

## Camera service — Raspberry Pi 4 (`<build>/device/`)

Python 3.11+, systemd unit `sportcam-head.service`. Modules common to both
builds:

| Module | Job |
| --- | --- |
| `main.py` | asyncio supervisor: WS client to server, state handling, control/frame/telemetry loops |
| `camera.py` | Picamera2: 720p preview (JPEG + person-detect) and 1080p **hardware** H.264 recording to `/home/pi/recordings` |
| `ptz.py` | the whole PTZ controller at I2C 0x0C: pan, tilt, zoom, focus, soft limits, homing |
| `ptzcheck.py` | bench tool — sweeps both axes to their limits so you can set `config` before filming |
| `led.py` | WS2812B status ring over SPI, so nothing needs to run as root |
| `power.py` | battery gauge (INA260 or INA226, or none): watt-hour integration, runtime estimate, low/critical levels |
| `storage.py` | SD-card space in minutes of recording left, with the same low/critical treatment |
| `focuscal.py` | `python -m sportcam.focuscal <metres>` — sweeps the focus motor at five focal lengths and prints a `FOCUS_GRID` |
| `uploader.py` | background recording upload → backend, with progress, retry, and a boot-time drain of anything stranded ([08](08-recordings-and-cloud.md)) |
| `wifi_portal.py` | hotspot + captive setup page when offline, for gym Wi-Fi ([08](08-recordings-and-cloud.md)) |
| `local_api.py` | the camera-hosted copy of the server's API, for phones connecting directly ([09](09-direct-connection-and-app.md)) |
| `discovery.py` | mDNS advertisement as `_sportcam._tcp` |
| `config.py` | all tunables, including `TRACKING_MODE` (this build's name, reported to the server and phones) and `UPLOAD_API_BASE` |

`tracker.py` and `session.py` exist in both but differ completely, and the UWB
build adds `uwb.py` and `rangecal.py` — see the build sections.

Install on the Pi (the clone holds both builds; run the one you built):

```bash
sudo apt install -y python3-picamera2 python3-opencv
git clone https://github.com/gitaaron/sport_cam.git ~/sportcam
cd ~/sportcam/<build>/device              # with_uwb or without_uwb
pip install -r requirements.txt           # + smbus2 and neopixel-spi
sudo raspi-config            # Interface Options → enable I2C (PTZ, gauge) and SPI (ring)
sudo cp sportcam-head.service sportcam-wifi.service /etc/systemd/system/
sudo systemctl enable sportcam-head sportcam-wifi
```

The service files point at `/home/pi/sportcam/<build>/device`. The service
runs as an ordinary user. Nothing here needs root, which is why the LED ring
goes out over SPI rather than the PWM/DMA driver. Your build's
software setup guide has every step in order.

Before the first run, set the soft limits and check the servo
directions:

```bash
python -m sportcam.ptzcheck
```

After a recording stops, `main.py` hands the finished MP4 to `uploader.py`
as a background task — tracking and live streaming continue uninterrupted —
which uploads it to whichever backend `UPLOAD_API_BASE` points at, then
deletes the local copy once the backend confirms the byte count. See
[08 — Recordings, cloud backend & gym Wi-Fi](08-recordings-and-cloud.md).

Streaming choices:

- **Dev / simplest**: `camera.py` JPEG-encodes the 720p preview at 15 fps and
  pushes binary WS frames to the server, which re-serves them as MJPEG. Zero
  extra moving parts; ~250 ms latency.
- **Production**: run [MediaMTX](https://github.com/bluenviron/mediamtx) on the
  Pi, feed it H.264 via `rpicam-vid`, and let the app play WebRTC (WHEP)
  directly from the Pi; the server only brokers the URL. ~150 ms latency,
  no transcode. The Vue player tries WHEP first and falls back to MJPEG.

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
snapping. There is no `panVel` message, on the wire or anywhere else.

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
`<build>/device/tests/test_ptz.py` covers the focus lookup in both builds; all device
tests run on any machine (`python3 tests/test_<name>.py`).

### Status ring

16 × WS2812B over SPI0 MOSI: `idle` solid blue, `tracking` while acquiring a
green light chasing round once a second, `tracking` once locked on solid green,
`recording` 1 Hz breathing red, lost subject 2 Hz flash, low battery dims the
ring and blinks orange once a second over whatever colour the state is.

## Message protocol (device ↔ server)

Common to both builds; the UWB build adds the tag messages listed in
[its section](#protocol-additions-with-uwb).

```jsonc
// device → server
{ "type": "hello", "device": "head" | "sim", "mode": "with_uwb" | "without_uwb",
  "caps": ["video","pan","tilt","zoom","led","battery","direct"] }   // + "uwb" with UWB
{ "type": "telemetry", "pan": -12.5, "tilt": 10.0, "zoomMm": 7.4, "dist": 4.2,
  "phase": "acquiring" | "acquired" | null, "acquireStalled": false,
  "battery": 0.82, "batteryWatts": 14.6, "batteryMinutes": 191, "batteryLevel": "ok" }
{ "type": "warning", "code": "battery-low", ... }
{ "type": "frame" }                    // followed by one binary WS message (JPEG)
{ "type": "stateReport", "state": "recording" }  // the head changed state itself
                                       // (lock-on, tag on/off, give-up, low battery); the server adopts it
{ "type": "uploadProgress", "name": "rec_….mp4", "sent": 12345, "total": 99999 }

// server → app clients
{ "type": "state", "mode": "with_uwb" | "without_uwb", ... }   // full StateSnapshot
{ "type": "recordings", "recordings": [ … ] }   // library, newest first
{ "type": "uploadProgress", … }        // relayed from the head

// server → device
{ "type": "state", "state": "idle" | "tracking" | "recording" | "off" }
{ "type": "resetBattery" }             // zero the fuel gauge on a fresh pack
{ "type": "shutdown" }
```

`mode` in the hello is the camera's `config.TRACKING_MODE`. The server does
not change behaviour on it — its own `TRACKING_MODE` decides — but it logs a
warning if the two disagree ([06](06-server-and-app.md#tracking-mode)).

Devices are dumb about state: they render/act on whatever `state` the server
last sent. The exception is a change the head makes itself — a lock-on
starting a recording, low battery, and the build-specific ones below — which
it reports as `stateReport` and the server adopts. On (re)connecting, the head
reports its state first and the server takes it, rather than pushing its own:
a recording started at the gym must survive the home server coming back into
reach.

`pan` is degrees from centre (negative is left), not an absolute 0–360
heading, because the axis no longer rotates.

---

## With UWB

Two programs run on the hardware: the camera and the wearable.

### Modules, with UWB

| Module | Job |
| --- | --- |
| `uwb.py` | parses ranges from the radio (ULA1 frames, or our own two-serial sketch), bearing maths + Kalman → (θ, d) |
| `tracker.py` | loops from [04](../with_uwb/docs/04-tracking-system.md): pan and tilt positions from ranging, CV bias trims, vision framing (zoom to fill 65 % of the frame), focus from distance, and the lock-on test |
| `session.py` | tag-driven sessions: tag on → tracking (acquiring) → recording on lock-on; tag off → idle ([01](01-system-overview.md#a-session-with-uwb)) |
| `rangecal.py` | `python -m sportcam.rangecal <metres>` — with the tag taped on the boresight, measures each anchor's range bias and noise and prints a `RANGE_BIAS_M` |

`config.py` also carries the anchor geometry and calibration biases.

After `ptzcheck`, with the tag taped 5.00 m out on the boresight, measure each
anchor's range bias. With the 250 mm mast this is not optional: a few
centimetres on A3 is ten degrees of tilt.

```bash
cd ~/sportcam/with_uwb/device && python -m sportcam.rangecal 5
```

### Vision, with UWB

With the third anchor fitted, ranging gives both angles and the person
detector does three jobs: it cancels a slow bias on pan and on tilt, it
frames the shot, and it verifies lock-on before a tag-started session
records. On a two-anchor build (`UWB_ANCHORS = 2`) it is the only source of
tilt, because a horizontal baseline carries no elevation information. Tilt
only has to keep up with roughly 1.7°/s of subject motion.

The search strip comes from ranging: the tracker turns the known bearing into
a pixel column, so the detector looks at about 40 % of frame width.
`Camera.person_bbox()` returns `(bbox, fresh)`.

`with_uwb/device/tests/test_tracker.py` covers the fresh-only rule, the strip
hint, the slew limits, tilt from the third anchor, the sign of every vertical
correction, and vision framing (fill target, edge guard, stale relax).
`test_session.py` covers lock-on and the tag-driven session flow.

When ranging drops out the camera **holds** rather than letting vision chase
whoever is in frame. The detector cannot tell your subject from a bystander;
the tag can, and that is the reason the tag exists.

### Where ranges come from

`config.UWB_PROTOCOL` picks the radio stack, and the two differ in shape:

- **`ula1`** — Haorutech ULA1. The tag polls each anchor and broadcasts one
  RangeData frame; a single anchor plugged into the Pi forwards it as
  `mc <mask> <r0> <r1> <r2> <r3> …`, ranges in **hexadecimal millimetres**
  behind a validity mask. RANGE0–2 are A1–A3. They share a timestamp, which
  is what the angle maths assumes. One USB data connection, not three. A
  frame missing only A3 still gives a bearing; it just carries no elevation.

  **Flash the `RTLS_Tag` and `RTLS_Anchor` sketches, not `RangingTag` and
  `RangingAnchor`.** The vendor ships both pairs and they behave differently:
  the Ranging pair completes one tag-to-anchor exchange and reports that
  single distance, while the RTLS pair ranges to every anchor in turn and then
  broadcasts the collected RangeData. Only the second produces the frame this
  parser reads, and only the second lets one anchor report for all three.
  Load the wrong pair and you will see a stream carrying one range where
  three are expected — at which point either reflash, or switch to
  `dual-serial`.
- **`dual-serial`** — one port per anchor running our own DS-TWR sketch
  ([`with_uwb/firmware/uwb_anchor/`](../with_uwb/firmware/uwb_anchor/)),
  printing `R,<tag>,<range_m>`. Vendor-agnostic, but the ranges are
  independent samples.

`with_uwb/device/tests/test_uwb.py` parses the manual's own worked example and
checks the mask, the hex scaling, the bearing geometry, and the elevation
solve — exact to 0.01° across the whole envelope with A3's backward offset
in. It runs anywhere.

### Wearable tag — ULA1 (`with_uwb/wearable/`)

The tag is a ULA1 module running the vendor's ranging firmware, powered by a
small USB bank. It initiates ranging against each anchor and broadcasts the
results.

Our previous sketch (`with_uwb/wearable/tag_firmware/`) targeted a Makerfabs
ESP32-UWB and added a pair/record button broadcast over BLE as
`SPORTCAM-BTN:<kind>`, which the camera relayed as `tagButton`. The ULA1 is
also an ESP32 under Arduino, so that code can be ported, but the pin map must
come from the vendor's schematic first. Until then, recording is started from
the phone.

### Protocol additions, with UWB

```jsonc
// device → server, with UWB only
{ "type": "telemetry", …, "tagPresent": true }   // the wearable is switched on and ranging
{ "type": "tagButton", "kind": "short" | "long" } // long press toggles recording
{ "type": "lost" }                     // tag gone past the timeout → server drops to idle
```

The head also reports the tag switching on or off as a `stateReport`. A server
running `TRACKING_MODE=without_uwb` ignores `tagButton` and `lost`.

---

## Without UWB

One program runs on the hardware — the camera. There is no wearable and with
no UWB there is no tag to talk to.

### Modules, without UWB

| Module | Job |
| --- | --- |
| `tracker.py` | the SEARCH → CENTRE → TRACK state machine and control loops from [04](../without_uwb/docs/04-tracking-system.md): sweep, first-person lock-on with a gate, pan/tilt goals and slew, vision-only zoom framing, focus from apparent size |
| `session.py` | `AutoSession`: the first lock of a session that began in idle starts recording; a tracking session that never found anyone gives up after 180 s ([01](01-system-overview.md#a-session-without-uwb)) |

`config.py` also carries the search and tracking gains, the detector settings,
and the zoom and focus curves. `camera.py` adds `person_boxes()`, which
returns every detected person.

### Vision, without UWB

Vision is the only sensor. The person detector does everything the tracker
knows: it finds the first person while sweeping, tells the tracker where they
are in the frame, and its box size gives the framing and the focus distance.

- **3 fps** is `DETECT_FPS_TRACKING`. HOG on a Pi 4 takes a few hundred
  milliseconds per frame.
- **The search strip** is the followed person's column once locked, about
  60 % of frame width (`DETECT_STRIP_FRACTION`). While sweeping the whole
  frame is searched.

`Camera.person_boxes()` returns `(boxes, fresh)`: every detected person as
`(x, y, w, h)`, and whether this list is a new measurement. The detector
itself is isolated in `Camera._detect()`: swapping HOG for a MobileNet-SSD
through `cv2.dnn` changes that method and nothing else.

`without_uwb/device/tests/test_tracker.py` covers the sweep and its
turn-arounds, the two-detection lock, the gate against bystanders, the sign
of every correction, the slew limits, and vision framing (fill target, edge
guard, stale relax). `test_session.py` covers auto-record on lock and the
give-up rule.

Vision cannot tell people apart. The tracker follows whoever it found first,
keeps to the detection nearest the last position, and sweeps again when it
loses them; see
[limitations](../without_uwb/docs/04-tracking-system.md#limitations).

### Protocol, without UWB

No additions. `dist` in the telemetry is estimated from the person's size in
frame (null while searching), and `acquireStalled` means the search has found
nobody for a while. The head's own state changes are the first lock-on
starting a recording and an empty-room give-up.
