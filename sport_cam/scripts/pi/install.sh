#!/usr/bin/env bash
# Installs everything the camera needs onto a freshly imaged Pi, from your
# computer (macOS or Linux), over SSH. Software setup step 2 of each build:
# docs/<build>/setup/14-software-setup.md (full build) or
# docs/<build>/bench/14-software-setup.md (bench test).
#
#   ./scripts/pi/install.sh with_uwb                 full build
#   ./scripts/pi/install.sh without_uwb --bench      bench test
#   ./scripts/pi/install.sh with_uwb --host 192.168.1.42
#
# Needs: the Pi imaged as in step 1 (user pi, SSH with your public key), on
# the same network as this computer, so that `ssh pi@sportcam.local` logs in
# without a password.
#
# On the Pi it:
#   - turns on I2C (and SPI for the LED ring, full build)
#   - upgrades the OS and installs the camera's apt packages
#   - full build: pigpio (pan/tilt PWM), analog audio off, the MobileNet-SSD
#     weights (getmodel)
#   - copies src/<build>/device from this checkout, installs its Python
#     requirements and runs its offline tests
#   - puts it in ~/sportcam/src/<build>/device, keeping a config.py already
#     there (your calibration) unless --reset-config
#   - bench: sets SERVO_DRIVER, POWER_MONITOR (and UWB_ANCHORS) for the bench
#   - reboots, and checks the camera, the I2C devices (and pigpiod)
# Safe to run again: each step skips or repeats harmlessly.
set -euo pipefail
cd "$(dirname "$0")/../.."

usage() { echo "usage: scripts/pi/install.sh with_uwb|without_uwb [--bench] [--host <host>] [--reset-config]"; exit 1; }

BUILD="${1:-}"
[[ "$BUILD" == with_uwb || "$BUILD" == without_uwb ]] || usage
shift
BENCH=0
HOST="sportcam"
RESET_CONFIG=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bench) BENCH=1 ;;
    --host) HOST="${2:?--host needs a value}"; shift ;;
    --reset-config) RESET_CONFIG=1 ;;
    *) usage ;;
  esac
  shift
done

PI="pi@${HOST}"
DEVICE="src/${BUILD}/device"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=15)
on_pi() { ssh "${SSH_OPTS[@]}" "$PI" "$@"; }
step() { printf '\n==> %s\n' "$*"; }

wait_for_pi() {
  for _ in $(seq 1 60); do
    on_pi true 2>/dev/null && return 0
    sleep 5
  done
  echo "the Pi didn't come back within 5 minutes"; exit 1
}

step "Connecting to ${PI}"
if ! on_pi true; then
  cat <<EOF

Can't log in to ${PI} without a password. Check step 1's "Done when":
  ssh ${PI}
must log you in without asking for a password. A different address:
  ./scripts/pi/install.sh ${BUILD} --host <the Pi's IP address>
EOF
  exit 1
fi
if [[ $BENCH == 1 ]]; then MODE="bench test"; else MODE="full build"; fi
echo "connected: $(on_pi 'grep PRETTY_NAME /etc/os-release | cut -d\" -f2; uname -m')"
echo "installing the ${BUILD} ${MODE}"

step "System: interfaces, OS upgrade, packages (10-20 min the first time)"
on_pi "sudo BENCH=${BENCH} bash -s" <<'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
CONFIG_TXT=/boot/firmware/config.txt
APT="apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"

raspi-config nonint do_i2c 0                        # PTZ controller (+ battery gauge)
[[ $BENCH == 1 ]] || raspi-config nonint do_spi 0   # LED ring

apt-get update
$APT full-upgrade
$APT install python3-pip python3-picamera2 python3-opencv python3-numpy libzbar0 i2c-tools

if [[ $BENCH == 0 ]]; then
  # Pan and tilt on the Pi's hardware PWM, through pigpiod
  if ! command -v pigpiod >/dev/null; then
    if apt-cache show pigpio >/dev/null 2>&1; then
      $APT install pigpio python3-pigpio
    else
      echo "no pigpio package: building it from source"
      $APT install build-essential curl
      tmp=$(mktemp -d)
      curl -fsSL https://github.com/joan2937/pigpio/archive/refs/heads/master.tar.gz | tar -xz -C "$tmp"
      make -C "$tmp"/pigpio-master -j4
      make -C "$tmp"/pigpio-master install
      rm -rf "$tmp"
      cat > /etc/systemd/system/pigpiod.service <<'UNIT'
[Unit]
Description=Pigpio daemon

[Service]
Type=forking
ExecStart=/usr/local/bin/pigpiod -l

[Install]
WantedBy=multi-user.target
UNIT
      systemctl daemon-reload
    fi
  fi
  systemctl enable pigpiod
  # Analog audio shares the PWM block with the servos
  grep -q '^dtparam=audio=off' "$CONFIG_TXT" || echo 'dtparam=audio=off' >> "$CONFIG_TXT"
fi
REMOTE

step "Copying ${DEVICE} to the Pi"
# Tracked files from this checkout, with any uncommitted edits, into a
# staging folder: the tests run there, on the checkout's own config.py
on_pi "rm -rf ~/.sportcam-staging && mkdir -p ~/.sportcam-staging"
git ls-files -z "$DEVICE" | while IFS= read -r -d '' f; do
  if [[ -f "$f" ]]; then printf '%s\0' "$f"; fi
done | COPYFILE_DISABLE=1 tar -cf - --no-xattrs --null -T - \
     | on_pi "tar -xf - -C ~/.sportcam-staging --warning=no-unknown-keyword"

