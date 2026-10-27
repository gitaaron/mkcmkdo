"""Camera-unit configuration — the **camera-only build**.

An Arducam IMX477 PTZ camera on a metal pan-tilt base: zoom and focus on
its I2C controller, pan and tilt driven by the Pi's hardware PWM (or the
controller, `SERVO_DRIVER`), all from a single Raspberry Pi 4. There is no UWB
radio, no anchor, no wearable tag: pressing *track / record* in the app makes
the camera sweep the room until its person detector sees someone, then it
follows the first person it found.

The Pi 4 is here for its **hardware H.264 encoder**, which the Pi 5 dropped.
Recording costs almost nothing on this board, and that is most of the battery
budget. The trade is CPU: person detection runs at a few frames per second
rather than ten. Vision is now the only sense the tracker has, so the loops
below are tuned for a 3 fps detector. See docs/03 and docs/04.
"""

# Which build this is. Written to the camera's Firestore document and sent
# to phones in every state snapshot, so the apps word things for this hardware.
TRACKING_MODE = "without_uwb"

# --- Firebase (the app from anywhere, and the recording library) ----------
# Set by scripts/firebase-setup.sh. With CAMERA_KEY empty the camera runs
# stand-alone: direct phone connection only, recordings kept on the card.
FIREBASE_PROJECT = ""        # e.g. "sportcam-aaron"
# The camera key: a long random string, shared with the apps. It names this
# camera's Firestore document and goes with every API call.
CAMERA_KEY = ""
# Service-account key for Firestore access (a service account limited to
# the "Cloud Datastore User" role). Not needed against the emulator.
FIREBASE_CREDENTIALS = "/home/pi/sportcam-firebase.json"
# The API: "https://<FIREBASE_PROJECT>.web.app". For local testing against the
# emulators: "http://<your-computer>:5001/demo-sportcam/us-central1/api"
# (and export FIRESTORE_EMULATOR_HOST=<your-computer>:8080).
UPLOAD_API_BASE = ""
HEARTBEAT_S = 5.0            # heartbeat + telemetry to Firestore; apps call it offline after 20 s
PREVIEW_FPS = 1.0            # live preview frames to Firestore, only while an app is watching
PREVIEW_MAX_BYTES = 200_000
# Person boxes in the live view (docs/01 F9): the last detection's boxes go
# out with each preview frame and, on the direct link, as each detection
# lands. Older than this (awake detects every 2 s) and they're dropped.
LIVE_BOXES_MAX_AGE_S = 3.0
VIEWER_WINDOW_S = 60.0       # how long an app's "watch" keeps previews coming
DELETE_AFTER_UPLOAD = True   # SD card is a buffer, not a store

# --- direct phone ↔ camera connection ------------------------------------
LOCAL_API_PORT = 8787        # same protocol as the Firebase API
CAMERA_NAME = "SportCam"     # shown in the app's camera picker
MDNS_HOSTNAME = "sportcam.local"
WHEP_URL = None              # set when MediaMTX runs on the Pi (WebRTC)

# --- Wi-Fi setup: connecting → pairing (wifi_portal.py, wifi_link.py) -------
# The portal service decides when to pair; these are the head unit's side.
WIFI_STATUS_WAIT_S = 15.0    # no word from the portal by then (not installed): go awake
QR_SCAN_PERIOD_S = 0.5       # look for a Wi-Fi QR code this often while pairing
QR_RETRY_S = 20.0            # don't resend the same code sooner (it failed, or is joining)
QR_FOCUS_M = 0.5             # a phone held 15–30 cm from the lens; set_focus's floor

# --- sleep and awake --------------------------------------------------------
# Sleep saves the battery: the camera sensor is stopped (no preview, detector
# or live view) and the head parked, while the Pi keeps its API, Firebase link
# and mDNS up to be woken. Power on joins Wi-Fi and comes up awake; awake this
# long with no session started, it goes back to sleep. An app showing the live
# view (the stream here, or a Firebase "watch") keeps it awake; the timeout
# counts from when it stops watching.
AWAKE_TIMEOUT_S = 30.0
CAMERA_WARMUP_S = 1.0        # after waking, let exposure settle before the first detection
SLEEP_LED_LEVEL = 0.25       # sleep: a single ring pixel at this level, to show it is on

