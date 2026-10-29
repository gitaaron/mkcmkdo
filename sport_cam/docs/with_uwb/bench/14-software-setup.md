# 14 — Software setup (bench test, with UWB)

From a blank SD card to the camera answering the phone app, on the bench rig
of [12](12-wiring.md). It is the UWB build's setup with everything the
bench doesn't have left out; where a step is the same, it links there.

| | |
| --- | --- |
| Prerequisite | the [bench wiring](12-wiring.md) done; its power-under-load check (step 3) comes after `ptzcheck` below |
| Equipment | a Mac with this repo checked out, [Raspberry Pi Imager](https://www.raspberrypi.com/software/), Node 22, Java 17+, the Flutter SDK and the Arduino IDE; one phone, or two to test sharing the camera; all on the same Wi-Fi |
| Duration | ≈ **1.5 h** |

| Left out of the full setup | Why |
| --- | --- |
| SPI, the LED ring | no ring on the bench |
| pigpio and the servo PWM | the servos stay on the PTZ controller (`SERVO_DRIVER = "arducam"`) |
| the person-detector download (`getmodel`) | HOG, built in, finds a person standing in front of the camera |
| the third anchor, A3 | `UWB_ANCHORS = 2`: tilt follows the person detector |
| calibration (range bias, bearing noise, zoom curve, focus grid) | not needed to test the app: the camera turns to the tag a few degrees off and the picture is a little soft |
| the services and the Wi-Fi portal | run the camera in a terminal instead; Wi-Fi comes from the Pi Imager settings |
| the power switch setup | no latch on the bench |

## 1. Raspberry Pi OS (on your Mac)

As [the full build's step 1](../setup/14-software-setup.md#1-raspberry-pi-os-on-your-mac),
every page of it: an SSH key on your Mac, Raspberry Pi Imager, the card
written as Raspberry Pi OS (Legacy, 64-bit) Lite with hostname `sportcam`,
user `pi`, your Wi-Fi and SSH with your key. Power the Pi by plugging in the
USB-C adapter.

**Done when:** `ssh pi@sportcam.local` logs in from your Mac without asking
for a password.

## 2. Install the camera software (from your Mac)

From the repo's root, on your Mac:

```bash
./scripts/pi-install.sh with_uwb --bench
```

As [the full build's step 2](../setup/14-software-setup.md#2-install-the-camera-software-from-your-mac)
(OS upgrade, packages, the code, its Python packages, the offline tests, a
reboot, checks), less what the bench leaves out: no SPI, pigpio or
`getmodel`. 15–25 minutes the first time. It also tells the camera what the
bench lacks, in `sportcam/config.py`:

| Setting | Set to | Because |
| --- | --- | --- |
| `SERVO_DRIVER` | `"arducam"` | the servos stay on the PTZ controller |
| `POWER_MONITOR` | `"none"` | no battery gauge: no battery warnings |
| `UWB_ANCHORS` | `2` | no A3: tilt follows the person detector |

**Done when:** it ends with `All set`: the camera found, and `0c` (the PTZ
controller) on I2C. A failed check names the connection to look at: fix it
and run the script again.

## 3. Flash the radios (on your computer)

As [the full build's step 3](../setup/14-software-setup.md#3-flash-the-radios-on-your-computer),
for three boards: A1, A2 and the tag. A3 isn't fitted.

| Board | Sketch | DIP switch 1 2 3 4 | Vendor name |
| --- | --- | --- | --- |
| A1 | `RTLS_Anchor` | ON off off off | A0 |
| A2 | `RTLS_Anchor` | ON off off ON | A1 |
| Tag | `RTLS_Tag` | off off off off | T0 |

**Done when:** with the tag powered, A1's port at 115200 baud in the Arduino
serial monitor shows lines starting `mc 03 …`: two ranges, A1's and A2's.

## 4. Bench checks

On the Pi (`ssh pi@sportcam.local`), from `~/sportcam/src/with_uwb/device`, the head:

```bash
python3 -m sportcam.ptzcheck      # sweeps both axes; the pan creeps in whole-degree ticks, as expected here
vcgencmd get_throttled            # throttled=0x0: the adapter held 5 V while the motors ran (12, step 3)
```

If a positive pan turns the lens the wrong way, or a positive tilt doesn't
point it up, flip `PAN_SIGN` / `TILT_SIGN`
([full build, step 5a](../setup/14-software-setup.md#5-bench-checks-motion-and-radios)).

**Done when:** both axes sweep.

Then the radios, tag on:

```bash
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200     # Ctrl-] to quit
```

**Done when** it streams `mc 03 …` at 8–20 lines a second. One range per
line: the Ranging sketches are on, not RTLS (step 3).

## 5. Run the camera

In a terminal on the Pi, from `~/sportcam/src/with_uwb/device`:

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

## 6. The app, on the camera alone

No backend yet: the app finds the camera on the Wi-Fi and nobody signs in.

```bash
cd src/app_flutter
flutter pub get
flutter run
```

Apply the [platform setup](../../../src/app_flutter/README.md#platform-setup-notes)
first (iOS `NSBonjourServices`; Android multicast and cleartext). Without it,
discovery silently finds nothing.

Then, on the camera's Wi-Fi, **pair the tag**: tag on (no other tag
near), account menu → **Pair my tag**. The app says *"Tag T0 is yours"*.
From then on, switching the tag on starts a recording that is this phone's.
The pairing is kept on the Pi (`PAIRINGS_FILE`), across restarts.

**Bearing sign.** Tag in hand, stand 3–5 m out in front of the camera and
press **Start tracking**: the camera turns to you. Walk to one side: it
should follow. If it turns the other way, set `UWB_THETA_SIGN = -1` in
`sportcam/config.py` and restart the camera (Ctrl-C, step 5).

**Done when:** the badge reads **Direct**, the live view shows the camera's
picture, the tag is paired and the camera follows you. The tests: [15, part A](15-verification.md#a-the-camera-alone).

## 7. The backend, on your computer

Sign-in, uploads and each person's library, with no Firebase project: the
Firebase emulators on your computer, which the Pi and the phone reach over
the Wi-Fi. From the repo root:

```bash
npm install
npm run dev:with_uwb
```

It prints `sign in to the app as admin@sportcam.dev or climber@sportcam.dev,
password sportcam-dev`. (It also runs a simulated camera, `dev-camera-key`;
the real one gets its own key below.) Your computer's firewall must let the
Pi and the phone reach ports **5001**, **8080** and **9099**.

On the Pi, point the camera at it, with your computer's address for
`<computer>` (e.g. `192.168.1.20`):

```bash
cd ~/sportcam/src/with_uwb/device
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
[full build's step 4](../setup/14-software-setup.md#4-connect-it-to-firebase-optional)
and drop `FIRESTORE_EMULATOR_HOST`.
