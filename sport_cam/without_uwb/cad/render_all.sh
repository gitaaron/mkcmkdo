#!/usr/bin/env bash
# Render every SportCam part to STL.  Requires openscad on PATH.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p stl

render() { echo "→ $2"; openscad -o "stl/$2" "${@:3}" "$1" 2>/dev/null || openscad -o "stl/$2" "${@:3}" "$1"; }

render base_housing.scad      base_housing.stl
render lid.scad               lid.stl
render led_diffuser_ring.scad led_diffuser_ring.stl
render battery_tray.scad      battery_tray.stl

echo "done — STLs in cad/stl/"