# --- pan / tilt -------------------------------------------------------------
# Who drives the two servos (docs/04, "Servo drive"):
#   "pigpio"  — the Pi, via the pigpio daemon's hardware PWM on PAN_GPIO /
#               TILT_GPIO, through the 74AHCT125. Sub-degree steps, so slow
#               pans stay smooth zoomed in. Needs the servo signal leads
#               moved off the PTZ controller (docs 12, "Servos") and pigpiod
#               running (docs 14).
#   "arducam" — the PTZ controller's registers 0x05 / 0x06, whole degrees
#               only. For a head still wired as the kit came.
SERVO_DRIVER = "pigpio"
PAN_GPIO, TILT_GPIO = 12, 13   # the Pi 4's two hardware PWM channels (pins 32, 33)
SERVO_PWM_HZ = 50
# Pulse width at raw 0° and 180°: the standard servo range, and what the
# controller's registers map to. If a commanded ±45° measures short or long
# on the bench, widen or narrow these about 1500 µs.
SERVO_US_AT_0, SERVO_US_AT_180 = 500, 2500

# Angles are degrees from centre. Raw servo values are 0-180; CENTER_RAW is
# the raw value that aims the lens straight ahead of the enclosure, and SIGN
# flips if your base is assembled mirrored. CENTER_RAW may be fractional with
# the pigpio driver. Verify both on the bench with
# `python -m sportcam.ptzcheck` before the first tracking run.
I2C_BUS = 1                     # PTZ controller (zoom, focus; and pan/tilt on "arducam")
PAN_CENTER_RAW, PAN_SIGN = 90, 1
TILT_CENTER_RAW, TILT_SIGN = 90, 1

# Soft limits. The servos sweep 180°, but the metal base fouls before that
# with a camera on it — these are deliberately conservative. Sweep by hand,
# find where the lens or the ribbon binds, and widen to taste.
PAN_MIN_DEG, PAN_MAX_DEG = -80.0, 80.0
TILT_MIN_DEG, TILT_MAX_DEG = -45.0, 85.0

PAN_MAX_DPS = 120.0            # slew limit on the pan servo (deg/s)
TILT_MAX_DPS = 90.0
# Easing. Racing to each new aim point at the slew limit and stopping dead
# shows in the video as a lurch every detection. Instead the servos move at
# a speed proportional to the distance left, covering it in about
# TRACK_EASE_S, and change speed no faster than the acceleration limits, so
# every move starts and ends gently and a new aim point bends the motion
# rather than jerking it. Longer is smoother but lags a fast mover more.
TRACK_EASE_S = 0.4
PAN_MAX_ACCEL_DPS2 = 60.0
TILT_MAX_ACCEL_DPS2 = 45.0

# --- manual aim: the phone app's joystick (awake only) ---------------------
# The knob's pull, as a fraction of the ring's radius, sets the speed: it
# grows with the square of the pull, so a small pull aims finely and a full
# pull turns at these rates.
JOG_PAN_MAX_DPS = 60.0
JOG_TILT_MAX_DPS = 45.0
JOG_TIMEOUT_S = 0.3            # no joystick message this long: stop. A dropped
                               # connection can't leave the head turning

CONTROL_RATE_HZ = 20            # tracker / state-machine tick

# --- search: sweeping the room for the first person ------------------------
# Pressing track / record puts the camera in SEARCH. It zooms wide and sweeps
# pan end to end at SEARCH_PAN_DPS; each time it reaches a limit it reverses
# and steps to the next tilt row, so the room is scanned in a zig-zag. The
# first person the detector sees stops the sweep. Slow enough that a 3 fps
# detector sees a person in more than one frame, and that a person does not
# smear across the frame: at the wide end (96 deg) 25 deg/s is a quarter of
# the frame per second.
SEARCH_PAN_DPS = 25.0
SEARCH_TILT_ROWS_DEG = (5.0, 22.0)   # tilt for each pass; lens is ~1.5 m up
SEARCH_TILT_DPS = 40.0
SEARCH_FOCUS_M = 5.0           # a room-sized hyperfocal guess while sweeping
SEARCH_GIVE_UP_S = 180.0       # tracking (not recording) and sweeping this long
                               # without finding anyone → back to awake. A
                               # recording is never abandoned: the user stops that.
LOST_ZOOM_OUT_S = 2.0          # the person being recorded missing this long → zoom
                               # straight out to wide, still pointing where they were
RESEARCH_AFTER_S = 6.0         # missing this long → sweep again (still wide)
LOST_HOLD_S = 2.0              # target missing → hold still and flash the ring

