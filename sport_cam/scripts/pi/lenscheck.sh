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

mkdir -p logs
stamp=$(date +%Y%m%d-%H%M%S)
log="logs/lenscheck-${stamp}.log"
jpg="logs/lenscheck-${stamp}.jpg"

./scripts/pi/run --host "$HOST" PYTHONUNBUFFERED=1 lenscheck 2>&1 | tee "$log"
status=${PIPESTATUS[0]}

if scp -q -o ConnectTimeout=10 -o LogLevel=ERROR "pi@${HOST}:lenscheck.jpg" "$jpg"; then
  echo "saved ${log} and ${jpg}"
else
  echo "saved ${log} (no contact sheet came back from the Pi)"
fi
exit "$status"
