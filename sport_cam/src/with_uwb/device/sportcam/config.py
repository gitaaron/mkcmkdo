"""Camera-unit configuration.

This is the **PTZ-base build on a Raspberry Pi 4**: an Arducam IMX477 PTZ
camera on a metal pan-tilt base, all four axes behind one I2C controller.
There is no pan stepper, no slip ring and no base ESP32, so everything below
runs on the single Pi.

The Pi 4 is here for its **hardware H.264 encoder**, which the Pi 5 dropped.
Recording costs almost nothing on this board, and that is most of the battery
budget. The trade is CPU: person detection runs at a few frames per second
rather than ten, which is fine because with three anchors vision only trims
what ranging has already pointed at, and a climber moves slowly. See docs/03
and docs/04.
"""

# Which build this is. Written to the camera's Firestore document and sent
# to phones in every state snapshot, so the apps word things for this hardware.
TRACKING_MODE = "with_uwb"

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
VIEWER_WINDOW_S = 60.0       # how long an app's "watch" keeps previews coming
DELETE_AFTER_UPLOAD = True   # SD card is a buffer, not a store

# --- direct phone ↔ camera connection ------------------------------------
LOCAL_API_PORT = 8787        # same protocol as the Firebase API
CAMERA_NAME = "SportCam"     # shown in the app's camera picker
MDNS_HOSTNAME = "sportcam.local"
WHEP_URL = None              # set when MediaMTX runs on the Pi (WebRTC)

# --- Wi-Fi setup: connecting → pairing (wifi_portal.py, wifi_link.py) -------
# The portal service decides when to pair; these are the head unit's side.
WIFI_STATUS_WAIT_S = 15.0    # no word from the portal by then (not installed): go idle
QR_SCAN_PERIOD_S = 0.5       # look for a Wi-Fi QR code this often while pairing
QR_RETRY_S = 20.0            # don't resend the same code sooner (it failed, or is joining)
QR_FOCUS_M = 0.5             # a phone held 15–30 cm from the lens; set_focus's floor

# --- pan / tilt (Arducam PTZ controller, I2C 0x0C) ------------------------
# Angles are degrees from centre. Raw servo values are 0-180; CENTER_RAW is
# the raw value that aims the lens along the anchor bar's normal, and SIGN
# flips if your base is assembled mirrored. Verify both on the bench with
# `python -m sportcam.ptzcheck` before the first tracking run.
I2C_BUS = 1
PAN_CENTER_RAW, PAN_SIGN = 90, 1
TILT_CENTER_RAW, TILT_SIGN = 90, 1

# Soft limits. The servos sweep 180°, but the metal base fouls before that
# with a camera on it — these are deliberately conservative. Sweep by hand,
# find where the lens or the ribbon binds, and widen to taste.
PAN_MIN_DEG, PAN_MAX_DEG = -80.0, 80.0
TILT_MIN_DEG, TILT_MAX_DEG = -45.0, 85.0

PAN_MAX_DPS = 120.0            # slew limit on the pan servo (deg/s)
TILT_MAX_DPS = 90.0

# --- tracking -------------------------------------------------------------
UWB_BASELINE_M = 0.4          # anchor separation (cad/config.scad uwb_half_base × 2)
# Raw range noise of the DW1000s after antenna-delay calibration. Angle noise
# is √2·σ/baseline, so this and the two baselines set how hard uwb.py's
# filters smooth: 10 cm over 0.25 m is ≈ 32° raw per frame.
UWB_RANGE_SIGMA_M = 0.10

