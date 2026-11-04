#!/usr/bin/env bash
# Copies the samples the app's Sample button saved on the camera (samples.py,
# in ~/samples on the Pi) into samples/ here, each once: a frame at full size,
# the frame detection saw, and a .json of what it made of it.
#
#   ./scripts/pi/samples.sh                  copy the new ones; the Pi keeps its copies
#   ./scripts/pi/samples.sh --move           …and delete them from the Pi once copied
#   ./scripts/pi/samples.sh --host 192.168.4.37
#   ./scripts/pi/samples.sh --clean          delete every sample, on the Pi and in
#                                            samples/ here (asks first; --yes doesn't)
#
# They are photos of people: samples/ is ignored by git, and they never go to
# the cloud backend.
set -uo pipefail
cd "$(dirname "$0")/../.."

HOST="${SPORTCAM_HOST:-sportcam}"
MOVE=0
CLEAN=0
YES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:?--host needs a value}"; shift ;;
    --move) MOVE=1 ;;
    --clean) CLEAN=1 ;;
    --yes) YES=1 ;;
    *) echo "usage: scripts/pi/samples.sh [--host <host>] [--move | --clean [--yes]]"; exit 1 ;;
  esac
  shift
done

PI="pi@${HOST}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR)
mkdir -p samples

if [[ $CLEAN == 1 ]]; then
  # Every sample, both ends: after the camera is moved or re-mounted, old
  # ones no longer show what detection sees
  here=$(ls samples/*.json 2>/dev/null | wc -l | tr -d ' ')
  there=$(ssh "${SSH_OPTS[@]}" "$PI" 'ls ~/samples/*.json 2>/dev/null | wc -l') || {
    echo "can't reach ${PI}: nothing deleted"; exit 1; }
  there=$(echo "$there" | tr -d ' ')
  if [[ $YES != 1 ]]; then
    read -r -p "Delete ${there} sample(s) on the Pi and ${here} in samples/ here? This can't be undone. [y/N] " ok
    [[ $ok == [yY]* ]] || { echo "nothing deleted"; exit 0; }
  fi
  ssh "${SSH_OPTS[@]}" "$PI" 'rm -f ~/samples/*' || { echo "deleting on the Pi failed: nothing deleted here"; exit 1; }
  rm -f samples/*
  echo "deleted ${there} sample(s) on the Pi and ${here} here"
  exit 0
fi

before=$(ls samples/*.json 2>/dev/null | wc -l | tr -d ' ')

if ! ssh "${SSH_OPTS[@]}" "$PI" 'test -d ~/samples'; then
  echo "no samples on the Pi yet: take some with the app's Sample button"
  exit 0
fi

if ssh "${SSH_OPTS[@]}" "$PI" 'command -v rsync >/dev/null' && command -v rsync >/dev/null; then
  extra=()
  [[ $MOVE == 1 ]] && extra=(--remove-source-files)
  rsync -a --ignore-existing ${extra[@]+"${extra[@]}"} -e "ssh ${SSH_OPTS[*]}" "${PI}:samples/" samples/ || exit 1
else
  # no rsync: the whole folder over tar, keeping what is here already
  ssh "${SSH_OPTS[@]}" "$PI" 'cd ~/samples && tar -cf - .' | tar -xkf - -C samples 2>/dev/null
  sent=${PIPESTATUS[0]}
  if [[ $sent != 0 ]]; then
    echo "copying from the Pi failed: nothing removed there"; exit 1
  fi
  if [[ $MOVE == 1 ]]; then
    # only what is safely here now
    for f in samples/*; do
      printf '%s\n' "$(basename "$f")"
    done | ssh "${SSH_OPTS[@]}" "$PI" 'cd ~/samples && xargs -r rm -f --'
  fi
fi

after=$(ls samples/*.json 2>/dev/null | wc -l | tr -d ' ')
echo "copied $((after - before)) new sample(s) into samples/ (${after} in all)$([[ $MOVE == 1 ]] && echo '; removed from the Pi')"
