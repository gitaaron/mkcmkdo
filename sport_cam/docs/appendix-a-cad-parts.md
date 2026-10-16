# Appendix A — CAD: printed parts

Parametric OpenSCAD sources for every printed part live in
[`cad/`](../cad/). Every dimension is in **[`cad/config.scad`](../cad/config.scad)**
(enclosure size, board hole patterns, anchor baseline, battery size,
clearances) — change it there, re-render, and all parts stay consistent.
Compiled STLs are committed in [`cad/stl/`](../cad/stl/); per-part previews and
download links are in the [BOM's printed-parts table](07-bill-of-materials.md#printed-parts).

This is the **PTZ-base build**: the camera, both motion axes and the zoom lens
are one bought assembly, so everything printed here is an enclosure or a
bracket. The pan stage parts (ring pulley, rotating platform, tilt towers,
camera cradle) were deleted along with the stepper.

## Render

```bash
./cad/render_all.sh              # requires openscad; STLs land in cad/stl/
python3 cad/render_previews.py   # preview PNGs → docs/images/parts/
# or one part:
openscad -o cad/stl/lid.stl cad/lid.scad
```

After any change, also refresh the assembly guide's meshes:

```bash
python3 docs/setup/assembly/build_models.py
python3 docs/setup/assembly/render_steps.py
```

Inside the project's Docker workspace (see `compose.yaml` at the repo root)
OpenSCAD and the Python libraries are pre-installed.

## Print settings, materials and printer requirements

Per-part settings are summarised below, but the full treatment — printer
requirements, filament to buy, orientation, where the one bit of support is
needed, print times and the PETG-on-PEI trap — is in
**[3D printing specifications](3d_printer/specifications.md)**.

## Parts

| File | Part | Print settings |
| --- | --- | --- |
| `base_housing.scad` | Enclosure (Ø 135 × 66): Pi standoffs, LED window, 5 V jack, vents, three wall bosses (anchor arms at ±Y, A3 mast at −X), tripod boss for a 3/8-16 insert | PETG, 4 walls, 20 %; support only under the three bosses |
| `lid.scad` | Top plate carrying the Arducam pan-tilt base; slotted bolt pattern, central cable opening | PETG, **5 walls, 40 %** — this part holds the camera up |
| `led_diffuser_ring.scad` | Translucent band closing the LED window | white/natural PETG, 2 walls, 0 % infill |
| `anchor_arm.scad` | Static UWB anchor arm (×2); bolts to the M3 inserts in the ±Y bosses | print flat, 4+ walls |
| `anchor_mast.scad` | A3 mast: `part="foot"` bolts to the −X boss and holds a ½" dowel; `part="cradle"` caps it and carries the board. Echoes the dowel cut length (246 mm) | socket up, 4+ walls; one M3 insert per socket |
| `battery_tray.scad` | Saddle for the USB-C power bank, strap slots + 1/4-20 bore | PETG, 3 walls, 20 % |
| `wearable_case.scad` | Wearable pod body + lid, strap bars, USB-C slot | PETG, 2 walls; TPU also works nicely |

## Before printing — measure these

The same list lives in
[10 — Verification checklist](10-verification.md#before-you-print), together
with the on-arrival and bench checks.

Dimensions in `config.scad` marked `MEASURE YOURS`, because vendors vary:

- `ptz_bolt_min` / `ptz_bolt_max` — **the important one.** Arducam publishes no
  drawing for the B0167B12 metal base and the footprint has changed between
  revisions, so the lid is cut with radial slots spanning 30–72 mm instead of
  fixed holes. Measure your base, check it falls inside, mark through the
  slots and bolt it down with M3 and nuts.
- `bank_l/w/h` — your power bank. Banks of the same capacity vary by 15 mm in
  every direction.
- `uwb_l/uwb_w/uwb_hole_*` — the ULA1's outline and hole pattern. The manual
  gives 40 × 25 mm but not the mounting holes.
- `mast_d` — your dowel. "½-inch" dowels run a few tenths either side of
  12.7 mm; the sockets add `clr` on top, and the pinch screws take up the
  rest.
- `tripod_hole_d` — the bore for the 3/8-16 brass insert, modelled at
  12.7 mm. Epoxied, so aim for a snug slip fit; open it up rather than
  reprint if yours is larger. The insert must be no longer than the 8 mm
  boss, because the Pi sits just above it.

One dimension worth *choosing* rather than measuring: `uwb_half_base`. It is
set to 125 mm (a 250 mm baseline) to keep the head compact — see
[constraints C1–C2](01-system-overview.md#constraints). Bearing noise scales
as 1/baseline ([04](04-tracking-system.md#geometry)), so if you have the room,
widening it buys accuracy as long as the tripod stays stable and the arms stay
stiff; set `UWB_BASELINE_M` to match. `uwb_v_base` does the same for
elevation; if you change it, cut the dowel to the length `anchor_mast.scad`
echoes and set `UWB_A3_UP_M` to match. Don't go below 250 mm on either.

Prefer remixing community designs instead? See
[Appendix B — Open-source printed-part alternatives](appendix-b-open-source-parts.md).