# The third anchor, A3, stands on a mast behind the enclosure and supplies
# elevation, which a horizontal baseline cannot. Its position is measured from
# the midpoint between A1 and A2: `back` is how far it sits behind the bar
# (away from the lens), `up` how far above it. The mast puts it slightly
# behind rather than exactly over the bar so the camera can tilt without
# hitting it; the solver in uwb.py accounts for the offset. Both figures come
# from the CAD (`mast_axis_r`, `uwb_v_base`); cad/fit.py keeps them, the
# baseline and LED_COUNT in step with it.
# Set UWB_ANCHORS = 2 to run without A3: tilt then falls back to vision alone.
UWB_ANCHORS = 3
UWB_A3_BACK_M = 0.089
UWB_A3_UP_M = 0.250

# Elevation is measured at the anchor plane, but the lens sits higher, on the
# tilt axis. At 5 m the 10 cm difference is over a degree, so it is corrected.
# TILT_Z − the A1/A2 board height in docs/setup/assembly (120 − 22 mm).
LENS_ABOVE_ANCHORS_M = 0.098
# Where to aim relative to the tag. The recommended climbing spots (harness
# belt, low back) sit near the body's centre, so the default is zero; raise
# it if you wear the tag low and the shots look bottom-heavy.
TAG_AIM_OFFSET_M = 0.0

# Which radio stack is fitted.
#   "ula1"        Haorutech ULA1 (ESP32 + DWM1000). The tag polls the anchors
#                 and broadcasts one frame holding every range; ONE anchor
#                 plugged into the Pi forwards it. Every range therefore shares
#                 a timestamp, which is what the angle formulas assume.
#   "dual-serial" one port per anchor, each running our own DS-TWR sketch.
#                 Vendor-agnostic, but the ranges are independent samples.
UWB_PROTOCOL = "ula1"
UWB_PORT = "/dev/ttyUSB0"      # ula1: the one anchor that reports
UWB_PORTS = ("/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2")   # dual-serial: one per anchor, A1 A2 A3
UWB_BAUD = 115200
UWB_RATE_HZ = 20               # control-loop rate; verify the radio keeps up
RANGE_BIAS_M = (0.0, 0.0, 0.0) # per-anchor, A1 A2 A3: measure with `python -m sportcam.rangecal 5`
UWB_THETA_SIGN = 1             # flip to -1 if the two anchors are swapped

# The anchors are static, so UWB bearing is measured from the **bar normal**,
# not the lens. The pan loop commands that bearing as an absolute position and
# the CV trim below removes any residual bias.
PAN_PID = dict(Kp=0.55, Ki=0.0, Kd=0.06)   # smooths the commanded position
# Both CV gains are applied once per *fresh* detection, not once per control
# tick. At DETECT_FPS_TRACKING = 3 a 100 px error moves the bias about
# 1.2 deg/s and tilt about 1.8 deg/s, against a subject that climbs at
# roughly 1.7 deg/s seen from 10 m. Raise them if tracking lags; lower them
# if the tilt axis hunts, which is what too much gain plus detector latency
# looks like.
PAN_CV_BIAS_GAIN = 0.004       # deg of pan bias per pixel, per detection
PAN_CV_BIAS_LIMIT = 12.0       # how far CV may disagree with UWB before we trust UWB
# With A3 fitted, tilt works like pan: ranging sets the angle and vision
# trims a bias. The bias gain is the fraction of the measured angular error
# absorbed per detection — angular, not per pixel, so it means the same thing
# at either end of the zoom.
TILT_CV_BIAS_GAIN = 0.25
TILT_CV_BIAS_LIMIT = 10.0      # deg; elevation noise is worst on steep shots
# Without A3 (or while its range drops out) tilt is vision-only, as before.
TILT_PID = dict(Kp=0.04, Ki=0.0, Kd=0.008)   # deg per pixel-error
TILT_STEP_GAIN = 0.15          # fraction of the PID output applied per detection

LOST_HOLD_S = 2.0              # no ranges → hold + flash
LOST_IDLE_S = 5.0              # no ranges → drop to idle (saving any recording)

