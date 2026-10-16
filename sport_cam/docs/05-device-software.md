# 05 — Device software

Two programs run on the hardware now — the camera and the wearable. The base
controller is gone: with no pan stepper there is nothing for a second
microcontroller to do, so pan, tilt, zoom, focus and the status ring all moved
onto the Pi. Both programs speak the same WebSocket protocol to the server
(`/ws/device`), documented in [06 — Server & app](06-server-and-app.md).

## 1. Camera service — Raspberry Pi 4 (`device/`)

Python 3.11+, systemd unit `sportcam-head.service`. Modules:

| Module | Job |
| --- | --- |
| `main.py` | asyncio supervisor: WS client to server, state handling, control/frame/telemetry loops |
| `camera.py` | Picamera2: 720p preview (JPEG + person-detect) and 1080p **hardware** H.264 recording to `/home/pi/recordings` |
| `ptz.py` | the whole PTZ controller at I2C 0x0C: pan, tilt, zoom, focus, soft limits, homing |
| `ptzcheck.py` | bench tool — sweeps both axes to their limits so you can set `config` before filming |
| `led.py` | WS2812B status ring over SPI, so nothing needs to run as root |
| `power.py` | battery gauge (INA260 or INA226, or none): watt-hour integration, runtime estimate, low/critical levels |
| `storage.py` | SD-card space in minutes of recording left, with the same low/critical treatment |
| `uwb.py` | parses ranges from the radio (ULA1 frames, or our own two-serial sketch), bearing maths + Kalman → (θ, d) |
| `tracker.py` | loops from [04](04-tracking-system.md): pan and tilt positions from ranging, CV bias trims, vision framing (zoom to fill 65 % of the frame), focus from distance, and the lock-on test |
| `session.py` | tag-driven sessions: tag on → tracking (acquiring) → recording on lock-on; tag off → idle ([01](01-system-overview.md#concept-of-operations)) |
| `focuscal.py` | `python -m sportcam.focuscal <metres>` — sweeps the focus motor at five focal lengths and prints a `FOCUS_GRID` |
| `rangecal.py` | `python -m sportcam.rangecal <metres>` — with the tag taped on the boresight, measures each anchor's range bias and noise and prints a `RANGE_BIAS_M` |
| `uploader.py` | background recording upload → backend, with progress, retry, and a boot-time drain of anything stranded ([08](08-recordings-and-cloud.md)) |
| `wifi_portal.py` | hotspot + captive setup page when offline, for gym Wi-Fi ([08](08-recordings-and-cloud.md)) |
| `config.py` | all tunables (pins, PID gains, calibration biases, `UPLOAD_API_BASE`) |

Install on the Pi:

```bash
sudo apt install -y python3-picamera2 python3-opencv
pip install -r device/requirements.txt    # + smbus2 and neopixel-spi
sudo raspi-config            # Interface Options → enable I2C (PTZ, gauge) and SPI (ring)
sudo systemctl enable sportcam-head sportcam-wifi
```

The service runs as an ordinary user. Nothing here needs root, which is why
the LED ring goes out over SPI rather than the PWM/DMA driver.

Before the first tracking run, set the soft limits and check the servo
directions:

```bash
cd device && python -m sportcam.ptzcheck
```

Then, with the tag taped 5.00 m out on the boresight, measure each anchor's
range bias. With the 250 mm mast this is not optional: a few centimetres on
A3 is ten degrees of tilt.

```bash
cd device && python -m sportcam.rangecal 5
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
ptz.set_pan(-12.5)      # degrees from the anchor bar's normal
ptz.set_tilt(18.0)      # degrees above level, at the lens
ptz.set_focus(9.4)      # subject distance in metres; looked up in FOCUS_GRID
ptz.set_zoom_mm(7.4)    # interpolated through config.ZOOM_CURVE, rate-limited
ptz.park()              # centre both axes
```

The tracker calls `set_pan` with an absolute target each tick, slew-limited to
`PAN_MAX_DPS` so the servo glides between frames instead of snapping. There is
no `panVel` message any longer, on the wire or anywhere else.

### Vision, and why it runs slowly

With the third anchor fitted, ranging gives both angles and the person
detector does three jobs: it cancels a slow bias on pan and on tilt, it
frames the shot (zooming until the person fills 65 % of the frame, and out
fast if they near an edge), and it verifies lock-on before a tag-started
session records. On a two-anchor build
(`UWB_ANCHORS = 2`) it is the only source of tilt, because a horizontal
baseline carries no elevation information. None of it needs to be fast.

Two things make it cheap enough for a Pi 4:

- **It runs at 3 fps**, dropping to 0.5 when idle. Tilt only has to keep up
  with roughly 1.7°/s of subject motion.
- **It searches a vertical strip, not the frame.** The tracker turns the known
  bearing into a pixel column and hands it to `Camera.set_search_column()`,
  so the detector looks at about 40 % of frame width.

`Camera.person_bbox()` returns `(bbox, fresh)`. The control loop runs at 20 Hz
and vision at 3, so acting on the cached box every tick would apply one
measurement about seven times over and make the tilt axis hunt. The tracker
acts only when `fresh` is true. `device/tests/test_tracker.py` covers that,
the strip hint, the slew limits, tilt from the third anchor, the sign of every
vertical correction, and vision framing (fill target, edge guard, stale
relax). `device/tests/test_session.py` covers lock-on and the tag-driven
session flow, and `device/tests/test_ptz.py` the focus lookup. All run on any
machine.

When ranging drops out the camera **holds** rather than letting vision chase
whoever is in frame. The detector cannot tell your subject from a bystander;
the tag can, and that is the reason the tag exists.

### Status ring

16 × WS2812B over SPI0 MOSI: `idle` solid blue, `tracking` while acquiring a
green light chasing round once a second, `tracking` once locked on solid green,
`recording` 1 Hz breathing red, lost tag 2 Hz flash, low battery dims the ring
and blinks orange once a second over whatever colour the state is.

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
- **`dual-serial`** — one port per anchor running our own DS-TWR sketch,
  printing `R,<tag>,<range_m>`. Vendor-agnostic, but the ranges are
  independent samples.

`device/tests/test_uwb.py` parses the manual's own worked example and checks
the mask, the hex scaling, the bearing geometry, and the elevation solve —
exact to 0.01° across the whole envelope with A3's backward offset in. It
runs anywhere.

## 2. Wearable tag — ULA1 (`wearable/`)

The tag is a ULA1 module running the vendor's ranging firmware, powered by a
small USB bank. It initiates ranging against each anchor and broadcasts the
results.

Our previous sketch (`wearable/tag_firmware/`) targeted a Makerfabs
ESP32-UWB and added a pair/record button broadcast over BLE as
`SPORTCAM-BTN:<kind>`, which the camera relayed as `tagButton`. The ULA1 is
also an ESP32 under Arduino, so that code can be ported, but the pin map must
come from the vendor's schematic first. Until then, recording is started from
the phone.

## Message protocol (device ↔ server)

```jsonc
// device → server
{ "type": "hello", "device": "head" | "sim", "caps": ["video","pan","tilt","zoom","uwb","led","battery"] }
{ "type": "telemetry", "pan": -12.5, "tilt": 10.0, "zoomMm": 7.4, "dist": 4.2,
  "phase": "acquiring" | "acquired" | null, "tagPresent": true,
  "battery": 0.82, "batteryWatts": 14.6, "batteryMinutes": 191, "batteryLevel": "ok" }
{ "type": "warning", "code": "battery-low", ... }
{ "type": "frame" }                    // followed by one binary WS message (JPEG)
{ "type": "tagButton", "kind": "short" | "long" }
{ "type": "lost" }                     // tag gone past the timeout → server drops to idle
{ "type": "stateReport", "state": "recording" }  // the head changed state itself
                                       // (tag on/off, lock-on, low battery); the server adopts it
{ "type": "uploadProgress", "name": "rec_….mp4", "sent": 12345, "total": 99999 }

// server → app clients
{ "type": "state", ... }               // full StateSnapshot
{ "type": "recordings", "recordings": [ … ] }   // library, newest first
{ "type": "uploadProgress", … }        // relayed from the head

// server → device
{ "type": "state", "state": "idle" | "tracking" | "recording" | "off" }
{ "type": "resetBattery" }             // zero the fuel gauge on a fresh pack
{ "type": "shutdown" }
```

Devices are dumb about state: they render/act on whatever `state` the server
last sent. The exception is a change the head makes itself — the tag
switched on or off, lock-on, low battery — which it reports as `stateReport`
and the server adopts. On (re)connecting, the head reports its state first
and the server takes it, rather than pushing its own: a recording the tag
started at the gym must survive the home server coming back into reach.

`pan` is degrees from centre (negative is left), not an absolute 0–360
heading, because the axis no longer rotates.
