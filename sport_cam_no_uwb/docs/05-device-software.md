# 05 — Device software

One program runs on the hardware now — the camera. There is no wearable and no
base controller: with no pan stepper there is nothing for a second
microcontroller to do, and with no UWB there is no tag to talk to, so pan,
tilt, zoom, focus, the status ring and the person detector all live on the
Pi. It speaks the WebSocket protocol to the server (`/ws/device`), documented
in [06 — Server & app](06-server-and-app.md).

## 1. Camera service — Raspberry Pi 4 (`device/`)

Python 3.11+, systemd unit `sportcam-head.service`. Modules:

| Module | Job |
| --- | --- |
| `main.py` | asyncio supervisor: WS client to server, state handling, control/frame/telemetry loops |
| `camera.py` | Picamera2: 720p preview (JPEG + HOG person detection, `person_boxes()`) and 1080p **hardware** H.264 recording to `/home/pi/recordings` |
| `ptz.py` | the whole PTZ controller at I2C 0x0C: pan, tilt, zoom, focus, soft limits, homing |
| `ptzcheck.py` | bench tool — sweeps both axes to their limits so you can set `config` before filming |
| `led.py` | WS2812B status ring over SPI, so nothing needs to run as root |
| `power.py` | battery gauge (INA260 or INA226, or none): watt-hour integration, runtime estimate, low/critical levels |
| `storage.py` | SD-card space in minutes of recording left, with the same low/critical treatment |
| `tracker.py` | the SEARCH → CENTRE → TRACK state machine and control loops from [04](04-tracking-system.md): sweep, first-person lock-on with a gate, pan/tilt goals and slew, vision-only zoom framing, focus from apparent size |
| `session.py` | `AutoSession`: the first lock of a session that began in idle starts recording; a tracking session that never found anyone gives up after 180 s ([01](01-system-overview.md#concept-of-operations)) |
| `focuscal.py` | `python -m sportcam.focuscal <metres>` — sweeps the focus motor at five focal lengths and prints a `FOCUS_GRID` |
| `uploader.py` | background recording upload → backend, with progress, retry, and a boot-time drain of anything stranded ([08](08-recordings-and-cloud.md)) |
| `wifi_portal.py` | hotspot + captive setup page when offline, for gym Wi-Fi ([08](08-recordings-and-cloud.md)) |
| `config.py` | all tunables (soft limits, search and tracking gains, detector, zoom and focus curves, `UPLOAD_API_BASE`) |

Install on the Pi:

```bash
sudo apt install -y python3-picamera2 python3-opencv
pip install -r device/requirements.txt    # + smbus2 and neopixel-spi
sudo raspi-config            # Interface Options → enable I2C (PTZ, gauge) and SPI (ring)
sudo systemctl enable sportcam-head sportcam-wifi
```

The service runs as an ordinary user. Nothing here needs root, which is why
the LED ring goes out over SPI rather than the PWM/DMA driver.

Before the first run, set the soft limits and check the servo
directions:

```bash
cd device && python -m sportcam.ptzcheck
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
ptz.set_pan(-12.5)      # degrees from the enclosure's forward axis
ptz.set_tilt(18.0)      # degrees above level, at the lens
ptz.set_focus(9.4)      # subject distance in metres; looked up in FOCUS_GRID
ptz.set_zoom_mm(7.4)    # interpolated through config.ZOOM_CURVE, rate-limited
ptz.park()              # centre both axes
```

The tracker calls `set_pan` / `set_tilt` with an absolute target each tick,
slew-limited to `PAN_MAX_DPS` / `TILT_MAX_DPS` so the servo glides between
detections instead of snapping. There is no `panVel` message, on the wire or
anywhere else.

### Vision, and why it runs slowly

Vision is the only sensor. The person detector does everything the tracker
knows: it finds the first person while sweeping, tells the tracker where they
are in the frame, and its box size gives the framing and the focus distance.
None of it needs to be fast, but it needs to be steady:

- **It runs at 3 fps** (`DETECT_FPS_TRACKING`), dropping to 0.5 when idle.
  HOG on a Pi 4 takes a few hundred milliseconds, and a person moves slowly
  seen from several metres.
- **It searches a vertical strip once locked.** The tracker hands the
  followed person's column to `Camera.set_search_column()`, so the detector
  looks at about 60 % of frame width (`DETECT_STRIP_FRACTION`), a several-fold
  saving. While sweeping the whole frame is searched.

`Camera.person_boxes()` returns `(boxes, fresh)`: every detected person as
`(x, y, w, h)`, and whether this list is a new measurement. The control loop
runs at 20 Hz and vision at 3, so acting on the cached list every tick would
apply one measurement about seven times over and make the camera hunt. The
tracker acts only when `fresh` is true. The detector itself is isolated in
`Camera._detect()`: swapping HOG for a MobileNet-SSD through `cv2.dnn` changes
that method and nothing else.

`device/tests/test_tracker.py` covers the sweep and its turn-arounds, the
two-detection lock, the gate against bystanders, the sign of every
correction, the slew limits, and vision framing (fill target, edge guard,
stale relax). `device/tests/test_session.py` covers auto-record on lock and
the give-up rule, and `device/tests/test_ptz.py` the focus lookup. All run on
any machine.

Vision cannot tell people apart. The tracker follows whoever it found first,
keeps to the detection nearest the last position, and sweeps again when it
loses them; see [limitations](04-tracking-system.md#limitations).

### Status ring

16 × WS2812B over SPI0 MOSI: `idle` solid blue, `tracking` while acquiring a
green light chasing round once a second, `tracking` once locked on solid green,
`recording` 1 Hz breathing red, a lost target 2 Hz flash, low battery dims the ring
and blinks orange once a second over whatever colour the state is.

## Message protocol (device ↔ server)

```jsonc
// device → server
{ "type": "hello", "device": "head" | "sim", "caps": ["video","pan","tilt","zoom","led","battery","direct"] }
{ "type": "telemetry", "pan": -12.5, "tilt": 10.0, "zoomMm": 7.4, "dist": 4.2,   // estimated from the person's size
  "phase": "acquiring" | "acquired" | null, "acquireStalled": false,
  "battery": 0.82, "batteryWatts": 14.6, "batteryMinutes": 191, "batteryLevel": "ok" }
{ "type": "warning", "code": "battery-low", ... }
{ "type": "frame" }                    // followed by one binary WS message (JPEG)
{ "type": "stateReport", "state": "recording" }  // the head changed state itself
                                       // (first lock-on, give-up, low battery); the server adopts it
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
last sent. The exception is a change the head makes itself — the
first lock-on starting a recording, an empty-room give-up, low battery — which it reports as `stateReport`
and the server adopts. On (re)connecting, the head reports its state first
and the server takes it, rather than pushing its own: a recording the camera
started at the gym must survive the home server coming back into reach.

`pan` is degrees from centre (negative is left), not an absolute 0–360
heading, because the axis no longer rotates.
