# cad/ — parametric OpenSCAD sources for all printed parts

Every dimension lives in **`config.scad`** (bearing sizes, board hole
patterns, lens diameter, clearances). Change it there, re-render, and all
parts stay consistent.

## Render

```bash
./render_all.sh          # requires openscad; STLs land in cad/stl/
# or one part:
openscad -o stl/ring_pulley.stl ring_pulley.scad
openscad -o stl/tilt_tower_bearing.stl -D 'side="bearing"' tilt_tower.scad
```

## Parts

| File | Part | Print settings |
| --- | --- | --- |
| `base_housing.scad` | Base shell: deck for lazy-susan + slip ring + NEMA17, LED window, 1/4-20 tripod boss | PETG, 4 walls, 20 %, no supports (jack hole bridges fine) |
| `led_diffuser_ring.scad` | Translucent band closing the LED window | white/natural PETG, 2 walls, 0 % infill |
| `ring_pulley.scad` | 120T GT2 ring pulley, ID 60 (encircles slip-ring flange), 6:1 with 20T motor pulley | 0.16 mm layers, 5 walls |
| `rotating_platform.scad` | Platform: bearing + pulley bolt patterns, Pi standoffs, tower slots, arm sockets | PETG, 25 %+, 5 walls |
| `tilt_tower.scad` | Uprights — render twice: `-D 'side="servo"'` and `-D 'side="bearing"'` | PETG/ABS, 30 %, print upright with brim |
| `camera_cradle.scad` | Lens-barrel clamp; servo-horn screws one side, 6701ZZ stub shaft the other | PETG, 30 %, supports under stub |
| `anchor_arm.scad` | 200 mm UWB anchor arm (×2) | print flat, 4+ walls |
| `wearable_case.scad` | Wearable pod body + lid, strap bars, USB-C slot | PETG, 2 walls; TPU also works nicely |

## Before printing — measure these

Three dimensions in `config.scad` are marked `MEASURE YOURS` because vendors
vary:

- `lens_d` — Arducam zoom-lens barrel diameter (set to 33; measure with
  calipers)
- `uwb_l/uwb_w/uwb_hole_*` — your ESP32-UWB board outline and hole pattern
- `servo_*` — verify against your DS3225's datasheet drawing (most clones
  match)

Also verify the slip-ring flange (`sr_*`) against the unit you receive; the
defaults fit the Adafruit-736-class 22 mm rings.

Prefer remixing community designs instead? See
[docs/08-open-source-parts.md](../docs/08-open-source-parts.md).
