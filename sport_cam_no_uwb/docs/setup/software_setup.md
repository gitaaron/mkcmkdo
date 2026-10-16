# Software setup

From a blank SD card to a camera that tracks, in order. Do the
[assembly guide](assembly/index.html) and its [wiring guide](wiring.md) first; this picks up where its last
step ("Power-on checks") leaves off. Each step says what *done* looks like.
If one fails, the matching row in
[10 — Verification](../10-verification.md#on-the-bench-before-the-first-session) says why.

**You need:** the assembled camera on its tripod; a 16 GB+ microSD card; a
computer with [Raspberry Pi Imager](https://www.raspberrypi.com/software/); a
tape measure; and a phone or laptop on the same Wi-Fi. About **1 hour**, most
of it calibration. Nothing here is worn or measured out: the camera finds
people by sight alone.

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
cd ~/sportcam/device
sudo pip3 install --break-system-packages -r requirements.txt
```

The packages go in system-wide because both services run the system
`python3`, and the Wi-Fi portal runs as root. Picamera2 only comes from apt,
so a virtualenv would need `--system-site-packages` and edited unit files.

**Done when:** the offline tests pass:

```bash
for t in tests/test_*.py; do python3 $t | tail -1; done
```

## 3. Point it at your server (optional)

Edit `~/sportcam/device/sportcam/config.py`:

| Setting | Set it to |
| --- | --- |
| `SERVER_WS` | `ws://<your-computer>.local:8787/ws/device`, if you run the home server (step 7) |
| `UPLOAD_API_BASE` | the same host as `http://…:8787`, or `https://<project>.web.app` for the cloud backend ([08](../08-recordings-and-cloud.md)) |

Skip this step for **direct mode**: the phone app talks to the camera itself
and needs no server ([09](../09-direct-connection-and-app.md)).

## 4. Bench checks: camera and motion

Run everything from `~/sportcam/device`.

**a. Camera:** `rpicam-hello -t 2000` shows a picture. If it does not, see
step 1.

**b. Pan and tilt:**

```bash
python3 -m sportcam.ptzcheck
```

It sweeps each axis to its soft limits and back. In `config.py`:

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

Do these in order. Each prints a line to paste into `config.py`, or tells you
what to change there.

**a. Zoom curve.** This is manual; there is no tool for it yet. See
[04 — Calibration](../04-tracking-system.md#calibration). Until you do it,
`ZOOM_CURVE` is a straight-line guess, and framing is roughly right but not
exact.

**b. Focus grid.** Tape a high-contrast target (a printed chart or a
newspaper) at each distance in turn, in the light you will film in, and run:

```bash
python3 -m sportcam.focuscal 2
python3 -m sportcam.focuscal 5
python3 -m sportcam.focuscal 10
python3 -m sportcam.focuscal 30
```

After the last run, paste the `FOCUS_GRID = {…}` it prints. Until then,
focus depends on zoom alone and is soft away from one distance. The search
sweep focuses at `SEARCH_FOCUS_M` (5 m); once someone is locked, focus follows
the distance estimated from their size in the frame.

## 6. Install the services

```bash
sudo cp ~/sportcam/device/sportcam-head.service ~/sportcam/device/sportcam-wifi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sportcam-head sportcam-wifi
journalctl -u sportcam-head -f          # watch it start; Ctrl-C to stop
```

**Done when** the LED ring turns solid blue (idle). After any `config.py` edit,
run `sudo systemctl restart sportcam-head`. A restart also resets the battery
gauge to "full" (step 8.6), so don't restart mid-session on a part-used bank. **Stop the service**
(`sudo systemctl stop sportcam-head`) before running `focuscal` or `ptzcheck`
again, because they need the camera and motors to themselves.

## 7. The app

Pick one:

- **Direct, no server.** On the same Wi-Fi as the camera:
  `cd app_flutter && flutter pub get && flutter run`. It finds the camera by
  mDNS ([09](../09-direct-connection-and-app.md)). For the record start/stop
  chimes to play with the phone in your bag, apply the platform setup in
  [`app_flutter/README.md`](../../app_flutter/README.md) first, and allow
  notifications on Android when asked.
- **Home server + web app**, on your computer with Node 22:

  ```bash
  npm install
  SIM=0 npm run dev        # API on :8787, app on http://localhost:5173
  ```

  `SIM=0` turns off the built-in camera simulator, so the app shows the real
  camera.
- **Cloud**, for filming away from home: see
  [08 — Recordings, cloud & gym Wi-Fi](../08-recordings-and-cloud.md).

**At a new gym:** power on, join the camera's `SportCam-Setup` hotspot from
your phone, open `http://10.42.0.1` and pick the gym's network. The camera
remembers it.

## 8. Live checks

With the service running, the ring is solid blue. Do these in order: the
tuning steps only mean something once the signs are right.

1. **First run.** Stand 3–5 m from the camera, in the room you will film in,
   upright and facing it. In the app press **Track & record**. The status
   reads "Looking for a person…" and the ring shows a green light chasing
   round while the camera zooms wide and sweeps left and right, stepping to the
   next tilt row at each end. When it sees you it stops and turns to put you in
   the middle; after two centred detections it locks on, the ring turns
   breathing red, recording starts and the app chimes. The zoom then settles
   with you filling about two-thirds of the frame.
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
   (`RESEARCH_AFTER_S`) the camera should start sweeping again and re-lock on
   the first person it finds. If nobody is ever found it gives up to idle after
   `SEARCH_GIVE_UP_S` (180 s) when not recording.
6. **Battery gauge.** The gauge cannot read the bank's charge; it counts
   what has been used since the camera software started, and assumes the
   bank was full then. So start on a freshly charged bank, and check its
   minutes-left against a stopwatch over the first half hour. There is no
   app button to re-zero it yet.

If it keeps sweeping and the app says it can't find anyone, the camera is
pointing somewhere you aren't, or the detector can't see you: recheck step 4,
face the camera, and make sure the room is lit.

## Values you end up setting

All in `device/sportcam/config.py`:

| Setting | From |
| --- | --- |
| `PAN_SIGN`, `TILT_SIGN`, soft limits (`PAN_MIN/MAX_DEG`, `TILT_MIN/MAX_DEG`) | step 4b, `ptzcheck`, then step 8 |
| `ZOOM_CURVE` | step 5a, by hand |
| `FOCUS_GRID` | step 5b, `focuscal` |
| `SEARCH_PAN_DPS`, `SEARCH_TILT_ROWS_DEG` | step 8.3: how fast and where the sweep looks |
| `DETECT_HIT_THRESHOLD` | step 8.4: raise for fewer false people |
| `TRACK_PAN_GAIN`, `TRACK_TILT_GAIN` | step 8.2: raise if the camera lags a fast mover, lower if it oscillates |
| `AUTO_RECORD_ON_LOCK` | `True` records as soon as it locks on; `False` makes recording a separate tap |
| `RESEARCH_AFTER_S`, `SEARCH_GIVE_UP_S` | step 8.5: how long before re-sweeping, and before giving up on an empty room |
| `ACQUIRE_DETECTIONS` and the other `ACQUIRE_*` lock-on settings | defaults are fine; see [04](../04-tracking-system.md) to tune |
| `SERVER_WS`, `UPLOAD_API_BASE` | step 3, only with a server |
