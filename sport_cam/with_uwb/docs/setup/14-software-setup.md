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
([09](../../../docs/design/09-direct-connection-and-app.md)).

Once, on a computer: `./scripts/firebase-setup.sh <project-id>`, then
`npm run deploy` ([08](../../../docs/design/08-recordings-and-cloud.md#deploying-the-firebase-backend)).
Setup prints three values and writes the camera's key file. Copy the key
file to the Pi:

```bash
scp sportcam-firebase.json pi@sportcam.local:/home/pi/   # then delete it on your computer
```

Set the values in `~/sportcam/src/with_uwb/device/sportcam/config.py`:

| Setting | Set it to |
| --- | --- |
| `FIREBASE_PROJECT` | your project id |
| `CAMERA_KEY` | the key the setup printed — it's also in your app link |
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

Sweeps each axis to its soft limits and back. Adjust in `config.py`:

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

Paste the `RANGE_BIAS_M = (…)` it prints. If it warns that a bias is over
30 cm, the setup is wrong (distance, aim, or anchor order), not the radios.
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

```bash
sudo cp ~/sportcam/src/with_uwb/device/sportcam-head.service ~/sportcam/src/with_uwb/device/sportcam-wifi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sportcam-head sportcam-wifi
journalctl -u sportcam-head -f          # watch it start; Ctrl-C to stop
```

**Done when** the LED ring is blue (idle): solid, or breathing slowly if the camera can see you.

| Operation | Command / note |
| --- | --- |
| Apply a `config.py` change | `sudo systemctl restart sportcam-head`. Also resets the battery gauge to "full" (step 8): don't restart mid-session on a part-used bank |
| Before running `rangecal`, `bearingcal`, `focuscal` or `ptzcheck` | `sudo systemctl stop sportcam-head` (they need exclusive access to the hardware) |

## 8. Live checks

With the service running and the tag **off**, the ring is blue (breathing slowly while it sees you). Do
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
   3, 2, 1), then turns breathing red, starts recording, and the app chimes.
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

- **The web app, from anywhere.** Open the link `firebase-setup.sh` printed
  (`https://<project>.web.app/#key=…`) on your phone or computer; add it to
  your home screen. It shows the camera's state and a live preview, drives
  it, and plays the recording library. Needs step 4.
- **The native app, on the camera's Wi-Fi** — full-rate video with no internet:
  `cd src/app_flutter && flutter pub get && flutter run`. It finds the camera by
  mDNS ([09](../../../docs/design/09-direct-connection-and-app.md)). Add
  `--dart-define=SPORTCAM_FALLBACK=https://<project>.web.app --dart-define=SPORTCAM_CAMERA_KEY=<key>`
  and it reaches the camera through Firebase when it's not on the same
  network. For the record start/stop chimes to play with the phone in your
  bag, apply the platform setup in
  [`src/app_flutter/README.md`](../../../src/app_flutter/README.md) first, and
  allow notifications on Android when asked.

Both word their buttons for this build: the camera reports
`TRACKING_MODE = "with_uwb"` itself ([07 — Tracking mode](../../../docs/design/07-backend-and-app.md#tracking-mode)).

**At a new gym:** power on, join the camera's `SportCam-Setup` hotspot from
your phone, open `http://10.42.0.1` and pick the gym's network. The camera
remembers it.

## Values you end up setting

All in `src/with_uwb/device/sportcam/config.py`:

| Setting | From |
| --- | --- |
| `PAN_SIGN`, `TILT_SIGN`, soft limits | step 5a, `ptzcheck` |
| `RANGE_BIAS_M` | step 6a, `rangecal` |
| `UWB_A3_UP_M`, `UWB_A3_BACK_M` | step 6b, only if the mast differs |
| `ZOOM_CURVE` | step 6c, by hand |
| `FOCUS_GRID` | step 6d, `focuscal` |
| `TAG_BEARING_SIGMA_DEG`, `TAG_BEARING_CORR_S` | step 6e, `bearingcal` |
| `UWB_THETA_SIGN` | step 8 |
| `AUTO_SESSION`, the `ACQUIRE_*` and `FOUND_*` settings | defaults are fine; see [05](../design/05-tracking-system.md) to tune |
| `FIREBASE_PROJECT`, `CAMERA_KEY`, `UPLOAD_API_BASE` | step 4, only with Firebase |
