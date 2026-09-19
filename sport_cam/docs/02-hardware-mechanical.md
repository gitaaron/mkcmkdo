# 02 — Mechanical design

![Mechanical layout](images/mechanical-layout.png)

## Stack, bottom to top

1. **Standard photo tripod** — any tripod with a 1/4-20 screw. The base
   housing has a 1/4-20 brass insert epoxied into its floor.
2. **Base housing** (3D-printed, ~120 × 120 × 60 mm): 12 V barrel jack, ESP32
   DevKitC, TMC2209 on the carrier PCB, buck #1, and the WS2812B LED ring in a
   diffused window around the circumference so status is visible from any
   direction.
3. **Pan stage**: a 3" lazy-susan bearing carries the rotating platform. A
   printed 120-tooth GT2 ring pulley is bolted to the platform's underside —
   its 60 mm bore encircles the slip-ring flange — and the NEMA17 (20-tooth
   pulley) drives it by belt at 6:1. 1.8° motor × 16 microsteps × 6 =
   **0.019°/step** — far finer than needed to keep a person centred.
4. **Slip ring** (Adafruit-style 22 mm, 12 wires @ 2 A) mounted in the centre
   of the pan axis. We parallel wires: 4 for +12 V, 4 for GND (≈ 8 A capacity),
   4 spare. Its stationary flange screws to the base; the rotating shaft wires
   feed the platform.
5. **Rotating platform** (3D-printed or 3 mm aluminium plate): carries the
   Raspberry Pi 5, buck #2 (Pi rail) and buck #3 (servo rail), the tilt tower,
   and the two UWB anchor arms.
6. **Tilt tower**: two printed uprights; the DS3225 270° servo sits in one,
   its spline driving the camera cradle shaft; the far side rides in a 6701ZZ
   ball bearing. Mount the camera so the lens axis passes through the tilt
   axis (minimises parallax and servo load).
7. **Camera cradle**: Arducam IMX219 + motorized zoom lens. The lens's zoom
   and focus are driven by the lens's own little steppers via I2C — no extra
   mechanics needed.

## Ranges of motion

| Axis | Mechanism | Range | Notes |
| --- | --- | --- | --- |
| Pan | NEMA17 + TMC2209, GT2 6:1 belt | **360° continuous, unlimited turns** | Homing via hall sensor + magnet on the platform edge |
| Tilt | DS3225 270° servo, direct drive | **−45° … +225°** (270°) | > 180° vertical requirement met; end stops enforced in software |
| Zoom | Arducam motorized lens | ~8–20 mm EFL (≈ 2.5× optical) | Plus digital crop for further reach |

The 270° tilt is what buys ">180° on the vertical plane": the camera can look
45° below the horizon, up through the zenith, and 45° below the horizon on the
*other* side. Combined with continuous pan, every direction above (and
slightly below) the tripod is reachable — and the pan axis can always take the
"shorter way round" because it is unlimited.

## Design rules that matter

- **Nothing but power crosses the slip ring.** Video, control, and telemetry
  are Wi-Fi. If you ever see stepper noise on the head's 5 V rail, add a
  470 µF electrolytic + ferrite at buck #2's input.
- **Mass balance**: keep the Pi and bucks diametrically opposite the tilt
  tower so the platform's centre of mass sits on the pan axis; the stepper
  then only fights inertia, not gravity.
- **Cable service loop**: the tilt axis needs ~120 mm of slack in the camera
  FFC, spiralled around the tilt shaft.
- **UWB anchors** go at the ends of two 200 mm printed arms (400 mm baseline),
  level with the camera, with their antennas clear of the metal plate — see
  [04 — Tracking system](04-tracking-system.md) for why baseline length sets
  bearing resolution.
- Print structural parts in **PETG** (20 % infill, 4 walls); brackets touching
  the servo in **PETG or ABS** (servo gets warm).

## Printed / fabricated parts list

| Part | Qty | Notes |
| --- | --- | --- |
| Base housing + LED diffuser ring | 1 | diffuser in white PETG, 2 walls, 0 % infill |
| Rotating platform | 1 | or 3 mm aluminium plate |
| 120T GT2 ring pulley | 1 | print at 0.16 mm layers; must be a ring (ID 60 mm) to clear the slip-ring flange |
| Tilt tower uprights | 2 | one carries servo, one carries 6701ZZ bearing |
| Camera cradle | 1 | fits Arducam lens barrel |
| UWB anchor arms | 2 | 200 mm, dovetail into platform |
| Wearable case + strap loop | 1 | fits ESP32-UWB board + 1000 mAh LiPo |

## CAD sources

All printed parts have **parametric OpenSCAD sources in [`cad/`](../cad/)** —
every dimension (bearing sizes, board hole patterns, lens diameter, clearances)
lives in `cad/config.scad`. Render everything to STL with:

```bash
./cad/render_all.sh        # requires openscad; outputs to cad/stl/
```

Before printing, measure and update the three dimensions flagged `MEASURE
YOURS` in `config.scad`: the Arducam lens barrel diameter (`lens_d`), and your
UWB board's outline/hole pattern (`uwb_*`) — vendors vary. Precision features
are only the pan-bearing bolt circle and the servo interface; use the
DS3225's included metal horn screwed into the printed cradle rather than
printing a spline.

Prefer remixing proven designs? See
[08 — Open-source printed-part alternatives](08-open-source-parts.md).
