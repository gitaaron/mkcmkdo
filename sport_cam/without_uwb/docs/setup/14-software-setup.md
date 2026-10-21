# 14 — Software setup

Procedure from a blank SD card to a tracking camera. Each step ends with a
**Done when** check; failures map to rows in
[15 — Verification](15-verification.md#on-the-bench-before-the-first-session).

| | |
| --- | --- |
| Prerequisite | [assembly guide](assembly/index.html) and [wiring guide](12-wiring.md) complete, through "Power-on checks" |
| Equipment | the assembled camera on its tripod; 16 GB+ microSD; computer with [Raspberry Pi Imager](https://www.raspberrypi.com/software/); tape measure; phone or laptop on the same Wi-Fi |
| Duration | ≈ **1 h**, mostly calibration |

## 1. Raspberry Pi OS

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

## 2. Install the camera software

```bash
sudo apt install -y git python3-pip python3-picamera2 python3-opencv i2c-tools
git clone https://github.com/gitaaron/sport_cam.git ~/sportcam
cd ~/sportcam/src/without_uwb/device
sudo pip3 install --break-system-packages -r requirements.txt
```

System-wide install rationale: both services use the system `python3`; the
Wi-Fi portal runs as root; Picamera2 is apt-only (a virtualenv would need
`--system-site-packages` and edited unit files).

**Done when:** the offline tests pass:

```bash
for t in tests/test_*.py; do python3 $t | tail -1; done
```

## 3. Connect it to Firebase (optional)

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

Set the values in `~/sportcam/src/without_uwb/device/sportcam/config.py`:

| Setting | Set it to |
| --- | --- |
| `FIREBASE_PROJECT` | your project id |
| `CAMERA_KEY` | the key the setup printed — it's also in your app link |
| `UPLOAD_API_BASE` | `https://<project>.web.app` |
| `FIREBASE_CREDENTIALS` | leave as `/home/pi/sportcam-firebase.json` |

**Done when:** after the services are installed (step 6), `journalctl -u sportcam-head`
shows `[cloud] connected to <project>`, and your app link shows the camera
online.

## 4. Bench checks: camera and motion

Run everything from `~/sportcam/src/without_uwb/device`.

**a. Camera:** `rpicam-hello -t 2000` shows a picture. If it does not, see
step 1.

**b. Pan and tilt:**

```bash
python3 -m sportcam.ptzcheck
```

Sweeps each axis to its soft limits and back. Adjust in `config.py`:

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

```bash
sudo cp ~/sportcam/src/without_uwb/device/sportcam-head.service ~/sportcam/src/without_uwb/device/sportcam-wifi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sportcam-head sportcam-wifi
journalctl -u sportcam-head -f          # watch it start; Ctrl-C to stop
```

**Done when** the LED ring is blue (idle): solid, or breathing slowly if the camera can see you.

| Operation | Command / note |
| --- | --- |
| Apply a `config.py` change | `sudo systemctl restart sportcam-head`. Also resets the battery gauge to "full" (step 8.6): don't restart mid-session on a part-used bank |
| Before running `focuscal` or `ptzcheck` | `sudo systemctl stop sportcam-head` (they need exclusive access to the hardware) |

## 7. The app

- **The web app, from anywhere.** Open the link `firebase-setup.sh` printed
  (`https://<project>.web.app/#key=…`) on your phone or computer; add it to
  your home screen. It shows the camera's state and a live preview, drives
  it, and plays the recording library. Needs step 3.
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
`TRACKING_MODE = "without_uwb"` itself ([07 — Tracking mode](../../../docs/design/07-backend-and-app.md#tracking-mode)).

**At a new gym:** power on, join the camera's `SportCam-Setup` hotspot from
your phone, open `http://10.42.0.1` and pick the gym's network. The camera
remembers it.

## 8. Live checks

With the service running, the ring is blue (breathing slowly while it sees you). Do these in order: the
tuning steps only mean something once the signs are right.

1. **First run.** Stand 3–5 m from the camera, in the room you will film in,
   upright and facing it. In the app press **Track & record**. The status
   reads "Looking for a person…" and the ring shows a green light chasing
   round while the camera zooms wide and sweeps left and right, stepping to the
   next tilt row at each end; the app pings every 3 s while it searches. When it sees you it stops and follows you;
   the ring fills with green over 3 s and the app beeps 3, 2, 1. Still in
   frame at the end, the ring turns breathing red, recording starts and the
   app chimes. The
   zoom then settles with you filling about two-thirds of the frame.
2. **Sign checks.** Walk slowly to one side while it follows. If it turns
   *away* from you, flip `PAN_SIGN`; if it tilts away when you crouch or
   stand, flip `TILT_SIGN` (step 4b). Restart the service after each change.
3. **Sweep coverage.** Stand still out of view and press **Track & record**
   again from idle; watch one full sweep. The lens should pass over every
   part of the room you care about, without binding at either end of the pan.
   If the lens can't see your usual spot, adjust `SEARCH_TILT_ROWS_DEG`
   (tilt for each pass; the default rows are 5° and 22°) and, if something
   binds, `PAN_MIN_DEG` / `PAN_MAX_DEG`. A slower `SEARCH_PAN_DPS` helps if
   the camera keeps sweeping straight past you.
4. **Detector threshold.** If it stops the sweep for a coat stand, a chair or
   a bag, raise `DETECT_HIT_THRESHOLD` a little (0.3 by default; higher means
   fewer false people). If it sweeps past real people, lower it. Tune it in
   your own room and light, since that is where false positives come from.
5. **Re-sweep.** Walk out of view and wait. After about 6 s
   (`RESEARCH_AFTER_S`) the camera should start sweeping again and follow
   the first person it finds. If nobody is ever found it gives up to idle after
   `SEARCH_GIVE_UP_S` (180 s) when not recording.
6. **Battery gauge.** Counts energy used since the service started, assuming
   a full bank at that point. Start on a fully charged bank; compare
   minutes-left with a stopwatch over the first 30 min. No app reset control.

If it keeps sweeping and the app says it can't find anyone, the camera is
pointing somewhere you aren't, or the detector can't see you: recheck step 4,
face the camera, and make sure the room is lit.

## Values you end up setting

All in `src/without_uwb/device/sportcam/config.py`:

| Setting | From |
| --- | --- |
| `PAN_SIGN`, `TILT_SIGN`, soft limits (`PAN_MIN/MAX_DEG`, `TILT_MIN/MAX_DEG`) | step 4b, `ptzcheck`, then step 8 |
| `ZOOM_CURVE` | step 5a, by hand |
| `FOCUS_GRID` | step 5b, `focuscal` |
| `SEARCH_PAN_DPS`, `SEARCH_TILT_ROWS_DEG` | step 8.3: how fast and where the sweep looks |
| `DETECT_HIT_THRESHOLD` | step 8.4: raise for fewer false people |
| `TRACK_PAN_GAIN`, `TRACK_TILT_GAIN` | step 8.2: raise if the camera lags a fast mover, lower if it oscillates |
| `RESEARCH_AFTER_S`, `SEARCH_GIVE_UP_S` | step 8.5: how long before re-sweeping, and before giving up on an empty room |
| `FOUND_CONFIRM_S`, `FOUND_LOST_S` and `ACQUIRE_STALLED_S` | defaults are fine; see [05](../design/05-tracking-system.md) to tune |
| `FIREBASE_PROJECT`, `CAMERA_KEY`, `UPLOAD_API_BASE` | step 3, only with Firebase |
