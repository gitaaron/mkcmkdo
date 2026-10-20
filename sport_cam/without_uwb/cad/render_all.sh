#!/usr/bin/env bash
# Render every SportCam part to STL.  Requires openscad on PATH.
#
# Run on its own, this hands over to cad/fit.py, which first re-solves the
# layout from the part sizes (cad/ordered_parts.toml) and config.scad, calls
# back here to render, then audits that everything fits. So a CAD change can't
# skip the fit check.
set -euo pipefail
cd "$(dirname "$0")"
if [ -z "${SPORTCAM_FIT_RUNNING:-}" ]; then
    exec python3 ../../cad/fit.py --render --build "$(basename "$(dirname "$PWD")")"
fi
mkdir -p stl

render() { echo "→ $2"; openscad -o "stl/$2" "${@:3}" "$1" 2>/dev/null || openscad -o "stl/$2" "${@:3}" "$1"; }

render base_housing.scad      base_housing.stl
render lid.scad               lid.stl
render led_diffuser_ring.scad led_diffuser_ring.stl
render shelf.scad             shelf.stl
render battery_tray.scad      battery_tray.stl

echo "done — STLs in cad/stl/"
