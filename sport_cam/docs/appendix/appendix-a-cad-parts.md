# Appendix A — CAD: printed parts

Parametric OpenSCAD sources for every printed part live in <!--both-->each build's<!--/--><!--with_uwb: the build's--><!--without_uwb: the build's-->
`cad/` folder — <!--with_uwb-->[`with_uwb/cad/`](../../with_uwb/cad/)<!--/--><!--both--> and<!--/--> <!--without_uwb-->[`without_uwb/cad/`](../../without_uwb/cad/)<!--/-->. Inputs:

| What | Where | Who edits it |
| --- | --- | --- |
| Sizes of the parts you buy — Pi, buck, PD trigger, switch, power bank, Arducam base, ULA1s … | [`cad/ordered_parts.toml`](../../cad/ordered_parts.toml), shared by both builds | you, as parts arrive |
| Design choices — wall thickness, clearances, window height, anchor baseline … | `<build>/cad/config.scad` | you, rarely |
| The layout — enclosure size, where each board sits, which way the Pi faces, where the wall openings go | `<build>/cad/layout.scad` | **generated** by `cad/fit.py` |

Compiled STLs: `<build>/cad/stl/` (committed). Previews and download links:
BOM printed-parts table
([with UWB](../with_uwb/setup/10-bill-of-materials.md#printed-parts),
[without UWB](../without_uwb/setup/10-bill-of-materials.md#printed-parts)).

All motion comes from the bought PTZ assembly; every printed part is an
enclosure, shelf or bracket.

## Fit the layout to your parts

```bash
cd sport_cam
python3 cad/fit.py            # solve, regenerate, render, audit — both builds
```

`fit.py` reads the part sizes and design parameters, then:

1. **Solves the layout.**
   - Power drum under the floor: the bank's pocket across it, as far forward
     as the outline allows with the tripod axis under the bank; the buck and
     the power latch on edge against the pocket's walls (whichever walls they
     fit); the PD trigger on the floor nearest a finger window; the switch in
     the wall; three or four posts for the screws up into the enclosure,
     spread round the axis<!--with_uwb-->; the opening clear of the arm bosses<!--/-->.
   - Enclosure: shelf posts clear of the drum's screws (with a screwdriver's
     way down to each) and its wire hole; LED ring under the shelf, within the
     LED window band, just above the floor; Pi on the shelf.
   - Search space: the pocket's offset and which walls the boards stand on,
     the trigger's place, the switch's angle, Pi orientation and position,
     post positions. Objective: minimum height.
2. **Falls back when parts don't fit**, in order:
   - taller enclosure;
   - wider enclosure and drum, 2 mm steps, up to the A1 Mini limit;<!--with_uwb-->
   - with UWB: anchor boards turned across the arms if the extension socket
     doesn't fit along them;<!--/-->
   - lid slots stretched to the measured standoff spacing, and the lid's
     cable slot moved clear of them.

   No solution: reports the part and the violated constraint.
3. **Writes** `<build>/cad/layout.scad` (and `layout.json`, and the 3D
   guide's `layout.js`), and keeps the geometry constants in
   `src/<build>/device/sportcam/config.py` (<!--with_uwb-->`UWB_BASELINE_M`, `UWB_A3_BACK_M`,
   `UWB_A3_UP_M`, `LENS_ABOVE_ANCHORS_M`, <!--/-->`LED_COUNT`) in step.
4. **Renders** every STL through `<build>/cad/render_all.sh`, and refreshes
   the guide's meshes and preview images if `numpy-stl` and `matplotlib` are
   installed.
5. **Audits** both builds and writes [`cad/FIT_REPORT.md`](../../cad/FIT_REPORT.md).
   The audit checks:
   - every bought part, as a 3D envelope, is inside the enclosure and below
     the lid, or inside the drum and below the enclosure floor;
   - no two parts overlap, and none hits a post, a pocket wall, a drum screw,
     the shelf, the lid's ring or the screw heads under the lid;
   - nothing on the enclosure floor stands in front of the LED window;
   - the switch is clear of the bank's opening, its ring can clamp it to the wall, and its key flat fits its hole;
   - every board's screws land where they can be driven, and the bolts are long enough;
   - the bank's pocket fits the drum, its catch flexes within PETG's limit, its cable reaches the trigger, and the tripod nut fits the plate;
   - the pod and the dowel come out of their stock;
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
- Claude Code's Stop hook (`tools/claude-check.sh`, see
  [Appendix C](appendix-c-development.md#automated-checks)) runs `--check
  --deep` whenever a session changes the CAD, a part size or a device config.

Requires Python 3.11+ and, for rendering, OpenSCAD. Inside the project's
Docker workspace (`compose.yaml`) both are pre-installed.

## Common parts

In both builds' `cad/`. Print settings for each are in
[11 — 3D printing](../setup/11-3d-printing.md#the-common-parts):

| File | Part |
| --- | --- |
| `base_housing.scad` | Enclosure: three shelf posts merged into the wall, the LED window all the way round with a ledge below it for the diffuser band, vents above the shelf, four radial lid-screw holes; in the floor, countersunk holes for the power drum's screws and a hole for the leads up from it. The wall differs by build — see below |
| `shelf.scad` | Pi shelf: rests on the posts (3 × M3 × 8 into inserts), Pi holes for M2.5 nylon standoffs, a cut-away side for the cables, a centre mark for the LED ring underneath |
| `lid.scad` | Top plate carrying the Arducam pan-tilt base; slotted pattern for the base's standoffs, a cable slot at the back, a locating ring underneath with four radial M3 inserts |
| `led_diffuser_ring.scad` | Translucent band that slides over the outside of the LED window |
| `power_drum.scad` | Power drum, the enclosure's diameter, screwed under its floor: the bank's pocket across it, open at one side, with finger windows either side of the opening; countersunk holes through the pocket walls for the buck and latch standing on edge against them; the PD trigger's floor holes and rest; the round switch hole keyed to the flat on its thread, with a flat seat outside for its bezel and a flat boss inside for its ring; vents by the buck; posts with M3 inserts for the screws down through the enclosure floor; the tripod screw's hole<!--with_uwb-->; with UWB, the three bosses the arms and mast foot bolt to<!--/--> |
| `bank_plate.scad` | The bank pocket's drop-in floor: the tripod's 3/8-16 nut in a hex hole through it, a sprung crossbar with a catch at its front edge, two M3 inserts underneath for the screws up through the drum floor |

## Before printing — measure these

Measure every part as it arrives, put the numbers in
[`cad/ordered_parts.toml`](../../cad/ordered_parts.toml), change each value's
`MEASURE_TODO` to `MEASURE_DONE`, and re-run `fit.py`. Which sizes matter, and what each one changes,
is the first table of your build's 15 — Verification checklist
([with UWB](../with_uwb/setup/15-verification.md#before-you-print),
[without UWB](../without_uwb/setup/15-verification.md#before-you-print)).

Prefer remixing community designs instead? See
[Appendix B — Open-source printed-part alternatives](appendix-b-open-source-parts.md).

---

## With UWB

`with_uwb/cad/power_drum.scad` adds **three wall bosses** — anchor arms at
±Y, the A3 mast at −X — run down to the bed so they print without support.
`with_uwb/cad/base_housing.scad` adds a **slot high in the wall** behind the
Pi's USB ports, where the three anchor cables come in. Three more files:

| File | Part |
| --- | --- |
| `anchor_arm.scad` | Static UWB anchor arm (×2); bolts to the M3 inserts in the drum's ±Y bosses. The board pad runs along or across the arm, whichever way `fit.py` turned the ULA1s |
| `anchor_mast.scad` | A3 mast: `part="foot"` bolts to the drum's −X boss and holds a ½" dowel; `part="cradle"` caps it and carries the board. Echoes the dowel cut length (246 mm with the defaults) |
| `wearable_case.scad` | Wearable pod body + lid, strap bars, USB-C slot; sized by `fit.py` for the ULA1 plugged straight into the end of its bank |

One dimension worth *choosing* rather than measuring: `uwb_half_base`. It is
set to 190 mm, which puts the antennas 400 mm apart (each sits 10 mm
further out than the board's centre) — see
[constraints C1–C2](../product/01-requirements.md#non-functional-requirements). Bearing noise
scales as 1/baseline
([05](../with_uwb/design/05-tracking-system.md#geometry)), so if you have the
room, widening it buys accuracy as long as the tripod stays stable and the
arms stay stiff; `fit.py` sets `UWB_BASELINE_M` to match. `uwb_v_base` does
the same for elevation; if you change it, cut the dowel to the length
`anchor_mast.scad` echoes (`fit.py` keeps `UWB_A3_UP_M` in step). Don't go
below 250 mm on either.

---

## Without UWB

The camera-only variant: just the five common parts, and
`without_uwb/cad/base_housing.scad` has a **plain wall all round** — no
bosses, no cable slot, no supports.
