#!/usr/bin/env bash
# Puts this checkout's camera software on a Pi that install.sh has already
# set up, and restarts it: no OS upgrade, no reboot, about a minute.
#
#   ./scripts/pi/deploy.sh without_uwb
#   ./scripts/pi/deploy.sh without_uwb --host 192.168.4.37
#   ./scripts/pi/deploy.sh without_uwb --take VIEW_ROTATE_DEG,VIEW_MIRROR
#
# It copies src/<build>/device as it is here — uncommitted edits and new
# files included — runs the offline tests on the Pi, and only if they pass
# puts it in ~/sportcam/src/<build>/device. The config.py on the Pi is kept
# (your calibration), with any settings new since added at their defaults.
# --take copies the named settings' values from this checkout's config.py
# over the Pi's: a value you changed here on purpose.
set -euo pipefail
cd "$(dirname "$0")/../.."

usage() { echo "usage: scripts/pi/deploy.sh with_uwb|without_uwb [--host <host>] [--take NAME,NAME…]"; exit 1; }

BUILD="${1:-}"
[[ "$BUILD" == with_uwb || "$BUILD" == without_uwb ]] || usage
shift
HOST="${SPORTCAM_HOST:-sportcam}"
TAKE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:?--host needs a value}"; shift ;;
    --take) TAKE="${2:?--take needs setting names}"; shift ;;
    *) usage ;;
  esac
  shift
done

PI="pi@${HOST}"
DEVICE="src/${BUILD}/device"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=15)
on_pi() { ssh "${SSH_OPTS[@]}" "$PI" "$@"; }
step() { printf '\n==> %s\n' "$*"; }

step "Connecting to ${PI}"
if ! on_pi true; then
  echo "Can't log in to ${PI} without a password. Another address: --host <the Pi's IP>"
  exit 1
fi
on_pi "test -d ~/sportcam/src/${BUILD}/device" \
  || { echo "No ${BUILD} install on the Pi yet: run scripts/pi/install.sh first"; exit 1; }
# The offline tests serve the local API on its port: the camera running
# (`run main`, or its service) holds it, and they would fail
if on_pi "ss -ltn 2>/dev/null | grep -q ':8787 '"; then
  if on_pi "systemctl is-active --quiet sportcam-head 2>/dev/null"; then
    on_pi "sudo systemctl stop sportcam-head"     # restarted at the end, or on failure:
    trap 'on_pi "sudo systemctl start sportcam-head" >/dev/null 2>&1' EXIT
  else
    echo "The camera software is running on the Pi (port 8787 is in use)."
    echo "Stop ./scripts/pi/run main (Ctrl-C in its terminal), then deploy again."
    exit 1
  fi
fi

step "Copying ${DEVICE} to the Pi"
on_pi "rm -rf ~/.sportcam-staging && mkdir -p ~/.sportcam-staging"
{ git ls-files -z --cached --others --exclude-standard "$DEVICE"; printf '%s\0' scripts/pi/config_merge.py; } \
  | while IFS= read -r -d '' f; do
      if [[ -f "$f" && "$f" != *__pycache__* ]]; then printf '%s\0' "$f"; fi
    done | COPYFILE_DISABLE=1 tar -cf - --no-xattrs --null -T - \
         | on_pi "tar -xf - -C ~/.sportcam-staging --warning=no-unknown-keyword"

step "Offline tests on the Pi, then into place"
on_pi "BUILD=${BUILD} TAKE=${TAKE} bash -s" <<'REMOTE'
set -euo pipefail
STAGED=~/.sportcam-staging/src/$BUILD/device
DEST=~/sportcam/src/$BUILD/device
cd "$STAGED"
sudo pip3 install --break-system-packages -q -r requirements.txt
failed=0
for t in tests/test_*.py; do
  if out=$(python3 "$t" 2>&1); then
    echo "  pass  $t"
  else
    echo "  FAIL  $t"; echo "$out" | tail -5 | sed 's/^/        /'; failed=1
  fi
done
if out=$(python3 -c 'import sportcam.main' 2>&1); then
  echo "  pass  import sportcam.main"
else
  echo "  FAIL  import sportcam.main"; echo "$out" | tail -5 | sed 's/^/        /'; failed=1
fi
if [[ $failed == 1 ]]; then
  echo "offline tests failed: nothing was changed in $DEST"; exit 1
fi
tar -C "$STAGED" --exclude=./sportcam/config.py -cf - . | tar -C "$DEST" -xf -
python3 ~/.sportcam-staging/scripts/pi/config_merge.py \
  "$STAGED/sportcam/config.py" "$DEST/sportcam/config.py" "$TAKE"
rm -rf ~/.sportcam-staging
# The SSD person detector's weights (not in git): skipped if already there.
# Without them (no internet) the camera falls back to HOG and says so.
cd "$DEST"
python3 -m sportcam.getmodel || echo "  couldn't fetch the SSD weights: the camera will use HOG until it can"
# Recordings are written through ffmpeg; an install from before it was in
# install.sh doesn't have it, and every recording would write nothing
if ! command -v ffmpeg >/dev/null; then
  echo "  installing ffmpeg (recordings are written through it)…"
  sudo apt-get install -y -q ffmpeg >/dev/null \
    || echo "  couldn't install ffmpeg: the camera will refuse to record until it is"
fi
REMOTE

step "Restarting the camera"
if ! on_pi "systemctl list-unit-files sportcam-head.service | grep -q sportcam-head"; then
  echo "  no sportcam-head service on this Pi: if you run it by hand"
  echo "  (./scripts/pi/run main), stop that (Ctrl-C) and start it again"
  exit 0
fi
trap - EXIT
on_pi "sudo systemctl restart sportcam-head"
sleep 4
if on_pi "systemctl is-active --quiet sportcam-head"; then
  echo "  sportcam-head is running"
else
  echo "  sportcam-head didn't stay up. Its log:"
  on_pi "journalctl -u sportcam-head -n 30 --no-pager" || true
  exit 1
fi
