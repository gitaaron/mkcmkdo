#!/usr/bin/env bash
# Checks the camera (and the PTZ controller) on the Pi, from your computer,
# without reinstalling anything: re-seat the ribbon, reboot the Pi, run this.
#
#   ./scripts/pi/camera-check.sh                      pi@sportcam.local
#   ./scripts/pi/camera-check.sh --host 192.168.1.42
#   ./scripts/pi/camera-check.sh --no-photo           skip the test photo
#
# It reads what the Pi's kernel and camera stack report, says which of these
# it is, and with a camera found, takes a photo and opens it on your Mac:
#   - camera found
#   - the IMX477 driver loaded but the sensor doesn't answer: the ribbon
#   - no IMX477 driver at all: the boot config, or the firmware saw no camera
# Changes nothing on the Pi.
set -uo pipefail

HOST="sportcam"
PHOTO=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:?--host needs a value}"; shift ;;
    --no-photo) PHOTO=0 ;;
    *) echo "usage: scripts/pi/camera-check.sh [--host <host>] [--no-photo]"; exit 1 ;;
  esac
  shift
done

PI="pi@${HOST}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
on_pi() { ssh "${SSH_OPTS[@]}" "$PI" "$@"; }

on_pi true || { echo "can't log in to ${PI} without a password (software setup, step 1)"; exit 1; }

echo "==> Boot config (/boot/firmware/config.txt)"
on_pi "grep -nE '^(camera_auto_detect|dtoverlay=imx|\[)' /boot/firmware/config.txt" | sed 's/^/  /'

echo
echo "==> Kernel log (camera)"
KLOG=$(on_pi "sudo dmesg | grep -iE 'imx477|unicam'" || true)
if [[ -n "$KLOG" ]]; then sed 's/^/  /' <<<"$KLOG"; else echo "  (nothing)"; fi

echo
echo "==> Cameras the Pi sees (rpicam-hello --list-cameras)"
CAMS=$(on_pi "rpicam-hello --list-cameras 2>&1" || true)
sed 's/^/  /' <<<"$CAMS"

echo
echo "==> PTZ controller on I2C (0x0c)"
I2C=$(on_pi "sudo i2cdetect -y 1" || true)   # captured: grep -q in a pipe races the ssh
if grep -qE '^00:.* 0c( |$)' <<<"$I2C"; then
  echo "  ok: 0x0c answers"
else
  echo "  not found: the controller's cable, I1/I2 and J1/J2 (bench wiring guide)"
fi

echo
echo "==> Verdict"
if grep -q imx477 <<<"$CAMS"; then
  echo "  Camera found."
  if [[ $PHOTO == 1 ]]; then
    OUT="${TMPDIR:-/tmp}/sportcam-test-$(date +%H%M%S).jpg"
    if on_pi "rpicam-still -n -t 1500 --width 1280 --height 720 -o /tmp/camcheck.jpg >/dev/null 2>&1" \
       && scp -q "${SSH_OPTS[@]}" "${PI}:/tmp/camcheck.jpg" "$OUT"; then
      echo "  Test photo: $OUT"
      [[ "$(uname)" == Darwin ]] && open "$OUT"
    else
      echo "  Found, but the test photo failed: on the Pi, run: rpicam-still -o /tmp/t.jpg"
    fi
  fi
  exit 0
elif grep -qiE 'imx477.*(fail|error)' <<<"$KLOG"; then
  echo "  The IMX477 driver loaded but the sensor didn't answer it. That's the"
  echo "  ribbon: power off, then at both ends lift the latch, push the ribbon"
  echo "  fully in (silver contacts toward the HDMI ports at the Pi) and press"
  echo "  the latch down. It must be the CAMERA socket, between the HDMI ports"
  echo "  and the audio jack, not the display one."
elif grep -qE '^[0-9]+:camera_auto_detect=0' < <(on_pi "grep -n camera_auto_detect /boot/firmware/config.txt") \
     && ! on_pi "grep -q '^dtoverlay=imx477' /boot/firmware/config.txt"; then
  echo "  Auto-detect is off and there's no dtoverlay=imx477 line: add it under"
  echo "  [all] in /boot/firmware/config.txt and reboot (or re-run scripts/pi/install.sh)."
else
  echo "  No IMX477 driver loaded, so at boot the firmware saw no camera. Check the"
  echo "  ribbon as above. If config.txt still has camera_auto_detect=1, re-run"
  echo "  scripts/pi/install.sh: it switches to dtoverlay=imx477, as Arducam says to."
fi
echo
echo "  After a fix: ssh ${PI} sudo reboot, wait a minute, run this again."
exit 1
