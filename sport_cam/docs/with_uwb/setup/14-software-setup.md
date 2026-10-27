# 14 — Software setup

Procedure from a blank SD card to a tracking camera. Each step ends with a
**Done when** check; failures map to rows in
[15 — Verification](15-verification.md#on-the-bench-before-the-first-session).

| | |
| --- | --- |
| Prerequisite | [assembly guide](assembly/index.html) and [wiring guide](12-wiring.md) complete, through "Power-on checks" |
| Equipment | the assembled camera on its tripod; four ULA1 modules (three anchors, one tag); 16 GB+ microSD; computer with the Arduino IDE and [Raspberry Pi Imager](https://www.raspberrypi.com/software/); tape measure; phone or laptop on the same Wi-Fi |
| Duration | ≈ **2 h**, mostly calibration |

## 1. Flash the radios (on your computer)

The ULA1 is an ESP32, programmed over its USB plug from the Arduino IDE with
the ESP32 board package and the vendor's DW1000 library installed (both are
in the vendor's ULA1 package).

| Board | Sketch | DIP switch 1 2 3 4 | Vendor name |
| --- | --- | --- | --- |
| A1 (arm, +Y) | `RTLS_Anchor` | ON off off off | A0 |
| A2 (arm, −Y) | `RTLS_Anchor` | ON off off ON | A1 |
| A3 (mast) | `RTLS_Anchor` | ON off ON off | A2 |
| Tag (wearable) | `RTLS_Tag` | off off off off | T0 |

- Use the **RTLS** pair, not `RangingAnchor`/`RangingTag`. Only RTLS sends the
  one frame carrying every range that the camera reads.
- The role and address come from the board's **4-way DIP switch**, not from
  the sketch: switch 1 ON makes it an anchor, and switches 2–4 are its
  address in binary (manual §2). The vendor numbers anchors from **A0**, so
  our A1–A3 are its A0–A2, and their ranges arrive as RANGE0–2. Label the
  boards with our names.
- The firmware ranges A0–A3 in turn. With no A3 fitted, that slot is simply
  missing from the mask (`07`); check the cycle rate in step 5b.

**Done when:** with the tag powered, opening any anchor's port at 115200 baud
in the Arduino serial monitor shows lines starting `mc 07 …`.

## 2. Raspberry Pi OS

In Raspberry Pi Imager choose **Raspberry Pi OS (64-bit), Bookworm** (Lite is
fine), and in its settings:

- **username `pi`**. The services assume `/home/pi`.
- hostname `sportcam`
- your Wi-Fi, and SSH enabled

Boot it in the camera, SSH in (`ssh pi@sportcam.local`), then:

```bash
sudo raspi-config nonint do_i2c 0       # PTZ controller + battery gauge
sudo raspi-config nonint do_spi 0       # LED ring
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

**Done when:** `rpicam-hello -t 2000` shows the camera, and
`i2cdetect -y 1` lists `0c` (PTZ) and `40` (gauge). If the camera is missing,
add `dtoverlay=imx477` to `/boot/firmware/config.txt` and reboot.

## 3. Install the camera software

```bash
sudo apt install -y git python3-pip python3-picamera2 python3-opencv i2c-tools
git clone https://github.com/gitaaron/sport_cam.git ~/sportcam
cd ~/sportcam/src/with_uwb/device
sudo pip3 install --break-system-packages -r requirements.txt
```

**Pan and tilt driver.** The servos are driven by the Pi's hardware PWM
through the pigpio daemon (`SERVO_DRIVER = "pigpio"`,
[04 — Servo drive](../../design/04-electronics.md#servo-drive)). The service
talks to the daemon over a local socket, so it still doesn't run as root.
Analog audio uses the same PWM block, so turn it off:

```bash
sudo apt install -y pigpio python3-pigpio
sudo systemctl enable --now pigpiod
echo 'dtparam=audio=off' | sudo tee -a /boot/firmware/config.txt
sudo reboot
```

If apt has no `pigpio` package, build it from
[source](https://github.com/joan2937/pigpio) (`make && sudo make install`)
and install its `pigpiod` unit. A head still wired as the Arducam kit came,
with the servo leads on the PTZ controller, needs none of this: set
`SERVO_DRIVER = "arducam"` instead (whole-degree steps).

**Done when:** `pigs hwver` prints a number (pigpiod is up).

System-wide install rationale: both services use the system `python3`; the
Wi-Fi portal runs as root; Picamera2 is apt-only (a virtualenv would need
`--system-site-packages` and edited unit files).

**Done when:** the offline tests pass:

```bash
for t in tests/test_*.py; do python3 $t | tail -1; done
```

## 4. Connect it to Firebase (optional)

Firebase provides remote access and the recordings library. Skipping this
step gives **stand-alone** operation: direct phone connection only;
recordings stay on the card
([09](../../design/09-direct-connection-and-app.md)).

Once, on a computer, from the repo root (log in first with
`npx firebase login`):

```bash
./scripts/firebase-setup.sh <project-id>
```

| It does | Result |
| --- | --- |
| Create the project | `src/backend/.firebaserc` |
| Create the Firestore database and the bucket | `<project>-recordings` |
| Let the function sign URLs | its service account gets Token Creator on itself |
| Create the camera's service account | Firestore-only; key saved as `sportcam-firebase.json` |
| Make the camera key | printed with the `config.py` lines and the phone app's `--dart-define`s |
| No `gcloud` installed | prints the equivalent console steps instead |

Then upgrade the project to the **Blaze** (pay-as-you-go) plan in the
Firebase console: Cloud Functions need it, and the free-tier quotas still
apply. Deploy:

```bash
npm run deploy
```

What that deploys: [08 — The deployed backend](../../design/08-recordings-and-cloud.md#the-deployed-backend).
Optionally, add a lifecycle rule to the bucket in the Cloud Storage console
(e.g. delete after 365 days) so the library doesn't grow forever.

Setup printed three values and wrote the camera's key file. Copy the key
file to the Pi:

```bash
scp sportcam-firebase.json pi@sportcam.local:/home/pi/   # then delete it on your computer
```

Set the values in `~/sportcam/src/with_uwb/device/sportcam/config.py`:

| Setting | Set it to |
| --- | --- |
| `FIREBASE_PROJECT` | your project id |
| `CAMERA_KEY` | the key the setup printed |
| `UPLOAD_API_BASE` | `https://<project>.web.app` |
| `FIREBASE_CREDENTIALS` | leave as `/home/pi/sportcam-firebase.json` |

**Done when:** after the services are installed (step 7), `journalctl -u sportcam-head`
shows `[cloud] connected to <project>`, and your app link shows the camera
online.

## 5. Bench checks: motion and radios

Run everything from `~/sportcam/src/with_uwb/device`.

**a. Pan and tilt:**

```bash
python3 -m sportcam.ptzcheck
```

Sweeps each axis to its soft limits and back, then creeps the pan 0° → 3°
in tenths of a degree. Adjust in `config.py`:

- the creep should be smooth. Ticks of about a degree mean the pan servo is
  still on the PTZ controller, not GPIO12 ([wiring, M1–M6](12-wiring.md#servos));
- if a commanded ±45° measures short or long (phone level on the camera),
  widen or narrow `SERVO_US_AT_0` / `SERVO_US_AT_180` evenly about 1500 µs;

- narrow `PAN_MIN/MAX_DEG` or `TILT_MIN/MAX_DEG` if anything binds;
- flip `PAN_SIGN` if a positive pan turns the lens the wrong way;
- flip `TILT_SIGN` if a positive tilt does not point the lens **up**. Get this
  wrong and tracking sends the camera to the floor.

**b. Radios:**

```bash
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200     # Ctrl-] to quit
```

**Done when** it streams `mc 07 …` at 8–20 lines a second.

- `mc 03` means A3 is not being ranged: check the tag is set for 3 anchors.
- Lines with only one range mean the Ranging sketches are loaded instead of
  RTLS: reflash (step 1).
- No `/dev/ttyUSB0` means the data anchor is not plugged into the Pi.

## 6. Calibrate

In order. Each step prints a line for `config.py` or states the change.

**a. Range bias (required).** Centre the camera (`ptzcheck` leaves it
centred). Tape the tag **5.00 m** out, straight in front of the lens, at the
height of the A1/A2 boards, antenna facing the camera. Then:

```bash
python3 -m sportcam.rangecal 5
```

It takes 300 frames and compares each anchor's median range with the
geometry. Paste the `RANGE_BIAS_M = (…)` it prints. If it warns that a bias
is over 30 cm, the setup is wrong (distance, aim, or anchor order), not the
radios. It also prints each anchor's noise: well above `UWB_RANGE_SIGMA_M`
(0.10 m) means multipath or a badly placed anchor, so look at that first.
On the 250 mm mast, 5 cm of A3 error is about 12° of tilt, so don't skip
this.

**b. A3 geometry.** If you built the mast to the drawings (dowel 246 mm,
pushed fully home), the defaults are right. Otherwise measure the A3 board's
height above the A1/A2 boards and its distance behind the pan axis, and set
`UWB_A3_UP_M` and `UWB_A3_BACK_M` (in metres).

**c. Zoom curve.** Manual (no tool yet). Place a metre rule at a known
distance, step the raw zoom (`OPT_ZOOM`) across 3000–20000, and record the
visible width at each stop → field of view → focal length. Enter the
`(mm, raw)` pairs in `ZOOM_CURVE`. Default: a straight line between the
stops (framing approximate). The lens is open-loop; both lens motors are
homed against their stops at boot.

**d. Focus grid.** High-contrast target (printed chart or newspaper)
at each distance in turn, in the filming light:

```bash
python3 -m sportcam.focuscal 2
python3 -m sportcam.focuscal 5
python3 -m sportcam.focuscal 10
python3 -m sportcam.focuscal 30
```

After the last run, paste the `FOCUS_GRID = {…}` it prints. Until then,
focus depends on zoom alone and is soft away from one distance.

**e. Bearing noise (recommended).** When someone stands close beside the
climber, the camera averages the tag's bearing until it can tell which of
them is wearing it ([05](../design/05-tracking-system.md#telling-the-tag-wearer-from-everyone-else)).
How long it averages depends on two numbers that are estimates until you
measure them: how much the bearing wanders (`TAG_BEARING_SIGMA_DEG`, 7°) and
how fast (`TAG_BEARING_CORR_S`, 0.35 s). After step a, centre the camera, and
have someone wear the tag as they will when climbing and stand still 5 m out,
straight in front of the lens, facing it. Keep everyone else out of the way.

```bash
python3 -m sportcam.bearingcal 5
python3 -m sportcam.bearingcal 10        # then again at 10 m
```

Each run takes a minute and prints the measured σ and τ beside the values in
`config.py`. Paste the larger σ and the longer τ of the two runs. Higher than
the defaults means the camera would otherwise decide too soon beside a
belayer. Lower means it can decide sooner. If it warns that the mean is more
than 3° off straight ahead, the wearer isn't on the boresight or step a
needs redoing.

## 7. Install the services

Give the camera's setup hotspot its own password, and write it on the
head's label: you need it only for the setup page, the fallback to the QR
code ([Pairing](../../product/01-requirements.md#pairing)).

```bash
sudo mkdir -p /etc/sportcam
tr -dc 'a-z0-9' </dev/urandom | head -c 10 | sudo tee /etc/sportcam/hotspot-password; echo
sudo chmod 600 /etc/sportcam/hotspot-password
```

```bash
sudo cp ~/sportcam/src/with_uwb/device/sportcam-head.service ~/sportcam/src/with_uwb/device/sportcam-wifi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sportcam-head sportcam-wifi
journalctl -u sportcam-head -f          # watch it start; Ctrl-C to stop
```

**Done when** the LED ring chases white (connecting), then turns blue (awake): solid, or breathing slowly if the camera can see you. Left alone for 30 s with no app showing the live view, it goes to sleep: one dim blue pixel, camera off (**Wake up** in the app brings it back). Blinking white instead: it has no Wi-Fi it knows; pair it as below.

| Operation | Command / note |
| --- | --- |
| Apply a `config.py` change | `sudo systemctl restart sportcam-head`. Also resets the battery gauge to "full" (step 8): don't restart mid-session on a part-used bank |
| Before running `rangecal`, `bearingcal`, `focuscal` or `ptzcheck` | `sudo systemctl stop sportcam-head` (they need exclusive access to the hardware) |

### Power switch

The rocker switch signals the Pi, and a latch keeps the power on until the Pi
has shut down ([wiring](12-wiring.md#power-latch)). The Pi needs three settings
for that. Without them, switching off cuts the power at once, like pulling the
cable.

```bash
# HOLD (GPIO17) high from the first second of boot; SENSE (GPIO27) falling = power key
sudo tee -a /boot/firmware/config.txt <<'CFG'

# SportCam power latch (12-wiring, S3 and S4)
gpio=17=op,dh
dtoverlay=gpio-shutdown,gpio_pin=27,active_low=1,gpio_pull=off
CFG

# A halted Pi turns its 3.3 V off, so HOLD drops and the latch lets go
sudo rpi-eeprom-config > /tmp/eeprom.txt
sed -i -e '/^POWER_OFF_ON_HALT/d' -e '/^WAKE_ON_GPIO/d' /tmp/eeprom.txt
printf 'POWER_OFF_ON_HALT=1\nWAKE_ON_GPIO=0\n' >> /tmp/eeprom.txt
sudo rpi-eeprom-config --apply /tmp/eeprom.txt

# A hung Pi or a hung shutdown resets, which drops HOLD too
sudo sed -i -e 's/^#\?RuntimeWatchdogSec=.*/RuntimeWatchdogSec=15s/' \
            -e 's/^#\?RebootWatchdogSec=.*/RebootWatchdogSec=2min/' /etc/systemd/system.conf
sudo reboot
```

**Done when:** the camera is awake, you switch off, and the ring goes dark
within a few seconds. About 10 s later the buck's LED goes out too: the Pi has
halted and the latch has cut the power. Switch on again and it boots as usual.
Then do it while recording: the clip appears in the library after the next
boot, playable to the end.

If it ever stays on after you switch off (a Pi that won't shut down), the
watchdog resets it within 2 minutes and that cuts the power. Unplugging the
bank's cable always works too.

## 8. Live checks

With the service running and the tag **off**, the ring is blue (breathing slowly while it sees you; one dim pixel once it has gone to sleep, and **Wake up** in the app brings it back). Do
these in order: the session check only means something once the bearing and
elevation are right.

1. **Bearing sign.** Start tracking from the app (step 9), walk to one side
   and watch the `pan` readout. If it moves the opposite way, set
   `UWB_THETA_SIGN = -1`.
2. **Elevation.** Hold the tag level with the anchors 5 m out: `tilt`
   settles near −1°. Raise it 2 m: near +21°. If tilt goes the wrong way, A3
   is not address 2 on its DIP switch, vendor name A2 (step 1). Stop tracking
   from the app afterwards.
3. **Tag-started session.** Switch the tag off and wait 5 s. Stand 5 m out and
   switch it on, standing upright and facing the camera. Within about a second
   the ring shows a green light chasing round (search) while the camera
   turns to you (the app pings while it searches). Once it has settled on
   you **and seen you** it fills with green over 3 s (found; the app beeps
   3, 2, 1), then turns solid red, starts recording, and the app chimes.
   The zoom then settles with you filling about two-thirds of the frame.
   Switch the tag off: 5 s later the ring returns to solid blue and the clip
   is saved. If nothing happens, check `AUTO_SESSION = True` and that ranging
   works (step 5b). If it keeps chasing and the app says "Can't pick you out", either
   someone is standing right beside you (step away: the camera only records
   the person where the tag is), or the camera is pointing somewhere you
   aren't: recheck steps 1–2.
4. **Battery gauge.** Counts energy used since the service started, assuming
   a full bank at that point. Start on a fully charged bank; compare
   minutes-left with a stopwatch over the first 30 min. No app reset control.

## 9. The app

The phone app: `cd src/app_flutter && flutter pub get && flutter run`.

- **On the camera's Wi-Fi**: it finds the camera by mDNS
  ([09](../../design/09-direct-connection-and-app.md)) and shows full-rate
  video, with no internet needed.
- **From anywhere**: add
  `--dart-define=SPORTCAM_FALLBACK=https://<project>.web.app --dart-define=SPORTCAM_CAMERA_KEY=<key>`
  (both printed by `firebase-setup.sh`) and it reaches the camera through
  Firebase when it's not on the same network: state, a live preview,
  control and the recording library. Needs step 4.

Apply the platform setup in
[`src/app_flutter/README.md`](../../../src/app_flutter/README.md) first
(iOS `NSBonjourServices`; Android multicast and cleartext permissions).
Without it, discovery silently finds nothing, and the record start/stop
chimes don't play with the phone in your bag. Allow notifications on Android
when asked.

It words its buttons for this build: the camera reports
`TRACKING_MODE = "with_uwb"` itself ([07 — Tracking mode](../../design/07-backend-and-app.md#tracking-mode)).

**At a new gym:** power on. The ring chases white while the camera looks
for a network it knows, then blinks white: it's pairing. On your phone
(already on the gym's Wi-Fi) open the network's share code (Android:
Settings → Wi-Fi → the network → **Share**; iPhone, iOS 18+: Passwords →
Wi-Fi → the network → **Show Network QR Code**) and hold it 15–30 cm in
front of the lens. The ring chases white, then turns blue. The camera
remembers the network. Code not read: join the `SportCam-Setup` hotspot
(password on the label), open `http://10.42.0.1`, pick the network and
paste the password.

## 10. Wearing the tag

Where the tag goes decides how often the climber's body blocks it
([why](../design/05-tracking-system.md#wearing-the-tag)).

General ranking: upper-arm band > back of cap/collar > chest/back pocket.
Avoid: wrist (arm swing moves the bearing), below the waist.

**Indoor climbing (bouldering / top-rope / lead).**

The climber faces the wall and the camera is behind them, so the back faces
the camera for most of the climb. A back-mounted tag is rarely body-shadowed.

| Discipline | Position | Rationale |
| --- | --- | --- |
| Top-rope / lead | **Rear of the harness waist belt, 5–10 cm off-spine** (strap bars through the belt webbing, or clipped beside the haul loop) | stable; camera-facing; clear of belay loop and rope |
| Bouldering | **Low back, off-spine, under the shirt** on an elastic waistband; or upper-arm band | no harness; off-spine for falls onto mats |
| Either | chalk-bag belt | works, but bags rotate and get repositioned; bearing jitters |

| Topic | Guidance |
| --- | --- |
| Front of torso | never: compressed against the wall on slabs and mantles; full occlusion |
| Spine | keep 5–10 cm off-spine; a 45 g pod is safe to land on elsewhere |
| Overhangs | body horizontal, tag may face the ceiling. Ranges continue (diffraction); A3 usually has the clearest path. Expect the noisiest angles, not loss of lock |
| Camera distance | 8–12 m from the wall base (works 2–20 m, [placement envelope](../design/05-tracking-system.md#camera-placement-envelope)). Tilt −45° to +85° covers a 15 m top-out from 7 m (≈ 65°) |
| Jumpy bearing | multipath from steel and concrete. Raise `UWB_RANGE_SIGMA_M` from 0.10 toward 0.15 before changing any gain |
| Sweat and chalk | USB-C slot faces down when worn; clean the case, not the board. Chalk is non-conductive. No top vents (sweat ingress) |

## Values you end up setting

All in `src/with_uwb/device/sportcam/config.py`:

| Setting | From |
| --- | --- |
| `SERVO_DRIVER` | step 3: `"pigpio"` once the servo leads are on GPIO12/13, `"arducam"` if not |
| `PAN_SIGN`, `TILT_SIGN`, soft limits, `SERVO_US_AT_0/180` | step 5a, `ptzcheck` |
| `RANGE_BIAS_M` | step 6a, `rangecal` |
| `UWB_A3_UP_M`, `UWB_A3_BACK_M` | step 6b, only if the mast differs |
| `ZOOM_CURVE` | step 6c, by hand |
| `FOCUS_GRID` | step 6d, `focuscal` |
| `TAG_BEARING_SIGMA_DEG`, `TAG_BEARING_CORR_S` | step 6e, `bearingcal` |
| `UWB_THETA_SIGN` | step 8 |
| `AUTO_SESSION`, the `ACQUIRE_*` and `FOUND_*` settings | defaults are fine; see [05](../design/05-tracking-system.md) to tune |
| `FIREBASE_PROJECT`, `CAMERA_KEY`, `UPLOAD_API_BASE` | step 4, only with Firebase |
