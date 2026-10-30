#!/usr/bin/env bash
# Talks to the PTZ controller directly, from your computer, bypassing the
# camera software: reports the controller's state, then moves pan, tilt and
# zoom one at a time and reads each setting back. It speaks to the controller
# exactly as Arducam's own code for the IMX477 PTZ kit does
# (github.com/ArduCAM/PTZ-Camera-Controller, B016712MP/Focuser.py): wait for
# the busy register to clear, then a 16-bit word, high byte first.
#
#   ./scripts/pi/ptz-check.sh                      pi@sportcam.local
#   ./scripts/pi/ptz-check.sh --host 192.168.1.42
#   ./scripts/pi/ptz-check.sh --reset-mode            also Arducam's lens reset and
#                                                      mode switch (its tool's r and t
#                                                      keys), then the moves again
#
# Stop the camera service first if it runs: ssh pi@sportcam.local sudo systemctl stop sportcam-head
set -uo pipefail

HOST="sportcam"
RESET_MODE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:?--host needs a value}"; shift ;;
    --reset-mode) RESET_MODE=1 ;;
    *) echo "usage: scripts/pi/ptz-check.sh [--host <host>] [--reset-mode]"; exit 1 ;;
  esac
  shift
done

PI="pi@${HOST}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
on_pi() { ssh "${SSH_OPTS[@]}" "$PI" "$@"; }

on_pi true || { echo "can't log in to ${PI} without a password (software setup, step 1)"; exit 1; }

echo "Watch the head: each step pauses so you can see whether it moved."
on_pi "RESET_MODE=${RESET_MODE} python3 -" <<'PY'
import os
import time
from smbus2 import SMBus

ADDR, BUSY, VERSION, MODE = 0x0C, 0x04, 0x40, 0x30
STEPS = [  # (axis, register, values) -- the IMX477 kit's map
    ("pan",  0x05, (45, 135, 90)),
    ("tilt", 0x06, (45, 135, 90)),
    ("zoom", 0x01, (2100, 0)),
]

def swap(v):
    return ((v & 0xFF) << 8) | ((v >> 8) & 0xFF)

def read(b, reg):
    return swap(b.read_word_data(ADDR, reg))

def wait_free(b, timeout_s=6.0):
    t0 = time.monotonic()
    while read(b, BUSY) and time.monotonic() - t0 < timeout_s:
        time.sleep(0.01)
    return time.monotonic() - t0

def status(b):
    print(f"  firmware version 0x{read(b, VERSION):04x}")
    print(f"  busy register    0x{read(b, BUSY):04x}  (0 = idle)")
    print(f"  mode register    0x{read(b, MODE):04x}")

def command(b, label, reg, value, timeout_s):
    wait_free(b)
    b.write_word_data(ADDR, reg, swap(value))
    time.sleep(0.05)
    busy = read(b, BUSY)
    took = wait_free(b, timeout_s)
    print(f"  {label}: busy after write 0x{busy:04x}, busy for {took:.2f} s")

try:
    with SMBus(1) as b:
        print("\ncontroller:")
        status(b)
        if os.environ.get("RESET_MODE") == "1":
            print("\nArducam's lens reset (watch and listen: the lens motors should run)")
            command(b, "focus reset (0x0A)", 0x0A, 0, 15)
            command(b, "zoom reset (0x0B)", 0x0B, 0, 15)
            mode = read(b, MODE)
            print(f"\nArducam's mode switch: 0x{mode:04x} -> 0x{mode ^ 1:04x} (can take ~15 s)")
            command(b, "mode (0x30)", MODE, mode ^ 1, 20)
            print("\ncontroller now:")
            status(b)
        all_match = True
        for name, reg, values in STEPS:
            print(f"\n{name}:  starts at {read(b, reg)}")
            for v in values:
                waited = wait_free(b)
                b.write_word_data(ADDR, reg, swap(v))
                time.sleep(0.05)
                busy_after = read(b, BUSY)
                moving_s = wait_free(b)
                time.sleep(1.5)
                got = read(b, reg)
                ok = got == v
                all_match &= ok
                print(f"  set {v:4d} -> reads back {got:5d}  {'ok' if ok else 'DIFFERENT':9s}"
                      f"  busy after write 0x{busy_after:04x}, busy for {moving_s:.2f} s")
except OSError as e:
    print(f"\nI2C error: {e}")
    print("The controller doesn't answer at 0x0c: its cable's pins 3-6 (5V, GND, SCL, SDA).")
    raise SystemExit(2)

print()
if all_match:
    print("The controller took and kept every setting.")
    print("  Head moved:           tell Claude; the camera software needs to match this.")
    print("  Nothing moved at all: the motors get no power. Cable pins 1-2 (red to Pi pin 2,")
    print("                        black to Pi pin 14); about 5 V between them at the controller.")
    print("  Zoom moved, servos didn't: the servo plugs (PAN/TILT sockets, brown to GND).")
else:
    print("Some settings read back different: paste this whole output to Claude,")
    print("and say whether anything moved.")
PY
