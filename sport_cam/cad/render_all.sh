#!/usr/bin/env bash
# Render every SportCam part to STL.  Requires openscad on PATH.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p stl

render() { echo "→ $2"; openscad -o "stl/$2" "${@:3}" "$1" 2>/dev/null || openscad -o "stl/$2" "${@:3}" "$1"; }

render base_housing.scad      base_housing.stl
render led_diffuser_ring.scad led_diffuser_ring.stl
render ring_pulley.scad       ring_pulley.stl
render rotating_platform.scad rotating_platform.stl
render tilt_tower.scad        tilt_tower_servo.stl   -D 'side="servo"'
render tilt_tower.scad        tilt_tower_bearing.stl -D 'side="bearing"'
render camera_cradle.scad     camera_cradle.stl
render anchor_arm.scad        anchor_arm.stl
render wearable_case.scad     wearable_case.stl

echo "done — STLs in cad/stl/"
