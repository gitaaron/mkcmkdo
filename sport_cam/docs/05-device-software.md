# 05 — Device software

Three programs run on the hardware. All speak the same WebSocket protocol to
the server (`/ws/device`), documented in [06 — Server & app](06-server-and-app.md).

## 1. Head service — Raspberry Pi 5 (`device/`)

Python 3.11+, systemd unit `sportcam-head.service`. Modules:

| Module | Job |
| --- | --- |
| `main.py` | asyncio supervisor: WS client to server, state handling, control/frame/telemetry loops |
| `camera.py` | Picamera2: 720p preview (JPEG + person-detect) and 1080p H.264 recording to `/home/pi/recordings` |
| `lens.py` | Arducam zoom/focus over I2C (0x0C), homing, EFL → step conversion |
| `tilt.py` | pigpio hardware PWM on GPIO18, soft end-stops −45…+225° |
| `uwb.py` | reads both anchor serials, DS-TWR maths + Kalman → (θ, d) at 20 Hz |
| `tracker.py` | PIDs from [04](04-tracking-system.md): pan velocity out, tilt/zoom applied directly |
| `config.py` | all tunables (pins, PID gains, calibration biases) |

Install on the Pi:

```bash
sudo apt install -y python3-picamera2 python3-opencv pigpiod
pip install websockets simple-pid filterpy
sudo systemctl enable pigpiod sportcam-head
```

Streaming choices:

- **Dev / simplest**: `camera.py` JPEG-encodes the 720p preview at 15 fps and
  pushes binary WS frames to the server, which re-serves them as MJPEG. Zero
  extra moving parts; ~250 ms latency.
- **Production**: run [MediaMTX](https://github.com/bluenviron/mediamtx) on the
  Pi, feed it H.264 via `rpicam-vid`, and let the app play WebRTC (WHEP)
  directly from the Pi; the server only brokers the URL. ~150 ms latency,
  no transcode. The Vue player tries WHEP first and falls back to MJPEG.

## 2. Base controller — ESP32 (`firmware/base_controller/`)

Arduino (arduino-esp32 core). Responsibilities: Wi-Fi + WS client, pan
stepper, LED ring, hall-sensor homing.

- **Stepper**: `FastAccelStepper` driving TMC2209 STEP/DIR at 16 microsteps;
  accepts `{"type":"panVel","dps":-42.0}` messages (degrees/sec, slew- and
  accel-limited on-board so a dropped packet can't cause a lurch; auto-stops
  if no command for 500 ms).
- **LED ring**: FastLED, 16 × WS2812B. `idle`=solid blue, `tracking`=solid
  green, `recording`=1 Hz breathing red, `error`=flash orange.
- **Homing**: on boot, rotate until the hall sensor fires → that's pan 0°.
  Reports absolute pan angle back to the server at 5 Hz (dead-reckoned from
  step count; re-zeroed every time the magnet passes).

Build: Arduino IDE or `arduino-cli compile --fqbn esp32:esp32:esp32`
with libraries `FastAccelStepper`, `FastLED`, `ArduinoWebsockets`, `ArduinoJson`.

## 3. Wearable tag — ESP32-UWB (`wearable/tag_firmware/`)

Arduino + `arduino-dw1000` (Makerfabs fork for their board). DS-TWR responder
loop, button handling (short = re-acquire, long = toggle record — broadcast
as a 500 ms BLE advertisement `SPORTCAM-BTN:<kind>`, which the Pi head
service picks up with a BLE scan and relays as `tagButton`), battery ADC
reporting, deep sleep after 10 min without any anchor poll.

## Message protocol (device ↔ server)

```jsonc
// device → server
{ "type": "hello", "device": "head" | "base" | "sim", "caps": ["video","tilt","zoom","uwb"] }
{ "type": "telemetry", "pan": 123.4, "tilt": 10.0, "zoomMm": 12.5, "dist": 4.2, "battery": 0.82 }
{ "type": "frame" }                    // followed by one binary WS message (JPEG)
{ "type": "tagButton", "kind": "short" | "long" }

// server → device
{ "type": "state", "state": "idle" | "tracking" | "recording" | "off" }
{ "type": "panVel", "dps": -42.0 }     // server relays head → base
{ "type": "shutdown" }
```

Devices are dumb about state: they render/act on whatever `state` the server
last sent, and the server persists the state machine — so a rebooting device
rejoins in the correct mode.
