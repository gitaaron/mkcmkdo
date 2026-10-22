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
([with UWB](../../with_uwb/docs/setup/10-bill-of-materials.md#printed-parts),
[without UWB](../../without_uwb/docs/setup/10-bill-of-materials.md#printed-parts)).

All motion comes from the bought PTZ assembly; every printed part is an
enclosure, shelf or bracket.

## Fit the layout to your parts

```bash
cd sport_cam
python3 cad/fit.py            # solve, regenerate, render, audit — both builds
```

`fit.py` reads the part sizes and design parameters, then:

1. **Solves the layout.**
   - Floor: power boards clear of the tripod boss, shelf posts and each
     other; PD trigger socket at the wall USB-C inlet.
   - LED ring under the shelf, within the LED window band; Pi on the shelf.
   - Search space: Pi orientation and position, wall positions of inlet,
     switch and jack, post positions. Objective: minimum enclosure height.
2. **Falls back when parts don't fit**, in order:
   - boards raised on printed risers over the tripod boss;
   - taller enclosure;
   - wider enclosure, 2 mm steps, up to the A1 Mini limit;<!--with_uwb-->
   - with UWB: anchor boards turned across the arms if the extension socket
     doesn't fit along them;<!--/-->
   - lid slots stretched to the measured bolt spacing.

   No solution: reports the part and the violated constraint.
3. **Writes** `<build>/cad/layout.scad` (and `layout.json`, and the 3D
   guide's `layout.js`), and keeps the geometry constants in
   `src/<build>/device/sportcam/config.py` (<!--with_uwb-->`UWB_BASELINE_M`, `UWB_A3_BACK_M`,
   `UWB_A3_UP_M`, <!--/-->`LED_COUNT`) in step.
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
| `base_housing.scad` | Enclosure: three shelf posts merged into the wall, the LED window all the way round with a ledge below it for the diffuser band, USB-C inlet, switch cut-out (wall thinned for its clips), 5 V jack hole, low and high vents, four radial lid-screw holes, tripod boss for a 3/8-16 insert, risers when needed. The wall differs by build — see below |
| `shelf.scad` | Pi shelf: rests on the posts (3 × M3 × 8 into inserts), Pi holes for M2.5 nylon standoffs, a cut-away side for the cables, a centre mark for the LED ring underneath |
| `lid.scad` | Top plate carrying the Arducam pan-tilt base; slotted bolt pattern, central cable opening, a locating ring underneath with four radial M3 inserts |
| `led_diffuser_ring.scad` | Translucent band that slides over the outside of the LED window |
| `battery_tray.scad` | Saddle for the USB-C power bank, strap slots |

## Before printing — measure these

Measure every part as it arrives, put the numbers in
[`cad/ordered_parts.toml`](../../cad/ordered_parts.toml) with `measured = true`
on each, and re-run `fit.py`. Which sizes matter, and what each one changes,
is the first table of your build's 15 — Verification checklist
([with UWB](../../with_uwb/docs/setup/15-verification.md#before-you-print),
[without UWB](../../without_uwb/docs/setup/15-verification.md#before-you-print)).

Prefer remixing community designs instead? See
[Appendix B — Open-source printed-part alternatives](appendix-b-open-source-parts.md).

---

## With UWB

`with_uwb/cad/base_housing.scad` adds **three wall bosses** — anchor arms at
±Y, the A3 mast at −X — and needs support only under them. It also adds a
**slot high in the wall** behind the Pi's USB ports, where the three anchor
cables come in. Three more files:

| File | Part |
| --- | --- |
| `anchor_arm.scad` | Static UWB anchor arm (×2); bolts to the M3 inserts in the ±Y bosses. The board pad runs along or across the arm, whichever way `fit.py` turned the ULA1s |
| `anchor_mast.scad` | A3 mast: `part="foot"` bolts to the −X boss and holds a ½" dowel; `part="cradle"` caps it and carries the board. Echoes the dowel cut length (246 mm with the defaults) |
| `wearable_case.scad` | Wearable pod body + lid, strap bars, USB-C slot; sized by `fit.py` for the ULA1 plugged straight into the end of its bank |

One dimension worth *choosing* rather than measuring: `uwb_half_base`. It is
set to 190 mm, which puts the antennas 400 mm apart (each sits 10 mm
further out than the board's centre) — see
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
bosses, no cable slot, no supports.
