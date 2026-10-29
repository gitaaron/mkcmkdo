# 14 — Software setup

Procedure from a blank SD card to a tracking camera. Each step ends with a
**Done when** check; failures map to rows in
[15 — Verification](15-verification.md#on-the-bench-before-the-first-session).

| | |
| --- | --- |
| Prerequisite | [assembly guide](assembly/index.html) and [wiring guide](12-wiring.md) complete, through "Power-on checks" |
| Equipment | the assembled camera on its tripod; 16 GB+ microSD; a Mac with this repo checked out and [Raspberry Pi Imager](https://www.raspberrypi.com/software/) (step 1); tape measure; phone or laptop on the same Wi-Fi |
| Duration | ≈ **1 h**, mostly calibration |

## 1. Raspberry Pi OS (on your Mac)

Puts the OS on the microSD card with your Wi-Fi and your Mac's SSH key
already in it, so the Pi joins the network by itself and never needs a
screen or keyboard.

**a. An SSH key on your Mac.** Open Terminal (Applications → Utilities →
Terminal) and run:

```bash
ls ~/.ssh/id_ed25519.pub || ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
pbcopy < ~/.ssh/id_ed25519.pub        # the public key, onto the clipboard for c
```

The first line prints the key's path if you already have one, and makes one
(no passphrase) if you don't. A key with a passphrase works too, once it is
in the keychain: `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`.

**b. Raspberry Pi Imager.** On
[raspberrypi.com/software](https://www.raspberrypi.com/software/), click
**Download for macOS**, open the `.dmg` and drag **Raspberry Pi Imager**
into **Applications** (or: `brew install --cask raspberry-pi-imager`). Open
it from Applications, and click **Open** if macOS asks whether you're sure.

**c. Write the card.** Put the microSD card in your Mac's card slot or a USB
card reader. In Imager, page by page:

| Page | What to do |
| --- | --- |
| **Device** | **Raspberry Pi 4** → **Next** |
| **OS** | **Raspberry Pi OS (other)** → **Raspberry Pi OS (Legacy, 64-bit) Lite** → **Next**. Legacy is Bookworm (Debian 12), which the camera software is tested on; the newer one at the top of the list is not |
| **Storage** | your card, recognisable by its size (leave **Exclude system drives** on) → **Next** |
| **Customisation: Hostname** | `sportcam` → **Next** |
| **Customisation: Localisation** | your capital city (e.g. Ottawa). It sets the time zone, the keyboard and the Wi-Fi country → **Next** |
| **Customisation: User** | username `pi` (the services assume `/home/pi`), and a password → **Next** |
| **Customisation: Wi-Fi** | **Secure network**; the SSID and password of the network your Mac is on. The SSID is case-sensitive. Not a guest network: those usually keep devices from seeing each other → **Next** |
| **Customisation: Remote access** | turn on **Enable SSH**, choose **public key authentication**, and paste (⌘V) the key from a. (**Browse** instead: ⌘⇧. shows the hidden `.ssh` folder.) → **Next** |
| **Customisation: Raspberry Pi Connect** | leave it off → **Next** |
| **Writing** | check the summary → **Write** → **I understand, erase and write** → your Mac's password when macOS asks. Writing and verifying takes 5–10 min → **Finish** |

If macOS says *"The disk you inserted was not readable by this computer"*,
click **Ignore**. Imager ejects the card when it's done; take it out.

**d. Boot.** With the Pi off, push the card into the slot on the underside
of the Pi, contacts towards the board. Switch the camera on at its rocker.
The first boot takes 2–3 minutes and restarts once by itself; the green LED
flickers while it works.

**e. Log in from your Mac:**

```bash
ping -c 3 sportcam.local
ssh pi@sportcam.local
```

The first time, ssh asks *"Are you sure you want to continue connecting
(yes/no/[fingerprint])?"*: type `yes`. You land at `pi@sportcam:~ $` with no
password asked. Type `exit`.

**Done when:** `ssh pi@sportcam.local` logs in without asking for a
password.

| If | Then |
| --- | --- |
| `ping: cannot resolve sportcam.local` 5 minutes after power-on | the Pi isn't on the Wi-Fi, or your network hides it. Look for `sportcam` in your router's list of devices. Listed: use its IP address in place of `sportcam.local`, here and in step 2 (`--host`). Not listed: the SSID or password is wrong; write the card again |
| ssh asks for `pi@sportcam.local's password`, or says `Permission denied (publickey)` | the key in Imager isn't this Mac's: write the card again with the key from a |
| `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!` | the card was written again since you last logged in: `ssh-keygen -R sportcam.local`, then ssh again |

## 2. Install the camera software (from your Mac)

From the repo's root, on your Mac:

```bash
./scripts/pi-install.sh without_uwb
```

It logs in to `pi@sportcam.local` and does the rest; 20–30 minutes the
first time, most of it the OS upgrade. The Pi reboots near the end. The
code comes from your checkout, uncommitted edits included, so the Pi runs
what you have.

| It does | Detail |
| --- | --- |
| Interfaces | I2C (PTZ controller, battery gauge) and SPI (LED ring) turned on |
| OS | upgraded; `python3-picamera2`, `python3-opencv`, `i2c-tools` and `pip` installed |
| Pan and tilt | pigpio (from apt, or built from [source](https://github.com/joan2937/pigpio) if apt has none), with `pigpiod` enabled: the servos run off the Pi's hardware PWM through it (`SERVO_DRIVER = "pigpio"`, [04 — Servo drive](../../design/04-electronics.md#servo-drive)), and the service talks to it over a local socket, so it doesn't run as root. Analog audio off: it shares the PWM block |
| Code | `src/without_uwb/device` → `~/sportcam/src/without_uwb/device`. A `config.py` already there is kept, with your calibration; `--reset-config` replaces it |
| Python packages | `requirements.txt`, system-wide: both services use the system `python3`, the Wi-Fi portal runs as root, and Picamera2 is apt-only |
| Tests | the offline tests, before anything is put in place |
| Person detector | MobileNet-SSD's weights (`getmodel`, ≈ 48 MB download, 19 MB kept). HOG works out of the box; MobileNet-SSD finds climbers in poses HOG misses ([06 — The two detectors](../../design/06-device-software.md#the-two-detectors)), and the comparison in [verification](15-verification.md) needs it |
| Checks, after the reboot | the camera is found (if not, it adds `dtoverlay=imx477` and reboots once more); `0c` (PTZ) and `40` (gauge) on I2C; `pigpiod` answers |

**Done when:** it ends with `All set`. A failed check names the connection
to look at: fix it and run the script again. Every part of it is safe to
repeat, and running it again is also how you update the Pi after changing
the code on your Mac.

A head still wired as the Arducam kit came, with the servo leads on the PTZ
controller, doesn't use pigpio: set `SERVO_DRIVER = "arducam"` in
`config.py` (whole-degree steps).

## 3. Connect it to Firebase (optional)

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
| Accounts | prints the console steps: turn on **Email/Password** sign-in, find the **Web API key** |
| No `gcloud` installed | prints the equivalent console steps instead |

Then, in the Firebase console: upgrade the project to the **Blaze**
(pay-as-you-go) plan (Cloud Functions need it, and the free-tier quotas still
apply); turn on **Authentication → Sign-in method → Email/Password**; and
note the **Web API key** (Project settings → General) for the app. Deploy,
and make yourself the first admin:

```bash
npm run deploy
gcloud auth application-default login
GCLOUD_PROJECT=<project-id> npm run add-admin -w @sportcam/backend -- you@example.com '<password>'
```

Everyone else is added from the app (account menu → **People** → **Add
person**); there is no sign-up.

What that deploys: [08 — The deployed backend](../../design/08-recordings-and-cloud.md#the-deployed-backend).
Optionally, add a lifecycle rule to the bucket in the Cloud Storage console
(e.g. delete after 365 days) so the library doesn't grow forever.

Setup printed three values and wrote the camera's key file. Copy the key
file to the Pi:

```bash
scp sportcam-firebase.json pi@sportcam.local:/home/pi/   # then delete it on your computer
```

Set the values in `~/sportcam/src/without_uwb/device/sportcam/config.py`:

| Setting | Set it to |
| --- | --- |
| `FIREBASE_PROJECT` | your project id |
| `CAMERA_KEY` | the key the setup printed |
| `UPLOAD_API_BASE` | `https://<project>.web.app` |
| `FIREBASE_CREDENTIALS` | leave as `/home/pi/sportcam-firebase.json` |

**Done when:** after the services are installed (step 6), `journalctl -u sportcam-head`
shows `[cloud] connected to <project>`, and your app link shows the camera
online.

## 4. Bench checks: camera and motion

On the Pi (`ssh pi@sportcam.local`), run everything from
`~/sportcam/src/without_uwb/device`.

**a. Camera:** `rpicam-hello -t 2000` shows a picture. If it does not, see
step 2's checks.

**b. Pan and tilt:**

```bash
python3 -m sportcam.ptzcheck
```

Sweeps each axis to its soft limits and back, then creeps the pan 0° → 3°
in tenths of a degree. Adjust in `config.py`:

- the creep should be smooth. Ticks of about a degree mean the pan servo is
  still on the PTZ controller, not GPIO12 ([wiring, M1–M6](12-wiring.md#servos));
- if a commanded ±45° measures short or long (phone level on the camera),
  widen or narrow `SERVO_US_AT_0` / `SERVO_US_AT_180` evenly about 1500 µs;

- narrow `PAN_MIN/MAX_DEG` or `TILT_MIN/MAX_DEG` if anything binds. The
  search sweeps the whole pan range, so the ends of it matter more than they
  would if the camera only followed someone;
- flip `PAN_SIGN` if a positive pan turns the lens the wrong way;
- flip `TILT_SIGN` if a positive tilt does not point the lens **up**. Get this
  wrong and the search steps its tilt rows the wrong way and a person
  standing up sends the camera to the floor.

**Done when** both axes reach their limits without the ribbon or lens
touching anything, and the lens is left centred.

## 5. Calibrate

In order. Each step prints a line for `config.py` or states the change.

**a. Zoom curve.** Manual (no tool yet). Place a metre rule at a known
distance, step the raw zoom (`OPT_ZOOM`) across 3000–20000, and record the
visible width at each stop → field of view → focal length. Enter the
`(mm, raw)` pairs in `ZOOM_CURVE`. Default: a straight line between the
stops (framing approximate). The lens is open-loop; both lens motors are
homed against their stops at boot.

**b. Focus grid.** High-contrast target (printed chart or newspaper)
at each distance in turn, in the filming light:

```bash
python3 -m sportcam.focuscal 2
python3 -m sportcam.focuscal 5
python3 -m sportcam.focuscal 10
python3 -m sportcam.focuscal 30
```

After the last run, paste the `FOCUS_GRID = {…}` it prints. Until then,
focus depends on zoom alone and is soft away from one distance. The search
sweep focuses at `SEARCH_FOCUS_M` (5 m); once someone is found, focus follows
the distance estimated from their size in the frame.

## 6. Install the services

Give the camera's setup hotspot its own password, and write it on the
head's label: you need it only for the setup page, the fallback to the QR
code ([Pairing](../../product/01-requirements.md#pairing)).

```bash
sudo mkdir -p /etc/sportcam
tr -dc 'a-z0-9' </dev/urandom | head -c 10 | sudo tee /etc/sportcam/hotspot-password; echo
sudo chmod 600 /etc/sportcam/hotspot-password
```

```bash
sudo cp ~/sportcam/src/without_uwb/device/sportcam-head.service ~/sportcam/src/without_uwb/device/sportcam-wifi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sportcam-head sportcam-wifi
journalctl -u sportcam-head -f          # watch it start; Ctrl-C to stop
```

**Done when** the LED ring chases white (connecting), then turns blue (awake): solid, or breathing slowly if the camera can see you. Left alone for 30 s with no app showing the live view, it goes to sleep: one dim blue pixel, camera off (**Wake up** in the app brings it back). Blinking white instead: it has no Wi-Fi it knows; pair it as below.

| Operation | Command / note |
| --- | --- |
| Apply a `config.py` change | `sudo systemctl restart sportcam-head`. Also resets the battery gauge to "full" (step 8.6): don't restart mid-session on a part-used bank |
| Before running `focuscal` or `ptzcheck` | `sudo systemctl stop sportcam-head` (they need exclusive access to the hardware) |

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

## 7. The app

The phone app: `cd src/app_flutter && flutter pub get && flutter run`.

- **On the camera's Wi-Fi**: it finds the camera by mDNS
  ([09](../../design/09-direct-connection-and-app.md)) and shows full-rate
  video, with no internet needed.
- **From anywhere**: add
  `--dart-define=SPORTCAM_FALLBACK=https://<project>.web.app --dart-define=SPORTCAM_CAMERA_KEY=<key> --dart-define=SPORTCAM_FIREBASE_API_KEY=<Web API key>`
  (printed by `firebase-setup.sh`) and it reaches the camera through
  Firebase when it's not on the same network: state, a live preview,
  control and the recording library. It then opens on a sign-in page:
  each person signs in with the account an admin made them, and sees
  only the recordings they started. Needs step 3.

Apply the platform setup in
[`src/app_flutter/README.md`](../../../src/app_flutter/README.md) first
(iOS `NSBonjourServices`; Android multicast and cleartext permissions).
Without it, discovery silently finds nothing, and the record start/stop
chimes don't play with the phone in your bag. Allow notifications on Android
when asked.

It words its buttons for this build: the camera reports
`TRACKING_MODE = "without_uwb"` itself ([07 — Tracking mode](../../design/07-backend-and-app.md#tracking-mode)).

**At a new gym:** power on. The ring chases white while the camera looks
for a network it knows, then blinks white: it's pairing. On your phone
(already on the gym's Wi-Fi) open the network's share code (Android:
Settings → Wi-Fi → the network → **Share**; iPhone, iOS 18+: Passwords →
Wi-Fi → the network → **Show Network QR Code**) and hold it 15–30 cm in
front of the lens. The ring chases white, then turns blue. The camera
remembers the network. Code not read: join the `SportCam-Setup` hotspot
(password on the label), open `http://10.42.0.1`, pick the network and
paste the password.

## 8. Live checks

With the service running, the ring is blue (breathing slowly while it sees you; one dim pixel once it has gone to sleep, and **Wake up** in the app brings it back). Do these in order: the
tuning steps only mean something once the signs are right.

1. **First run.** Stand 3–5 m from the camera, in the room you will film in,
   upright and facing it. In the app press **Track & record**. The status
   reads "Looking for a person…" and the ring shows a green light chasing
   round while the camera zooms wide and sweeps left and right, stepping to the
   next tilt row at each end; the app pings every 3 s while it searches. When it sees you it stops and follows you;
   the ring fills with green over 3 s and the app beeps 3, 2, 1. Still in
   frame at the end, the ring turns solid red, recording starts and the
   app chimes. The
   zoom then settles with you filling about two-thirds of the frame.
2. **Sign checks.** Walk slowly to one side while it follows. If it turns
   *away* from you, flip `PAN_SIGN`; if it tilts away when you crouch or
   stand, flip `TILT_SIGN` (step 4b). Restart the service after each change.
3. **Sweep coverage.** Stand still out of view and press **Track & record**
   again from awake; watch one full sweep. The lens should pass over every
   part of the room you care about, without binding at either end of the pan.
   If the lens can't see your usual spot, adjust `SEARCH_TILT_ROWS_DEG`
   (tilt for each pass; the default rows are 5° and 22°) and, if something
   binds, `PAN_MIN_DEG` / `PAN_MAX_DEG`. A slower `SEARCH_PAN_DPS` helps if
   the camera keeps sweeping straight past you.
4. **Detector threshold.** If it stops the sweep for a coat stand, a chair or
   a bag, raise `DETECT_HIT_THRESHOLD` a little (0.3 by default; higher means
   fewer false people). If it sweeps past real people, lower it. Tune it in
   your own room and light, since that is where false positives come from.
5. **Zoom out, then re-sweep.** While it records you zoomed in, step a
   little to one side, just out of the shot: after about 2 s
   (`LOST_ZOOM_OUT_S`) it should zoom straight out, find you in the wide
   shot and close back in. Then walk right out of view and wait. After
   about 6 s (`RESEARCH_AFTER_S`) the camera should start sweeping again and follow
   the first person it finds. If nobody is ever found it gives up to awake after
   `SEARCH_GIVE_UP_S` (180 s) when not recording.
6. **Battery gauge.** Counts energy used since the service started, assuming
   a full bank at that point. Start on a fully charged bank; compare
   minutes-left with a stopwatch over the first 30 min. No app reset control.

If it keeps sweeping and the app says it can't find anyone, the camera is
pointing somewhere you aren't, or the detector can't see you: recheck step 4,
face the camera, and make sure the room is lit.

## 9. Tuning

Once the live checks pass, tune by symptom. Change one parameter at a time
and film a short walk or climb after each. Defaults are in
`src/without_uwb/device/sportcam/config.py`; what each one means:
[05 — Parameter reference](../design/05-tracking-system.md#parameter-reference).

| Symptom | Likely cause | Adjust |
| --- | --- | --- |
| Camera sweeps past a person, or never stops | detector missing them; sweep too fast; light | lower `DETECT_HIT_THRESHOLD` (0.3 → 0.2), lower `SEARCH_PAN_DPS`; check the preview |
| Records furniture or empty wall | false positives | raise `DETECT_HIT_THRESHOLD`; raise `FOUND_CONFIRM_S` |
| Camera oscillates around the person | gain too high for the detection rate | lower `TRACK_PAN_GAIN` / `TRACK_TILT_GAIN` (0.6 → 0.45); widen `TRACK_DEADBAND_FRACTION` |
| Camera lags a mover and the person drifts out of frame | gain too low | raise the gains toward 0.8; raise `PAN_MAX_DPS`; widen `ZOOM_FILL_TARGET` margin (lower it) |
| Shot "breathes" in and out | zoom too reactive | lower `ZOOM_VISION_GAIN`; raise `ZOOM_MIN_STEP_MM` |
| Person clipped at the edge | fill target too high or guard too late | lower `ZOOM_FILL_TARGET` (0.65 → 0.55); raise `ZOOM_GUARD_EDGE` |
| Bystanders take over | gate too wide | lower `TRACK_GATE_FRACTION` (0.45 → 0.3) |
| Tracking jumps to someone else after a short loss | re-search too eager | raise `RESEARCH_AFTER_S`; lower `TRACK_GATE_FRACTION` |
| Gives up on an empty room too soon, or never | give-up timer | `SEARCH_GIVE_UP_S` |
| Person seen late or missed at the sweep's ends | tilt rows miss them | edit `SEARCH_TILT_ROWS_DEG` for your lens height and room |
| Detector too slow on the Pi | strip too wide | lower `DETECT_STRIP_FRACTION`; lower `DETECT_DOWNSCALE_W` (hurts small, far people) |

## Values you end up setting

All in `src/without_uwb/device/sportcam/config.py`:

| Setting | From |
| --- | --- |
| `DETECTOR` | `"hog"` until `detectbench` ([15](15-verification.md)) shows `"ssd"` finding the climber more often at 3 fps or better |
| `SERVO_DRIVER` | step 2: `"pigpio"` once the servo leads are on GPIO12/13, `"arducam"` if not |
| `PAN_SIGN`, `TILT_SIGN`, soft limits (`PAN_MIN/MAX_DEG`, `TILT_MIN/MAX_DEG`), `SERVO_US_AT_0/180` | step 4b, `ptzcheck`, then step 8 |
| `ZOOM_CURVE` | step 5a, by hand |
| `FOCUS_GRID` | step 5b, `focuscal` |
| `SEARCH_PAN_DPS`, `SEARCH_TILT_ROWS_DEG` | step 8.3: how fast and where the sweep looks |
| `DETECT_HIT_THRESHOLD` | step 8.4: raise for fewer false people |
| `TRACK_PAN_GAIN`, `TRACK_TILT_GAIN` | step 8.2: raise if the camera lags a fast mover, lower if it oscillates |
| `RESEARCH_AFTER_S`, `SEARCH_GIVE_UP_S` | step 8.5: how long before re-sweeping, and before giving up on an empty room |
| `FOUND_CONFIRM_S`, `FOUND_LOST_S`, `ACQUIRE_STALLED_S` and the rest | defaults are fine; tune by symptom in step 9 |
| `FIREBASE_PROJECT`, `CAMERA_KEY`, `UPLOAD_API_BASE` | step 3, only with Firebase |
