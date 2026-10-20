# Appendix A — CAD: printed parts

Parametric OpenSCAD sources for every printed part live in each build's
`cad/` folder — [`with_uwb/cad/`](../../with_uwb/cad/) and
[`without_uwb/cad/`](../../without_uwb/cad/). Three kinds of number feed them:

| What | Where | Who edits it |
| --- | --- | --- |
| Sizes of the parts you buy — Pi, buck, PD trigger, switch, power bank, Arducam base, ULA1s … | [`cad/ordered_parts.toml`](../../cad/ordered_parts.toml), shared by both builds | you, as parts arrive |
| Design choices — wall thickness, clearances, window height, anchor baseline … | `<build>/cad/config.scad` | you, rarely |
| The layout — enclosure size, where each board sits, which way the Pi faces, where the wall openings go | `<build>/cad/layout.scad` | **generated** by `cad/fit.py` |

Compiled STLs are committed in `<build>/cad/stl/`; per-part previews and
download links are in the build's BOM printed-parts table
([with UWB](../../with_uwb/docs/setup/10-bill-of-materials.md#printed-parts),
[without UWB](../../without_uwb/docs/setup/10-bill-of-materials.md#printed-parts)).

This is the **PTZ-base build**: the camera, both motion axes and the zoom lens
are one bought assembly, so everything printed here is an enclosure, a shelf
or a bracket.

## Fit the layout to your parts

```bash
cd sport_cam
python3 cad/fit.py            # solve, regenerate, render, audit — both builds
```

`fit.py` reads the part sizes and the design choices, then:

1. **Solves the layout.** The power boards go on the enclosure floor, clear of
   the tripod boss, the shelf posts and each other, with the PD trigger's
   socket at a USB-C inlet in the wall. The LED ring sits under the shelf, in
   the band of the LED window, and the Pi sits on the shelf. It tries Pi
   orientations and positions, wall positions for the inlet, switch and jack,
   and post positions, and keeps the arrangement that needs the lowest
   enclosure.
2. **Finds another design if the parts don't fit.** If a board is too big to
   go round the tripod boss, it raises the boards on printed risers over it.
   Then it makes the enclosure taller, and then wider in 2 mm steps up to what
   an A1 Mini can print. With UWB, it turns the anchor boards across the arms
   if the extension cable's socket end has no room along them. It stretches
   the lid's slots to the base's measured bolt spacing. If nothing works, it
   names the part and the constraint.
3. **Writes** `<build>/cad/layout.scad` (and `layout.json`, and the 3D
   guide's `layout.js`), and keeps the geometry constants in
   `<build>/device/sportcam/config.py` (`UWB_BASELINE_M`, `UWB_A3_BACK_M`,
   `UWB_A3_UP_M`, `LED_COUNT`) in step.
4. **Renders** every STL through `<build>/cad/render_all.sh`, and refreshes
   the guide's meshes and preview images if `numpy-stl` and `matplotlib` are
   installed.
5. **Audits** both builds and writes [`cad/FIT_REPORT.md`](../../cad/FIT_REPORT.md).
   The audit checks:
   - every bought part, as a 3D envelope, is inside the enclosure and below
     the lid;
   - no two parts overlap, and none hits a post, the boss, the shelf, the
     lid's ring or the nuts under the lid;
   - the power boards sit below the LED window;
   - the wall openings can be reached, and the switch's clips can grip;
   - the bolts are long enough;
   - the tray, the pod and the dowel come out of their stock;
   - each STL is one piece no bigger than 170 mm on any side.
   It also lists every part size that is still assumed rather than measured.

| Command | What it does |
| --- | --- |
| `python3 cad/fit.py` | the normal run |
| `python3 cad/fit.py --check` | changes nothing; fails if the layout or STLs are stale or anything doesn't fit |
| `python3 cad/fit.py --watch` | re-runs on every save of `ordered_parts.toml` or a `.scad` |
| `python3 cad/fit.py --deep` | also intersects the real meshes with the part envelopes in OpenSCAD |
| `npm run cad:fit` / `cad:check` / `cad:watch` | the same, from `sport_cam/` |

**It runs whenever the CAD or a part size changes:**
- `render_all.sh` hands over to `fit.py`, so rendering by hand still goes
  through the audit.
- A git pre-commit hook (`npm run hooks:install`, once per clone) runs
  `--check` on any commit that touches `cad/`, a build's `cad/` or a device
  config.
- CI (`.github/workflows/sportcam-cad-fit.yml`) runs `--check --deep` on
  pushes and pull requests.

Requires Python 3.11+ and, for rendering, OpenSCAD. Inside the project's
Docker workspace (`compose.yaml`) both are pre-installed.

## Print settings, materials and printer requirements

Per-part settings are summarised below, but the full treatment — printer
requirements, filament to buy, orientation, where support is needed, print
times and the PETG-on-PEI trap — is in
**[3D printing specifications](../setup/11-3d-printing.md)**.

## Common parts

In both builds' `cad/`:

| File | Part | Print settings |
| --- | --- | --- |
| `base_housing.scad` | Enclosure: three shelf posts merged into the wall, the LED window all the way round with a ledge below it for the diffuser band, USB-C inlet, switch cut-out (wall thinned for its clips), 5 V jack hole, low and high vents, four radial lid-screw holes, tripod boss for a 3/8-16 insert, risers when needed. The wall differs by build — see below | PETG, 4 walls, 20 % |
| `shelf.scad` | Pi shelf: rests on the posts (3 × M3 × 8 into inserts), Pi holes for M2.5 nylon standoffs, a cut-away side for the cables, a centre mark for the LED ring underneath | PETG, 3 walls, 20 %; white or natural helps the light |
| `lid.scad` | Top plate carrying the Arducam pan-tilt base; slotted bolt pattern, central cable opening, a locating ring underneath with four radial M3 inserts | PETG, **5 walls, 40 %** — this part holds the camera up |
| `led_diffuser_ring.scad` | Translucent band that slides over the outside of the LED window | white/natural PETG, 2 walls, 0 % infill |
| `battery_tray.scad` | Saddle for the USB-C power bank, strap slots | PETG, 3 walls, 20 % |

## Before printing — measure these

The same list lives in your build's 15 — Verification checklist
([with UWB](../../with_uwb/docs/setup/15-verification.md#before-you-print),
[without UWB](../../without_uwb/docs/setup/15-verification.md#before-you-print)),
together with the on-arrival and bench checks.

Measure every part as it arrives and put the numbers in
[`cad/ordered_parts.toml`](../../cad/ordered_parts.toml), setting
`measured = true` on each; `fit.py` re-solves around them. The ones that move
the design most, in both builds:

- **`[ptz] bolt_spacing` — the important one.** Arducam publishes no drawing
  for the B0167B12 metal base and the footprint has changed between
  revisions. The lid is cut with radial slots, 30–72 mm by default, stretched
  to your spacing if it is outside that. Bolt it down with M3 and nuts; set
  `bolt_l` to the screws you have, and the lid is relieved under the slots if
  they are short.
- **`[buck]`, `[gauge]`, `[pd_trigger]`** — power modules of the same rating
  vary a lot. A bigger buck can push the boards onto risers or make the
  enclosure wider.
- **`[power_bank]`** — the tray is a pocket sized to it. Banks of the same
  capacity vary by 15 mm in every direction.
- **`[tripod_insert] od / l`** — the floor bore is cut to the insert's outside
  diameter for an epoxied slip fit, and it must be no longer than the 8 mm
  boss.
- **`[pi] heatsink_h`** — a fan case is taller than stick-on heatsinks and
  makes the enclosure taller.

Prefer remixing community designs instead? See
[Appendix B — Open-source printed-part alternatives](appendix-b-open-source-parts.md).

---

## With UWB

`with_uwb/cad/base_housing.scad` adds **three wall bosses** — anchor arms at
±Y, the A3 mast at −X — and needs support only under them. It also adds a
**slot high in the wall** behind the Pi's USB ports, where the three anchor
cables come in. Three more files:

| File | Part | Print settings |
| --- | --- | --- |
| `anchor_arm.scad` | Static UWB anchor arm (×2); bolts to the M3 inserts in the ±Y bosses. The board pad runs along or across the arm, whichever way `fit.py` turned the ULA1s | print flat, 4+ walls |
| `anchor_mast.scad` | A3 mast: `part="foot"` bolts to the −X boss and holds a ½" dowel; `part="cradle"` caps it and carries the board. Echoes the dowel cut length (246 mm with the defaults) | socket up, 4+ walls; one M3 insert per socket |
| `wearable_case.scad` | Wearable pod body + lid, strap bars, USB-C slot; sized by `fit.py` for the ULA1 plugged straight into the end of its bank | PETG, 2 walls; TPU also works nicely |

More to measure, in `cad/ordered_parts.toml`:

- `[ula1]` — the ULA1's outline, hole pattern and how far its USB plug
  sticks out. The manual gives 40 × 25 mm but not the mounting holes.
- `[usb_extension]` — the rigid socket end of your extension cables, and the
  plug end. These decide whether the anchor boards can lie along the arms.
  With the assumed sizes they can't, so they lie across them. They also set
  the size of the cable slot.
- `[dowel] d` — "½-inch" dowels run a few tenths either side of 12.7 mm; the
  sockets add `clr` on top, and the pinch screws take up the rest.
- `[tag_bank]` — the wearable's bank. The pod is sized to it plus the ULA1
  plugged into its end.

One dimension worth *choosing* rather than measuring: `uwb_half_base`. It is
set to 125 mm (a 250 mm baseline) to keep the head compact — see
[constraints C1–C2](../product/01-requirements.md#non-functional-requirements-with-uwb). Bearing noise
scales as 1/baseline
([05](../../with_uwb/docs/design/05-tracking-system.md#geometry)), so if you have the
room, widening it buys accuracy as long as the tripod stays stable and the
arms stay stiff; `fit.py` sets `UWB_BASELINE_M` to match. `uwb_v_base` does
the same for elevation; if you change it, cut the dowel to the length
`anchor_mast.scad` echoes (`fit.py` keeps `UWB_A3_UP_M` in step). Don't go
below 250 mm on either.

---

## Without UWB

The camera-only variant: just the five common parts, and
`without_uwb/cad/base_housing.scad` has a **plain wall all round** — no
bosses, no cable slot, no supports. Nothing more to measure than the common
list.
