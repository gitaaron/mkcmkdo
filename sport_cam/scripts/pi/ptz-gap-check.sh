#!/usr/bin/env bash
# How soon after a pan write the PTZ controller takes a tilt write. The
# camera software writes both axes each control tick; ptz-check spaces its
# writes out, so it can pass while the joystick's tilt does nothing. This
# writes pan, waits a gap, writes tilt, and reads tilt back: the smallest gap
# that lands every time is the spacing the writes need.
#
#   ./scripts/pi/ptz-gap-check.sh                      pi@sportcam.local
#   ./scripts/pi/ptz-gap-check.sh --host 192.168.1.42
#
# Stop the camera software first (Ctrl-C on `./scripts/pi/run main`).
set -uo pipefail

HOST="sportcam"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:?--host needs a value}"; shift ;;
    *) echo "usage: scripts/pi/ptz-gap-check.sh [--host <host>]"; exit 1 ;;
  esac
  shift
done

PI="pi@${HOST}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
on_pi() { ssh "${SSH_OPTS[@]}" "$PI" "$@"; }

on_pi true || { echo "can't log in to ${PI} without a password (software setup, step 1)"; exit 1; }

on_pi "python3 -" <<'PY'
import time
from smbus2 import SMBus

ADDR, PAN, TILT = 0x0C, 0x05, 0x06

def swap(v):
    return ((v & 0xFF) << 8) | ((v >> 8) & 0xFF)

def read(b, reg):
    return swap(b.read_word_data(ADDR, reg))

def write(b, reg, v):
    b.write_word_data(ADDR, reg, swap(v))

try:
    with SMBus(1) as b:
        print("pan, then tilt after a gap; tilt read back 0.3 s later\n")
        for gap_ms in (0, 2, 5, 10, 20, 50):
            hits = 0
            for i in range(4):
                pan, tilt = (95, 85) if i % 2 else (85, 95)
                write(b, PAN, pan)
                time.sleep(gap_ms / 1000)
                write(b, TILT, tilt)
                time.sleep(0.3)
                hits += read(b, TILT) == tilt
            print(f"  gap {gap_ms:2d} ms: tilt landed {hits}/4")
        write(b, PAN, 90)
        time.sleep(0.05)
        write(b, TILT, 90)
        print("\nhead centred")
except OSError as e:
    print(f"\nI2C error: {e}")
    print("The controller doesn't answer at 0x0c: its cable's pins 3-6 (5V, GND, SCL, SDA).")
    raise SystemExit(2)
PY
