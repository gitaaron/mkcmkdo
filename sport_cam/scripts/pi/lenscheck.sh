#!/usr/bin/env bash
# Runs the lens diagnostic on the Pi (python -m sportcam.lenscheck) and keeps
# what it found on this computer, in logs/:
#
#   logs/lenscheck-<time>.log   everything it printed (also shown as it runs)
#   logs/lenscheck-<time>.jpg   its contact sheet: focus motor alone, zoom alone
#
#   ./scripts/pi/lenscheck.sh                    stop `run main` first: it needs the camera
#   ./scripts/pi/lenscheck.sh --host 192.168.4.37
set -uo pipefail
cd "$(dirname "$0")/../.."

HOST="${SPORTCAM_HOST:-sportcam}"
if [[ "${1:-}" == --host ]]; then HOST="${2:?--host needs a value}"; fi

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o LogLevel=ERROR)
PI="pi@${HOST}"

# Only one program can hold the camera. [s]: pgrep's own command line, which
# ssh runs in a shell, must not match
if ssh "${SSH_OPTS[@]}" "$PI" "pgrep -f '[s]portcam[.]main' >/dev/null"; then
  echo "The camera software is running on the Pi, and it holds the camera."
  echo "Stop ./scripts/pi/run main (Ctrl-C in its terminal), then run this again."
  echo "If nothing is running in a terminal, it was left behind; stop it with:"
  echo "  ./scripts/pi/run pkill -f '[s]portcam[.]main'"
  exit 1
fi

mkdir -p logs
stamp=$(date +%Y%m%d-%H%M%S)
log="logs/lenscheck-${stamp}.log"
jpg="logs/lenscheck-${stamp}.jpg"

# Not last run's picture, if this one fails
ssh "${SSH_OPTS[@]}" "$PI" 'rm -f ~/lenscheck.jpg'
./scripts/pi/run --host "$HOST" PYTHONUNBUFFERED=1 lenscheck 2>&1 | tee "$log"
status=${PIPESTATUS[0]}

if [[ $status != 0 ]]; then
  echo "lenscheck failed: saved ${log}, no contact sheet"
elif scp -q -o ConnectTimeout=10 -o LogLevel=ERROR "pi@${HOST}:lenscheck.jpg" "$jpg"; then
  echo "saved ${log} and ${jpg}"
else
  echo "saved ${log} (no contact sheet came back from the Pi)"
fi
exit "$status"
