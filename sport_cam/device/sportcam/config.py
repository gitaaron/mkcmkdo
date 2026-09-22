"""Head-unit configuration."""

SERVER_WS = "ws://homeserver.local:8787/ws/device"

# Recording upload backend — same callable protocol either way:
#   home LAN : "http://homeserver.local:8787"
#   Firebase : "https://<your-project>.web.app"   (gym / away workflow)
UPLOAD_API_BASE = "http://homeserver.local:8787"
DELETE_AFTER_UPLOAD = True   # SD card is a buffer, not a store

# --- tracking -------------------------------------------------------------
UWB_BASELINE_M = 0.40          # anchor separation
UWB_PORTS = ("/dev/ttyUSB0", "/dev/ttyUSB1")
UWB_RATE_HZ = 20
RANGE_BIAS_M = (0.0, 0.0)      # per-anchor calibration (docs/04, "Calibration")

PAN_MAX_DPS = 180.0            # slew limit sent to base
PAN_PID = dict(Kp=2.2, Ki=0.1, Kd=0.15)
TILT_PID = dict(Kp=0.04, Ki=0.0, Kd=0.008)   # deg per pixel-error

LOST_HOLD_S = 5.0              # no ranges → hold + flash
LOST_IDLE_S = 30.0             # no ranges → drop to idle

# --- framing --------------------------------------------------------------
TARGET_FRAME_FRACTION = 0.40   # subject height as fraction of frame
ZOOM_DEADBAND_M = 0.3
ZOOM_MIN_MM, ZOOM_MAX_MM = 8.0, 20.0

# --- tilt servo -----------------------------------------------------------
TILT_GPIO = 18
TILT_MIN_DEG, TILT_MAX_DEG = -45.0, 225.0
TILT_US_AT_MIN, TILT_US_AT_MAX = 500, 2500   # DS3225 270° pulse endpoints

# --- video ----------------------------------------------------------------
PREVIEW_SIZE = (1280, 720)
RECORD_SIZE = (1920, 1080)
MJPEG_FPS = 15
RECORD_DIR = "/home/pi/recordings"