# --- following the person ---------------------------------------------------
# Vision measures the person's offset from the middle of the frame; that
# offset is turned into degrees (from the current field of view) and the pan
# and tilt goals move that far along, scaled by the gains below. The goals are
# then slew-limited so the servos glide. A gain under 1 deliberately
# under-corrects: the detector is slow and the measurement is already a few
# hundred milliseconds old when it arrives, so correcting fully each time
# overshoots and hunts. Raise it if tracking lags a fast mover; lower it if
# the camera oscillates.
TRACK_PAN_GAIN = 0.6
TRACK_TILT_GAIN = 0.5
TRACK_DEADBAND_FRACTION = 0.04  # offsets under this share of the frame are ignored
# The tracker follows the detection nearest the one it had, not the biggest,
# so a bystander walking past does not steal the lock. A detection further
# than this fraction of the frame width from the last one is not "the same
# person" and is ignored.
TRACK_GATE_FRACTION = 0.45

# --- finding a person ------------------------------------------------------
# SEARCH → FOUND → recording. The first detection stops the sweep and the
# camera follows and frames the person exactly as it will while recording
# (FOUND); they need not be centred. Still in frame FOUND_CONFIRM_S later, it
# records. One-frame false positives (a coat stand, a chair) therefore cost a
# short pause, not a recording of furniture.
FOUND_CONFIRM_S = 3.0          # FOUND this long, the person still in frame → record
FOUND_LOST_S = 1.0             # FOUND with nobody seen this long → resume the sweep
ACQUIRE_STALLED_S = 15.0       # searching this long → the app says "can't see anyone"

# --- vision ---------------------------------------------------------------
# Vision is the only sensor, so the detector runs at the full rate whenever a
# session is active. HOG on a Pi 4 takes a few hundred ms, which is why the
# loops above are written for ~3 detections a second. A person is a slow
# mover seen from a few metres; if yours is not, a MobileNet-SSD detector
# (cv2.dnn) is the upgrade path — `Camera._detect` is the only place to change.
DETECT_FPS_TRACKING = 3.0
DETECT_FPS_AWAKE = 0.5
AWAKE_PERSON_HOLD_S = 4.0       # awake: a person stays "in frame" this long after the
                               # last detection (two awake detections), so one
                               # missed frame does not flip the awake sub-state
DETECT_HIT_THRESHOLD = 0.3     # HOG SVM margin: higher = fewer false people.
                               # Tune on your own room; coat stands and chairs
                               # are the usual false positives.

# While locked on, search only a vertical strip of the frame around the
# person instead of all of it, which cuts detector time several-fold. Width is
# a fraction of the frame width; 0 disables the crop. Searching (no lock)
# always uses the whole frame.
DETECT_STRIP_FRACTION = 0.6
DETECT_DOWNSCALE_W = 480       # detector input width; smaller is faster

# Horizontal field of view at the two ends of the zoom range, used to turn a
# bearing into a pixel column. From the lens's published 96-33 deg spec.
HFOV_WIDE_DEG, HFOV_TELE_DEG = 96.0, 33.0

# --- framing --------------------------------------------------------------
# With no ranging, the person's own size in the frame is the only distance cue.
# SUBJECT_HEIGHT_M turns it into an *estimated* distance, used for focus
# only: it is deliberately a guess about the body, and focus has depth of field
# to spare at the wide end.
SUBJECT_HEIGHT_M = 1.7
SENSOR_H_MM = 3.537            # IMX477 active height in 16:9 video modes
ZOOM_DEADBAND_M = 0.3
DIST_SMOOTHING = 0.3           # share of each new distance estimate that is taken
DIST_MIN_M, DIST_MAX_M = 1.0, 30.0

# Vision framing. The camera starts wide. Each detection measures how much of
# the frame the person actually fills and nudges the zoom toward
# ZOOM_FILL_TARGET, leaving
# (1 − target)/2 of the frame as margin on each side for error and sudden
# moves. "Fill" is the larger of the person's height and width fractions, so
# a person stretched sideways is framed by their span.
# HOG boxes are padded: the body is about PERSON_IN_BOX_H of the box height
# and PERSON_IN_BOX_W of its width, and fill is measured on the body.
ZOOM_FILL_TARGET = 0.65        # person fills 65 %: ≈ 17 % margin each side
ZOOM_VISION_GAIN = 0.35        # share of the log-error corrected per detection
PERSON_IN_BOX_H = 0.75
PERSON_IN_BOX_W = 0.55
# Guard: a fast zoom-out when the body nears the edge of the frame or
# outgrows ZOOM_GUARD_FILL. HOG cannot see a body that is already clipped,
# so this has to act on the approach, and it wins over the fill loop.
ZOOM_GUARD_FILL = 0.85
ZOOM_GUARD_EDGE = 0.03         # box within this fraction of any frame edge
ZOOM_GUARD_STEP = 0.8          # multiply the zoom by this per trigger

