# 14 — Software setup (bench test, without UWB)

From a blank SD card to the camera answering the phone app, on the bench rig
of [12](12-wiring.md). It is the camera-only build's setup with everything the
bench doesn't have left out; where a step is the same, it links there.

| | |
| --- | --- |
| Prerequisite | the [bench wiring](12-wiring.md) done; its power-under-load check (step 3) comes after `ptzcheck` below |
| Equipment | a computer with [Raspberry Pi Imager](https://www.raspberrypi.com/software/), Node 22, Java 17+ and the Flutter SDK; one phone, or two to test sharing the camera; all on the same Wi-Fi |
| Duration | ≈ **1 h** |

| Left out of the full setup | Why |
| --- | --- |
| SPI, the LED ring | no ring on the bench |
| pigpio and the servo PWM | the servos stay on the PTZ controller (`SERVO_DRIVER = "arducam"`) |
| the person-detector download (`getmodel`) | HOG, built in, finds a person standing in front of the camera |
| calibration (zoom curve, focus grid) | not needed to test the app; tracking works on the defaults, a little soft |
| the services and the Wi-Fi portal | run the camera in a terminal instead; Wi-Fi comes from the Pi Imager settings |
| the power switch setup | no latch on the bench |

## 1. Raspberry Pi OS

As [the full build's step 1](../setup/14-software-setup.md#1-raspberry-pi-os)
— Bookworm 64-bit, username `pi`, hostname `sportcam`, **your Wi-Fi** and SSH
set in Imager — but enable only I2C:

```bash
sudo raspi-config nonint do_i2c 0       # the PTZ controller
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

**Done when:** `rpicam-hello -t 2000` shows the camera, and `i2cdetect -y 1`
lists `0c`. No picture: add `dtoverlay=imx477` to
`/boot/firmware/config.txt` and reboot.

## 2. Install the camera software

```bash
sudo apt install -y git python3-pip python3-picamera2 python3-opencv i2c-tools
git clone https://github.com/gitaaron/sport_cam.git ~/sportcam
cd ~/sportcam/src/without_uwb/device
sudo pip3 install --break-system-packages -r requirements.txt
```

Then tell it what the bench lacks, in `sportcam/config.py`:

```bash
sed -i -e 's/^SERVO_DRIVER = .*/SERVO_DRIVER = "arducam"/' \
       -e 's/^POWER_MONITOR = .*/POWER_MONITOR = "none"/' sportcam/config.py
```

**Done when:** the offline tests pass, and the head moves:

```bash
for t in tests/test_*.py; do python3 $t | tail -1; done
python3 -m sportcam.ptzcheck      # sweeps both axes; the pan creeps in whole-degree ticks, as expected here
vcgencmd get_throttled            # throttled=0x0: the adapter held 5 V while the motors ran (12, step 3)
```

If a positive pan turns the lens the wrong way, or a positive tilt doesn't
point it up, flip `PAN_SIGN` / `TILT_SIGN`
([full build, step 4b](../setup/14-software-setup.md#4-bench-checks-camera-and-motion)).

## 3. Run the camera

In a terminal on the Pi, from `~/sportcam/src/without_uwb/device`:

```bash
python3 -m sportcam.main
```

It waits 15 s for a Wi-Fi portal that isn't installed, then goes **awake**:
the log shows `[local-api] serving on http://0.0.0.0:8787`. `[led] disabled`
and the gauge's absence are expected.

**Stopping it:** stop any recording from the app first, then Ctrl-C.
(Ctrl-C parks the head but doesn't save a clip still recording; the full
build's service saves it.) Then `sudo poweroff`, and unplug the adapter once
the Pi's green LED stops.

## 4. The app, on the camera alone

No backend yet: the app finds the camera on the Wi-Fi and nobody signs in.

```bash
cd src/app_flutter
flutter pub get
flutter run
```

Apply the [platform setup](../../../src/app_flutter/README.md#platform-setup-notes)
first (iOS `NSBonjourServices`; Android multicast and cleartext). Without it,
discovery silently finds nothing.

**Done when:** the badge reads **Direct** and the live view shows the
camera's picture. The tests: [15, part A](15-verification.md#a-the-camera-alone).

## 5. The backend, on your computer

Sign-in, uploads and each person's library, with no Firebase project: the
Firebase emulators on your computer, which the Pi and the phone reach over
the Wi-Fi. From the repo root:

```bash
npm install
npm run dev:without_uwb
```

It prints `sign in to the app as admin@sportcam.dev or climber@sportcam.dev,
password sportcam-dev`. (It also runs a simulated camera, `dev-camera-key`;
the real one gets its own key below.) Your computer's firewall must let the
Pi and the phone reach ports **5001**, **8080** and **9099**.

On the Pi, point the camera at it, with your computer's address for
`<computer>` (e.g. `192.168.1.20`):

```bash
cd ~/sportcam/src/without_uwb/device
sed -i -e 's/^FIREBASE_PROJECT = .*/FIREBASE_PROJECT = "demo-sportcam"/' \
       -e 's/^CAMERA_KEY = .*/CAMERA_KEY = "bench-camera-key"/' \
       -e 's|^UPLOAD_API_BASE = .*|UPLOAD_API_BASE = "http://<computer>:5001/demo-sportcam/us-central1/api"|' \
       sportcam/config.py
FIRESTORE_EMULATOR_HOST=<computer>:8080 python3 -m sportcam.main
```

**Done when:** the log shows `[cloud] connected to demo-sportcam`, and the
Emulator UI (http://localhost:4000, Firestore) shows `cameras/bench-camera-key`.

Then build the app against it:

```bash
flutter run --dart-define=SPORTCAM_FALLBACK=http://<computer>:5001/demo-sportcam/us-central1/api \
            --dart-define=SPORTCAM_CAMERA_KEY=bench-camera-key \
            --dart-define=SPORTCAM_AUTH_EMULATOR=<computer>:9099
```

**Done when:** the app opens on the sign-in page. The tests:
[15, part B](15-verification.md#b-with-the-backend).

The emulators forget everything when stopped, and make the two people again
at the next `npm run dev`. For the real thing — a Firebase project, from
anywhere — follow the
[full build's step 3](../setup/14-software-setup.md#3-connect-it-to-firebase-optional)
and drop `FIRESTORE_EMULATOR_HOST`.