# --- tag-driven sessions (session.py) --------------------------------------
# Turning the tag on is the start button: standby → search → found → recording,
# and turning it off ends the session LOST_IDLE_S later. A switched-off tag
# looks exactly like one hidden behind a body, so a dropout longer than that
# also ends the session — and the tag reappearing then starts a new one, so
# the climb is split into two clips rather than lost. Raise LOST_IDLE_S if
# that happens often.
AUTO_SESSION = True            # False: the tag only ranges; start from the app
TAG_PRESENT_S = 1.0            # unbroken ranging this long = the tag is on
# SEARCH → FOUND → recording, as in the camera-only build, but SEARCH is a
# turn to the tag's bearing rather than a sweep, and every session starts
# there (there is no idle bypass: idle cannot tell who is wearing the tag).
# FOUND starts once the camera is pointing where the tag says, has settled
# there, and the detector sees the tag wearer (below). FOUND tracks exactly
# as recording does; the person need not be centred. Seen throughout
# FOUND_CONFIRM_S, it records. Vision must verify: recording never starts on
# ranging alone, so a wrong sign or a bad calibration shows up as a ring that
# keeps chasing, not as a clip of a wall. The start of a climb — standing
# upright at the foot of the wall — is the pose HOG handles best; it only
# struggles later, and nothing mid-climb depends on it.
ACQUIRE_POINT_TOL_DEG = 4.0    # pan (and tilt, with A3) within this of the target
ACQUIRE_SETTLE_S = 0.5         # ...for this long
FOUND_CONFIRM_S = 3.0          # FOUND this long, the person still in frame → record
FOUND_LOST_S = 1.0             # FOUND without the tag wearer seen this long → back to SEARCH
ACQUIRE_STALLED_S = 15.0       # acquiring this long → the app says "can't see you"

# The tag wearer, not just a person. HOG finds people, not *your* person, so
# each box is checked against the tag before it counts (Tracker._match_tag):
#   gate    — its bearing within TAG_MATCH_BEARING_DEG of the tag's (plus the
#             learned vision bias), and the distance its height implies
#             within a factor TAG_MATCH_RANGE_RATIO of the ranged distance.
#             Someone off to one side, or walking past close to the lens,
#             never counts.
#   follow  — everyone admitted through the gate is followed from one
#             detection to the next by where they are (moving less than
#             TAG_FOLLOW_DEG), so a second person cannot take over between
#             detections. The gate only admits: once in, a person is averaged
#             on every detection and kept for TAG_FORGET_S out of view, so
#             bearing noise cannot drop a rival from the comparison.
#   average — one bearing is too noisy (≈ 7° RMS) to split two people standing
#             close, but its average over a few seconds is not. Each person
#             keeps a running mean of box bearing − tag bearing. SEARCH picks
#             whoever is nearest on average. FOUND records only once everyone
#             else is further from the tag by a lead of TAG_MATCH_Z standard
#             errors of those averages (never less than TAG_MATCH_MARGIN_DEG);
#             the countdown holds at 1 until then. If someone else gets that
#             lead instead, FOUND switches to them and starts again. Alone in
#             the gate — most sessions — the wearer records after the usual
#             3 s. Measured in simulation (bearing noise as below, 48 runs):
#             a belayer 2.5 m from the climber at 10 m is resolved in ≈ 4–10 s,
#             1.5 m in ≈ 8 s and 1 m in ≈ 12 s on average, and never the wrong
#             way; within ≈ 0.5 m they are never told apart, and the app asks
#             the climber to step away once ACQUIRE_STALLED_S passes.
#             TAG_BEARING_SIGMA_DEG and TAG_BEARING_CORR_S are estimates until
#             `python -m sportcam.bearingcal` measures them on your hardware.
# Bystanders never move the vision tilt or the zoom: only the chosen person
# does. The pan bias also stands still while more than one person is in the
# gate, until recording, so it cannot lean the choice toward the first pick.
TAG_MATCH_BEARING_DEG = 14.0   # ≈ 2 σ of the filtered bearing
TAG_MATCH_RANGE_RATIO = 2.0    # vision distance within ×/÷ this of the UWB distance
TAG_FOLLOW_DEG = 6.0           # a person moves less than this between detections
TAG_FORGET_S = 5.0             # someone admitted is forgotten after this long out of view
TAG_MATCH_MARGIN_DEG = 4.0     # the chosen person's mean miss beats everyone else's by
                               # at least this...