# Arducam PTZ zoom lens. The published field of view is 96°→33° horizontal,
# which on the IMX477's 16:9 frame is about 2.8-10.6 mm of focal length.
# Verify during the zoom calibration in docs/04 and correct the curves below.
ZOOM_MIN_MM, ZOOM_MAX_MM = 2.8, 10.6
ZOOM_MIN_STEP_MM = 0.15        # ignore smaller changes — stops the lens breathing
ZOOM_RATE_LIMIT_S = 2.0

# (focal length mm, raw motor value). Straight lines between the stops until
# you measure yours; the raw ranges are the controller's own limits.
ZOOM_CURVE = [(2.8, 3000), (10.6, 20000)]

# Focus depends on subject distance as well as focal length. Depth of field
# is deep at the wide end and shallow at the tele end (roughly 6-20 m when
# focused at 10 m at 10.6 mm), so one curve per focal length is not enough.
#
#   FOCUS_GRID[efl_mm] = [(distance_m, raw), ...]
#
# Lookup interpolates between rows on focal length and within a row on
# 1/distance, because lens extension goes as 1/d. Measure it with
# `python -m sportcam.focuscal`, which sweeps the motor and keeps the
# sharpest position. UNTIL YOU DO, every row is flat, which reproduces the
# old focal-length-only behaviour exactly — nothing gets worse, and nothing
# gets better either.
FOCUS_GRID = {
    2.8:  [(2.0, 2000), (5.0, 2000), (10.0, 2000), (30.0, 2000)],
    10.6: [(2.0, 16000), (5.0, 16000), (10.0, 16000), (30.0, 16000)],
}
FOCUS_DEADBAND_DIOPTRE = 0.02  # ignore changes smaller than this in 1/d
FOCUS_RATE_LIMIT_S = 0.5

# --- battery -------------------------------------------------------------
# SportCam runs off a USB-C PD power bank: a PD trigger board pulls 12 V from
# it, one buck makes the 5 V rail, and an INA226 between them measures what
# the pack actually delivers. A bank reports no state of charge over PD, so
# the gauge integrates watt-hours and assumes a full pack at the last reset.
# Energy available **at the 12 V rail, where the gauge sits** — not the number
# on the bank. A 25 000 mAh bank is 92 Wh at its cells, and its own boost to
# 12 V costs about 9 % before our buck ever sees it. Using the nameplate here
# makes every estimate roughly 10 % optimistic. For a 74 Wh bank, use 67.
BATTERY_WH = 84.0
BATTERY_LOW_FRAC = 0.20        # warn: LED ring flashes orange
BATTERY_CRITICAL_FRAC = 0.07   # stop recording, park, go to sleep
# Which current sensor is fitted. "ina260" has the shunt on the die and is
# the easier part to buy and wire; "ina226" needs an external shunt; "none"
# builds without a gauge, losing the low-battery warning and the auto-save.
POWER_MONITOR = "ina260"
POWER_MONITOR_ADDR = 0x40      # both parts default to this
INA226_SHUNT_OHMS = 0.01       # only used when POWER_MONITOR = "ina226"

# Power saving. The detector throttles when nobody is being tracked and the
# ring dims on low battery; both happen automatically.
LED_BRIGHTNESS_LOW_BATT = 0.18

# --- status LED ring (WS2812B, driven by the Pi over SPI MOSI) ------------
# Data goes out of SPI0 MOSI (GPIO10) through a 74AHCT125 level shifter.
# The Pi 4 could also use the classic PWM+DMA driver on GPIO18, but that one
# needs the whole service to run as root; SPI does not. Enable SPI in
# raspi-config.
LED_COUNT = 16
LED_BRIGHTNESS = 0.45

# --- video ----------------------------------------------------------------
PREVIEW_SIZE = (1280, 720)
RECORD_SIZE = (1920, 1080)
RECORD_BITRATE = 12_000_000    # 1080p H.264, ≈ 5.4 GB/h. The storage maths in
                               # storage.py reads this, so the two cannot drift.
MJPEG_FPS = 15
RECORD_DIR = "/home/pi/recordings"

# --- SD card --------------------------------------------------------------
# The card is a buffer: clips are deleted once the backend confirms them. When
# uploads fail they pile up, so storage gets the same warn/stop treatment as
# the battery. Thresholds are in minutes of recording still available.
STORAGE_RESERVE_MB = 500       # never spend this on video; the OS needs room
STORAGE_LOW_MIN = 20.0         # warn: ring blinks, app shows it
STORAGE_CRITICAL_MIN = 5.0     # refuse to start, and stop a running recording

# Failed uploads are retried on start-up and then on this interval, so a
# session filmed with no backend reachable drains as soon as one appears.
UPLOAD_RETRY_INTERVAL_S = 900.0
