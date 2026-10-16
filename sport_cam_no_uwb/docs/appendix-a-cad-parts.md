# Appendix A — CAD: printed parts

Parametric OpenSCAD sources for every printed part live in
[`cad/`](../cad/). Every dimension is in **[`cad/config.scad`](../cad/config.scad)**
(enclosure size, board hole patterns, battery size,
clearances) — change it there, re-render, and all parts stay consistent.
Compiled STLs are committed in [`cad/stl/`](../cad/stl/); per-part previews and
download links are in the [BOM's printed-parts table](07-bill-of-materials.md#printed-parts).

This is the **PTZ-base build**: the camera, both motion axes and the zoom lens
are one bought assembly, so everything printed here is an enclosure or a
bracket. This is the camera-only variant: four parts, with a plain enclosure wall.

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
| `base_housing.scad` | Enclosure (Ø 135 × 66): Pi standoffs, LED window, 5 V jack, vents, plain wall all round, tripod boss for a 3/8-16 insert | PETG, 4 walls, 20 %; no supports |
| `lid.scad` | Top plate carrying the Arducam pan-tilt base; slotted bolt pattern, central cable opening | PETG, **5 walls, 40 %** — this part holds the camera up |
| `led_diffuser_ring.scad` | Translucent band closing the LED window | white/natural PETG, 2 walls, 0 % infill |
| `battery_tray.scad` | Saddle for the USB-C power bank, strap slots + 1/4-20 bore | PETG, 3 walls, 20 % |

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
- `tripod_hole_d` — the bore for the 3/8-16 brass insert, modelled at
  12.7 mm. Epoxied, so aim for a snug slip fit; open it up rather than
  reprint if yours is larger. The insert must be no longer than the 8 mm
  boss, because the Pi sits just above it.

Prefer remixing community designs instead? See
[Appendix B — Open-source printed-part alternatives](appendix-b-open-source-parts.md).