TAG_MATCH_Z = 3.0              # ...and by this many standard errors of the averages
TAG_BEARING_SIGMA_DEG = 7.0    # filtered bearing noise, RMS, 400 mm baseline (05)
TAG_BEARING_CORR_S = 0.35      # its correlation time: the Kalman filter's ≈ 7-frame memory

# --- vision ---------------------------------------------------------------
# With three anchors the detector is a trim, not a source: ranging gives both
# angles, and vision cancels their residual bias and guards the zoom. On a
# two-anchor build it is the ONLY source of tilt, because a horizontal
# baseline carries no elevation information. All of it tolerates a low rate.
#
# Rates are deliberately modest: HOG on a Pi 4 takes a few hundred ms, and
# tilt only needs to keep up with ~1.7 deg/s of subject motion.
DETECT_FPS_TRACKING = 3.0
DETECT_FPS_IDLE = 0.5
IDLE_PERSON_HOLD_S = 4.0       # idle: a person stays "in frame" this long after the
                               # last detection (two idle detections), so one
                               # missed frame does not flip the idle sub-state

# Ultra-wideband already knows where the subject is horizontally, so the
# detector only has to answer "how high". Searching a vertical strip centred
# on the known bearing instead of the whole frame cuts the work several times
# over. Width is a fraction of frame width; 0 disables the crop.
DETECT_STRIP_FRACTION = 0.42
DETECT_DOWNSCALE_W = 480       # detector input width; smaller is faster

# Horizontal field of view at the two ends of the zoom range, used to turn a
# bearing into a pixel column. From the lens's published 96-33 deg spec.
HFOV_WIDE_DEG, HFOV_TELE_DEG = 96.0, 33.0

# --- framing --------------------------------------------------------------
TARGET_FRAME_FRACTION = 0.45   # distance-only framing (vision refines it, below)
SUBJECT_HEIGHT_M = 1.8
SENSOR_H_MM = 3.537            # IMX477 active height in 16:9 video modes
ZOOM_DEADBAND_M = 0.3

# Vision framing. Distance gives a first zoom (TARGET_FRAME_FRACTION of an
# assumed SUBJECT_HEIGHT_M — deliberately loose, since it is a guess about
# the body). Then each detection measures how much of the frame the person
# actually fills and nudges the zoom toward ZOOM_FILL_TARGET, leaving
# (1 − target)/2 of the frame as margin on each side for error and sudden
# moves. "Fill" is the larger of the person's height and width fractions, so
# a climber stretched sideways on an overhang is framed by their span.
# HOG boxes are padded: the body is about PERSON_IN_BOX_H of the box height
# and PERSON_IN_BOX_W of its width, and fill is measured on the body.
ZOOM_FILL_TARGET = 0.65        # person fills 65 %: ≈ 17 % margin each side
ZOOM_VISION_GAIN = 0.35        # share of the log-error corrected per detection
ZOOM_SCALE_MIN, ZOOM_SCALE_MAX = 0.5, 2.5   # vision may move zoom this far off distance
PERSON_IN_BOX_H = 0.75
PERSON_IN_BOX_W = 0.55
# With no detection for this long (an overhang, a back-on reach), vision has
# nothing to say, so the zoom eases back to the looser distance framing at
# ZOOM_STALE_RELAX of the way per second — wider is the safe direction.
ZOOM_STALE_S = 2.0
ZOOM_STALE_RELAX = 0.3
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
BATTERY_CRITICAL_FRAC = 0.07   # stop recording, park, drop to idle
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