step "Python packages, offline tests, camera settings"
on_pi "BUILD=${BUILD} BENCH=${BENCH} RESET_CONFIG=${RESET_CONFIG} bash -s" <<'REMOTE'
set -euo pipefail
STAGED=~/.sportcam-staging/src/$BUILD/device
DEST=~/sportcam/src/$BUILD/device
cd "$STAGED"
# numpy must be apt's: picamera2 (simplejpeg) and opencv are built against
# it. Remove a pip numpy that shadows it (pip numpy 2 breaks them)
if python3 -c 'import numpy, sys; sys.exit(not numpy.__file__.startswith("/usr/local"))' 2>/dev/null; then
  sudo pip3 uninstall -y -q --break-system-packages numpy
fi
sudo pip3 install --break-system-packages -q -r requirements.txt

failed=0
for t in tests/test_*.py; do
  if out=$(python3 "$t" 2>&1); then
    echo "  pass  $t"
  else
    echo "  FAIL  $t"; echo "$out" | tail -5 | sed 's/^/        /'; failed=1
  fi
done
if [[ $failed == 1 ]]; then
  echo "offline tests failed: nothing was changed in $DEST"; exit 1
fi

# Into place. A config.py already there holds your calibration: keep it
mkdir -p "$DEST"
keep=()
if [[ $RESET_CONFIG == 0 && -f $DEST/sportcam/config.py ]]; then
  keep=(--exclude=./sportcam/config.py)
  echo "  kept the config.py already on the Pi (--reset-config replaces it)"
fi
tar -C "$STAGED" "${keep[@]}" -cf - . | tar -C "$DEST" -xf -
rm -rf ~/.sportcam-staging
cd "$DEST"

if [[ $BENCH == 1 ]]; then
  # What the bench lacks: servos stay on the PTZ controller, no gauge, no A3
  sed -i -e 's/^SERVO_DRIVER = .*/SERVO_DRIVER = "arducam"/' \
         -e 's/^POWER_MONITOR = .*/POWER_MONITOR = "none"/' sportcam/config.py
  [[ $BUILD == without_uwb ]] || sed -i -e 's/^UWB_ANCHORS = .*/UWB_ANCHORS = 2/' sportcam/config.py
else
  python3 -m sportcam.getmodel      # MobileNet-SSD weights; skips if already there
fi
grep -E '^(SERVO_DRIVER|POWER_MONITOR|UWB_ANCHORS) = ' sportcam/config.py | sed 's/^/  config.py: /'
if [[ $BENCH == 0 ]] && grep -qE '^(SERVO_DRIVER = "arducam"|POWER_MONITOR = "none"|UWB_ANCHORS = 2)' sportcam/config.py; then
  echo "  note: the kept config.py has bench values above. For the full build, set them back"
  echo "        in $DEST/sportcam/config.py, or run again with --reset-config (loses calibration)"
fi
REMOTE

step "Rebooting (I2C, SPI and the audio setting take effect)"
on_pi "sudo systemctl reboot" 2>/dev/null || true   # "connection closed": expected
sleep 15
wait_for_pi

step "Checks"
# Capture, then search: grep -q quits at the first match, and under pipefail
# the ssh still writing the long camera list then fails the check
camera_found() { local cams; cams=$(on_pi "rpicam-hello --list-cameras 2>&1"); grep -q imx477 <<<"$cams"; }
if ! camera_found; then
  # Arducam's PTZ quick start: auto-detect off, the IMX477 overlay under [all]
  echo "no camera found: setting camera_auto_detect=0 and dtoverlay=imx477, rebooting once more"
  on_pi "sudo sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/' /boot/firmware/config.txt
         grep -q '^camera_auto_detect=0' /boot/firmware/config.txt || printf '\\n[all]\\ncamera_auto_detect=0\\n' | sudo tee -a /boot/firmware/config.txt >/dev/null
         grep -q '^dtoverlay=imx477' /boot/firmware/config.txt || printf '\\n[all]\\ndtoverlay=imx477\\n' | sudo tee -a /boot/firmware/config.txt >/dev/null"
  on_pi "sudo systemctl reboot" 2>/dev/null || true   # "connection closed": expected
  sleep 15
  wait_for_pi
fi

ok=1
check() { if eval "$2"; then echo "  ok    $1"; else echo "  FAIL  $1 — $3"; ok=0; fi; }
I2C=$(on_pi "sudo i2cdetect -y 1" || true)   # /usr/sbin: not on a plain SSH login's PATH
check "camera (IMX477)" camera_found \
  "the camera ribbon: contacts the right way round, latches closed (wiring guide, C1)"
check "PTZ controller at 0x0c" "grep -qE '^00:.* 0c( |$)' <<<\"\$I2C\"" \
  "SDA, SCL, 5V and GND to the PTZ controller (wiring guide)"
if [[ $BENCH == 0 ]]; then
  check "battery gauge at 0x40" "grep -qE '^40: 40( |$)' <<<\"\$I2C\"" \
    "the gauge's I2C (wiring guide, I1-I4)"
  check "pigpiod running" "on_pi 'pigs hwver' >/dev/null 2>&1" \
    "on the Pi: sudo systemctl status pigpiod"
fi

if ! camera_found; then
  echo "        the Pi reports:"
  on_pi "rpicam-hello --list-cameras 2>&1; grep -nE '^(camera_auto_detect|dtoverlay=imx|\\[)' /boot/firmware/config.txt" \
    | sed 's/^/          /' || true
fi

echo
if [[ $ok == 1 ]]; then
  echo "All set: the ${BUILD} ${MODE} software is installed on ${PI}."
  if [[ $BENCH == 1 ]]; then DOC="docs/${BUILD}/bench"; else DOC="docs/${BUILD}/setup"; fi
  echo "Next: step 3 of ${DOC}/14-software-setup.md"
else
  echo "Installed, but a check failed (above). Fix it and run the script again."
  exit 1
fi
