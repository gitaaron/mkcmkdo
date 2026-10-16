# Appendix A — CAD: printed parts

Parametric OpenSCAD sources for every printed part live in each build's
`cad/` folder — [`with_uwb/cad/`](../with_uwb/cad/) and
[`without_uwb/cad/`](../without_uwb/cad/). Every dimension is in that build's
**`cad/config.scad`** (enclosure size, board hole patterns, battery size,
clearances — and, with UWB, the anchor baseline) — change it there,
re-render, and all parts stay consistent. Compiled STLs are committed in
`<build>/cad/stl/`; per-part previews and download links are in the build's
BOM printed-parts table
([with UWB](../with_uwb/docs/07-bill-of-materials.md#printed-parts),
[without UWB](../without_uwb/docs/07-bill-of-materials.md#printed-parts)).

This is the **PTZ-base build**: the camera, both motion axes and the zoom lens
are one bought assembly, so everything printed here is an enclosure or a
bracket. The pan stage parts (ring pulley, rotating platform, tilt towers,
camera cradle) were deleted along with the stepper.

## Render

Run from the repo root, with `<build>` = `with_uwb` or `without_uwb`:

```bash
./<build>/cad/render_all.sh              # requires openscad; STLs land in <build>/cad/stl/
python3 <build>/cad/render_previews.py   # preview PNGs → <build>/docs/images/parts/
# or one part:
openscad -o <build>/cad/stl/lid.stl <build>/cad/lid.scad
```

After any change, also refresh that build's assembly guide meshes:

```bash
python3 <build>/docs/setup/assembly/build_models.py
python3 <build>/docs/setup/assembly/render_steps.py
```

Inside the project's Docker workspace (see `compose.yaml` at the repo root)
OpenSCAD and the Python libraries are pre-installed.

## Print settings, materials and printer requirements

Per-part settings are summarised below, but the full treatment — printer
requirements, filament to buy, orientation, where support is needed, print
times and the PETG-on-PEI trap — is in
**[3D printing specifications](3d_printer/specifications.md)**.

## Common parts

In both builds' `cad/`:

| File | Part | Print settings |
| --- | --- | --- |
| `base_housing.scad` | Enclosure (Ø 135 × 66): Pi standoffs, LED window, 5 V jack, vents, tripod boss for a 3/8-16 insert. The wall differs by build — see below | PETG, 4 walls, 20 % |
| `lid.scad` | Top plate carrying the Arducam pan-tilt base; slotted bolt pattern, central cable opening | PETG, **5 walls, 40 %** — this part holds the camera up |
| `led_diffuser_ring.scad` | Translucent band closing the LED window | white/natural PETG, 2 walls, 0 % infill |
| `battery_tray.scad` | Saddle for the USB-C power bank, strap slots + 1/4-20 bore | PETG, 3 walls, 20 % |

## Before printing — measure these

The same list lives in your build's 10 — Verification checklist
([with UWB](../with_uwb/docs/10-verification.md#before-you-print),
[without UWB](../without_uwb/docs/10-verification.md#before-you-print)),
together with the on-arrival and bench checks.

Dimensions in `config.scad` marked `MEASURE YOURS`, because vendors vary —
in both builds:

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

---

## With UWB

`with_uwb/cad/base_housing.scad` adds **three wall bosses** — anchor arms at
±Y, the A3 mast at −X — and needs support only under them. Three more files:

| File | Part | Print settings |
| --- | --- | --- |
| `anchor_arm.scad` | Static UWB anchor arm (×2); bolts to the M3 inserts in the ±Y bosses | print flat, 4+ walls |
| `anchor_mast.scad` | A3 mast: `part="foot"` bolts to the −X boss and holds a ½" dowel; `part="cradle"` caps it and carries the board. Echoes the dowel cut length (246 mm) | socket up, 4+ walls; one M3 insert per socket |
| `wearable_case.scad` | Wearable pod body + lid, strap bars, USB-C slot | PETG, 2 walls; TPU also works nicely |

More to measure:

- `uwb_l/uwb_w/uwb_hole_*` — the ULA1's outline and hole pattern. The manual
  gives 40 × 25 mm but not the mounting holes.
- `mast_d` — your dowel. "½-inch" dowels run a few tenths either side of
  12.7 mm; the sockets add `clr` on top, and the pinch screws take up the
  rest.

One dimension worth *choosing* rather than measuring: `uwb_half_base`. It is
set to 125 mm (a 250 mm baseline) to keep the head compact — see
[constraints C1–C2](01-system-overview.md#constraints-with-uwb). Bearing noise
scales as 1/baseline
([04](../with_uwb/docs/04-tracking-system.md#geometry)), so if you have the
room, widening it buys accuracy as long as the tripod stays stable and the
arms stay stiff; set `UWB_BASELINE_M` to match. `uwb_v_base` does the same for
elevation; if you change it, cut the dowel to the length `anchor_mast.scad`
echoes and set `UWB_A3_UP_M` to match. Don't go below 250 mm on either.

---

## Without UWB

The camera-only variant: just the four common parts, and
`without_uwb/cad/base_housing.scad` has a **plain wall all round** — no
bosses, no supports. Nothing more to measure than the common list.
