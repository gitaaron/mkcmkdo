# 11 — 3D printing: requirements, materials and settings

Printed parts, printer requirements, materials and settings for both builds.
Any stock desktop FDM printer of Ender 3 / Prusa Mini / Bambu A1 class is
sufficient.

| Build | Parts | PETG | Machine time |
| --- | --- | --- | --- |
| [With UWB](#with-uwb) | 11 (6 common + 2 arms, mast foot, mast cradle, wearable pod) | ≈ 570 g | ≈ 55 h |
| [Without UWB](#without-uwb) | 6 (the common parts) | ≈ 500 g | ≈ 46 h |

| Topic | Reference |
| --- | --- |
| Sizes | for the part sizes assumed in [`cad/ordered_parts.toml`](../../cad/ordered_parts.toml). `cad/fit.py` resizes the enclosure, power drum, shelf, lid and diffuser to measured parts; current figures in [`cad/FIT_REPORT.md`](../../cad/FIT_REPORT.md) |
| Sources | `<build>/cad/` ([with UWB](../../with_uwb/cad/), [without UWB](../../without_uwb/cad/)); STL workflow in [Appendix A](../appendix/appendix-a-cad-parts.md) |
| Part roles | [03 — Mechanical design](../design/03-mechanical-design.md) |
| Croc charms (separate project, same printer) | [Croc charms](#croc-charms-jibbitz), [One printer for both](#one-printer-for-both) |

## Printer requirements

| Requirement | Minimum | Why |
| --- | --- | --- |
| Technology | FDM / FFF | all parts are designed for it |
| Build volume | **170 × 170 × 60 mm** | the with-UWB power drum is 166 × 170 mm across its arm bosses and 55 mm tall; the enclosures are Ø 162 (166 over the diffuser band's ledge) and 54 mm tall |
| Nozzle | 0.4 mm | every setting below assumes it. 0.6 works if you raise wall counts |
| Hotend temperature | **250 °C** | PETG |
| Heated bed | **80 °C** | PETG will not stay down without one |
| Part cooling fan | yes, controllable | PETG wants it at 30–50 %, not 100 % |
| Enclosure | not needed | PETG does not warp like ABS |
| Extruder | either | bowden is fine. Direct drive only matters for the optional TPU wearable pod (UWB build) |

### Design rule: every part prints on a Bambu Lab A1 Mini

Reference printer: **Bambu Lab A1 Mini** (180 × 180 × 180 mm). **Every
printed part in both builds must fit on it in one piece** (requirement C5).

| Rule | Detail |
| --- | --- |
| **≤ 170 mm on every axis** | 180 mm bed minus 5 mm per side for brim/skirt. Cubic volume: any orientation fits |
| **No split parts** | redesign instead; a glued seam in the enclosure or lid is a structural weak point |
| **Automated check** | `python3 cad/fit.py` measures every STL in both builds; fails on oversize or multi-piece parts. Caps the diameter (162 mm with UWB, where the arm bosses on the power drum add 8 mm). Runs on every render, on CAD commits, and when a Claude Code session ends with CAD changes ([Appendix A](../appendix/appendix-a-cad-parts.md#fit-the-layout-to-your-parts)) |

Sizes with the assumed parts (bounding box, mm):

| Part | Build | Size | Margin to 170 |
| --- | --- | --- | --- |
| Enclosure | both | 166 × 166 × 54 (Ø 162, and the band's ledge) | 4 |
| Power drum | with UWB | 166 × 170 × 55 (the arm bosses) | 0 |
| Power drum | without UWB | 162 × 162 × 55 | 8 |
| Bank plate | both | 127 × 76 × 12 | 43 |
| Pi shelf | <!--both-->with UWB / without<!--/--><!--with_uwb: with UWB--><!--without_uwb: without UWB--> | <!--with_uwb-->154 × 123 × 3<!--/--><!--both--> / <!--/--><!--without_uwb-->154 × 107 × 3<!--/--> | 16 |
| Lid | both | 162 × 162 × 11 | 8 |
| LED diffuser band | both | Ø 166 × 16 | 4 |
| Wearable pod | with UWB | 142 × 74 × 31 | 28 |
| Anchor arm | with UWB | 142 × 28 × 24 | 28 |
| Mast foot, mast cradle | with UWB | ≤ 69 mm | 100+ |

- **Build volume is the only hard requirement:** 170 × 170 mm clears every
  part at the assumed sizes, the A1 Mini's 180 × 180 with a brim. The
  with-UWB drum fills it: `cad/fit.py` won't let the diameter grow past
  162 mm there.
- Resin printers are unsuitable (structural parts).

## What to buy

| Material | Qty | Notes |
| --- | --- | --- |
| **PETG, 1 kg, any colour** | 1 spool | the structural parts: ≈ <!--with_uwb-->525 g<!--/--><!--both--> with UWB, ≈ <!--/--><!--without_uwb-->455 g<!--/--><!--both--> without<!--/-->. A 1 kg spool leaves enough for a reprint of the big parts |
| **PETG, white or natural** | ≈ 40 g | the LED diffuser band, which has to pass light, and ideally the shelf, whose underside bounces the ring's light out. They can't be your main colour unless that colour is white or natural. A 250 g sample spool is the cheap way to get it |
| Glue stick (PVA) | 1 | see the warning below — this is a release agent, not an adhesive |
| TPU 95A *(optional, UWB build)* | ≈ 30 g | nicer wearable pod against the skin. Needs direct drive |

> **Warning — PETG on smooth PEI:** PETG can fuse to a bare smooth PEI sheet
> and tear the surface on removal. Apply a thin layer of glue stick as a
> **release agent**. Textured PEI, garolite, and glass with glue are safe.

Material choice:

| Material | Suitability |
| --- | --- |
| **PETG** | specified |
| PLA | not recommended: creeps under sustained load, softens at ≈ 60 °C (lid cantilevers the camera; tripods get left in hot cars) |
| ABS / ASA | acceptable with an enclosed printer |

## The common parts

Every build prints these six; their sizes are in the
[table above](#design-rule-every-part-prints-on-a-bambu-lab-a1-mini).<!--both--> Links go to the UWB build's sources; the
camera-only build has the same files in `without_uwb/cad/`. Masses and times
are the with-UWB ones (camera-only in brackets where they differ).<!--/-->

| Part | Walls | Infill | Layer | Est. mass | Est. time |
| --- | --- | --- | --- | --- | --- |
| [Enclosure](../../with_uwb/cad/base_housing.scad) | 4 | 20 % | 0.2 | ≈ 140 g | ≈ 14 h |
| [Power drum](../../with_uwb/cad/power_drum.scad) | 4 | 25 % | 0.2 | <!--with_uwb-->≈ 190 g<!--/--><!--both--> (<!--/--><!--without_uwb: ≈ --><!--without_uwb-->180 g<!--/--><!--both-->)<!--/--> | <!--with_uwb-->≈ 19 h<!--/--><!--both--> (<!--/--><!--without_uwb: ≈ --><!--without_uwb-->18 h<!--/--><!--both-->)<!--/--> |
| [Bank plate](../../with_uwb/cad/bank_plate.scad) | 3 | 40 % | 0.2 | ≈ 50 g | ≈ 4 h |
| [Pi shelf](../../with_uwb/cad/shelf.scad) | 3 | 20 % | 0.2 | ≈ 39 g | ≈ 3 h |
| [Lid](../../with_uwb/cad/lid.scad) | **5** | **40 %** | 0.2 | ≈ 80 g | ≈ 5 h |
| [LED diffuser band](../../with_uwb/cad/led_diffuser_ring.scad) | **2** | **0 %** | 0.2 | ≈ 7 g | ≈ 1.5 h |

Differences by build: <!--with_uwb-->the UWB enclosure has a slot for the anchor cables, and the UWB
drum three bosses for the arms and mast<!--/--><!--both-->; the camera-only ones are plain all round<!--/--><!--without_uwb: the camera-only enclosure and drum are plain all round-->.

Estimates: mass from STL volume at 1.27 g/cm³ (PETG), scaled for walls and
infill; time for a 0.4 mm nozzle at 0.2 mm layers, default speeds. **The
slicer's figures take precedence.**

### Orientation and supports

Every part is modelled in print orientation. Printed as exported from
OpenSCAD, **no supports are needed**.

| Part | Orientation | Supports |
| --- | --- | --- |
| Enclosure | open end up, as modelled | none. The LED window is cut in bays with a thin rib every 22 mm, so the wall above it bridges short spans; the ledge under the window has a 45° underside; the shelf posts grow straight up out of the wall |
| Power drum | floor down, open top up, as modelled | none. The bank's opening and the finger windows are cut to the top of the wall, so nothing bridges over them; the switch hole and vents are small<!--with_uwb-->; the arm bosses run down to the bed<!--/--> |
| Bank plate | flat, underside down, as modelled | none: the only bridge is the 50 mm crossbar at its front edge, thinned underneath so the catch on it flexes; PETG bridges it cleanly at default bridge settings |
| Pi shelf | flat, as modelled | none |
| Lid | **flip it: top face on the bed**, locating ring up | none |
| Diffuser band | standing, as modelled | none. **Brim recommended**: it is a tall thin ring with a small footprint |

### Why the lid is different

The only part with raised settings (5 walls, 40 % infill). It carries the
Arducam base, camera, lens and both servos on four M3 bolts. Lower settings
allow flex under pan acceleration, visible as wobble in the footage.

### Why the diffuser is different

Must be as hollow as possible to diffuse 16 point sources into an even band:
2 walls, 0 % infill, **0 top and bottom layers** (set explicitly if the slicer
adds them). Denser prints show 16 distinct dots.

## Settings that are not per-part

| Setting | Value | Note |
| --- | --- | --- |
| Nozzle | 235–245 °C | start at 240 and tune down until stringing stops |
| Bed | 80 °C | 70 also works on textured sheets |
| First layer | +0.02 to 0.05 mm higher than PLA | squashing PETG makes it stick too hard and look rough |
| Part cooling | 30–50 % | full cooling makes PETG brittle and weakens layer bonding |
| Retraction | 4–6 mm bowden / 1–2 mm direct | PETG strings; dry filament matters more than retraction tuning |
| Flow | ~95 % | PETG tends to over-extrude at default flow |

Dry filament that has been open more than a few weeks. Wet PETG is the most
common cause of stringing and weak parts; strings are most visible on the lit
diffuser.

## After printing

| Step | Tool | Where |
| --- | --- | --- |
| Remove brims, clean up strings | flush cutters, deburring tool | all parts |
| Open every M3 clearance hole | 3.2 mm drill bit, by hand | enclosure lid-screw holes, shelf, lid slots<!--with_uwb--> (and, with UWB, arms and mast foot)<!--/--> |
| Check the 3/8-16 tripod nut drops into its hex hole | a file on the nut's flats if it is tight | bank plate |
| Fit heat-set inserts | soldering iron, flat tip, ≈ 200 °C | M3: one in the top of each of the three shelf posts, four pushed sideways into the lid's ring, one in the top of each of the power drum's posts (3 or 4, as `fit.py` placed them), and two in the underside of the bank plate (12–13 total) |
| Dry-fit before wiring | — | lid ring in the enclosure mouth; shelf on its posts; diffuser band over the window onto its ledge; the bank plate in the drum's pocket and the bank slid in over it until the catch clicks; the enclosure on the drum |

The 3/8-16 tripod nut is epoxied into the bank plate, not heat-set.<!--with_uwb--> Additional UWB inserts:
[below](#with-uwb).<!--/-->

## Measure before you print

Before printing (lid ≈ 5 h, enclosure ≈ 14 h, drum ≈ 18 h): measure the bought parts,
enter the values in [`cad/ordered_parts.toml`](../../cad/ordered_parts.toml),
run `python3 cad/fit.py` (re-solves the layout, re-renders, checks fit). What
to measure: first table of **15 — Verification checklist**
([with UWB](../with_uwb/setup/15-verification.md#before-you-print),
[without UWB](../without_uwb/setup/15-verification.md#before-you-print)).

## Print order

For building in parallel with printing:

| # | Part | Reason |
| --- | --- | --- |
| 1 | **Power drum** | longest print, and the power parts go in first; measure the bank, buck, latch and switch before printing it |
| 2 | **Bank plate** | the tripod nut is epoxied into it and needs a day to cure |
| 3 | **Enclosure** | the drum screws up under it |
| 4 | **Shelf** | carries the LED ring and the Pi |
| 5 | **Lid** | needed when the Arducam base arrives |
| 6 | **Diffuser band** | needed after the LED ring is fitted |

<!--with_uwb-->

UWB build: anchor arms and pod order in [Print order, with UWB](#print-order-with-uwb).

<!--/-->

## Printing from the command line

With an A1 Mini on your network, [`cad/printer.py`](../../cad/printer.py)
slices a part with the settings above, sends it to the printer and follows the
print:

```bash
python3 cad/printer.py --list                  # the parts and their settings
python3 cad/printer.py lid                     # slice, upload, start, follow
python3 cad/printer.py anchor_arm --copies 2   # both arms on one plate (with UWB)
python3 cad/printer.py lid --slice-only        # just slice; open the .3mf in Bambu Studio to check
python3 cad/printer.py --status                # what the printer is doing
```

| Needs | Detail |
| --- | --- |
| Bambu Studio | installed on the same computer; its command line does the slicing, with its own A1 mini, 0.20 mm and PETG profiles plus the per-part settings in the tables above (the lid is flipped onto its top face automatically) |
| Printer | an SD card in it; on its screen, Settings → Network: **LAN Only Mode** on and, on current firmware, **Developer Mode** on (without it the printer ignores commands from anything but Bambu's apps) |
| Its details | IP address, serial number (Settings → Device) and access code (Settings → Network), plus which build you are printing, in `~/.config/sportcam/printer.toml` — outside the repo, as the access code is a password. Running the script without them prints the template |

Before slicing it refuses STLs that are out of date with the CAD (run
`python3 cad/fit.py`), and lists any part sizes the part depends on that are
still assumed rather than measured. It asks before starting the printer
(`--yes` skips the question) and stops if the printer is already busy.
Ctrl-C stops following the print, not the print. Sliced jobs are kept in
`cad/sliced/` (not committed). The part settings live in `PARTS` at the top
of the script: change them there and in the tables above together.

---

## With UWB

Additional parts:

| Part | Walls | Infill | Layer | Est. mass | Est. time |
| --- | --- | --- | --- | --- | --- |
| [Anchor arm](../../with_uwb/cad/anchor_arm.scad) ×2 | 4 | 25 % | 0.2 | ≈ 22 g each | ≈ 2.3 h each |
| [Mast foot](../../with_uwb/cad/anchor_mast.scad) | 4 | 25 % | 0.2 | ≈ 11 g | ≈ 1.5 h |
| [Mast cradle](../../with_uwb/cad/anchor_mast.scad) | 4 | 25 % | 0.2 | ≈ 14 g | ≈ 1.5 h |
| [Wearable pod](../../with_uwb/cad/wearable_case.scad) | 2 | 20 % | 0.2 | ≈ 44 g | ≈ 4 h |

### Orientation and supports, with UWB

| Part | Orientation | Supports |
| --- | --- | --- |
| Anchor arm | flat, as modelled | none |
| Mast foot, mast cradle | socket opening up, as modelled | none |
| Wearable pod | body and lid side by side, as modelled | none |

### After printing, with UWB

| Step | Tool | Where |
| --- | --- | --- |
| Fit heat-set inserts | soldering iron, flat tip, ≈ 200 °C | 2 × M3 in each of the three bosses on the drum wall, 1 × M3 in each mast socket (8 more) |
| Dry-fit | — | an arm on each side boss; the foot on the back boss and the dowel in both sockets |

### Print order, with UWB

- **Anchor arms** ×2: after the lid (print while wiring the enclosure).
- **Wearable pod:** no dependencies; any time.

---

## Without UWB

Common parts only: ≈ 500 g PETG, ≈ 46 h. No supports. Sources:
[`without_uwb/cad/`](../../without_uwb/cad/).

---

## Croc charms (Jibbitz)

Small detailed charms that push into Croc shoe holes. A compact entry-level
desktop printer is sufficient.

### Printer requirements for charms

| Feature / spec | Recommended minimum | Why it matters for charms |
| --- | --- | --- |
| Build volume | **150 × 150 × 150 mm** (or larger) | charms are small (~25–35 mm); a compact bed keeps the printer cheap and small |
| Nozzle | **0.4 mm** (standard) | works fine. Being able to swap to a **0.2 mm** nozzle is ideal for sharp micro-detail on small logos and faces |
| Extruder | **direct drive** | **crucial for TPU** (flexible filament). Bowden extruders struggle or jam pushing the rubber-like material that makes durable stems |
| Materials | **PLA, PETG, TPU** | PLA for quick detailed designs, PETG for impact and heat resistance, TPU for flexible charms or non-snap buttons |
| Bed levelling | **auto bed levelling (ABL)** | small prints depend on a perfect first layer; ABL saves fighting manual calibration |
| Bed surface | **textured PEI spring-steel sheet** | grips without tape or glue stick, and prints pop off when the sheet is flexed |

### FDM, not resin

Resin (SLA) gives finer detail but is brittle and snaps when pushed into the
rubber holes. **Use FDM**; TPU or PETG charms survive daily wear.

### Which printer

Compact direct-drive printers that meet every requirement above out of the
box: **Bambu Lab A1 Mini**, **Creality Ender-3 V3 SE / KE**.

---

## One printer for both

Combined requirement (stricter of each):

| Spec | SportCam | Croc charms | Buy |
| --- | --- | --- | --- |
| Build volume | 155 × 155 × 90 mm | 150 × 150 × 150 mm | **≥ 155 × 155 × 150 mm** — a 150 × 150 bed is too small for the with-UWB enclosure (153 × 155 mm) |
| Nozzle | 0.4 mm | 0.4 mm, 0.2 mm swappable is ideal | 0.4 mm, with swappable nozzles |
| Extruder | either | direct drive | **direct drive** |
| Materials | PETG (TPU optional for the UWB wearable pod) | PLA, PETG, TPU | PLA, PETG, TPU — hotend to **250 °C** for PETG |
| Heated bed | 80 °C | — | 80 °C |
| Bed levelling | — | auto | **auto (ABL)** |
| Bed surface | textured PEI, garolite, or glass with glue (not bare smooth PEI) | textured PEI | **textured PEI** spring steel |
| Technology | FDM | FDM | FDM |

### Printers to buy

All meet the **Buy** column above. Manufacturer specs; prices vary with sales.

| # | Printer | Build volume | Fits both? | Buy | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | **Bambu Lab A1 Mini** — *top choice* | 180 × 180 × 180 mm | yes | [Bambu Lab Canada](https://ca.store.bambulab.com/products/a1-mini) · [Amazon.ca](https://www.amazon.ca/s?k=bambu+lab+a1+mini) | direct drive, full auto calibration, textured PEI included, tool-free nozzle swap (0.2 mm sold separately). Smallest and quietest of the list, and clears the 155 mm battery tray. ≈ C$249 on sale, C$389 list |
| 2 | Bambu Lab A1 | 256 × 256 × 256 mm | yes | [Bambu Lab Canada](https://ca.store.bambulab.com/products/a1) · [Amazon.ca](https://www.amazon.ca/s?k=bambu+lab+a1+3d+printer) | the same machine with a bigger bed — pick it if you'll print anything larger than SportCam |
| 3 | Creality Ender-3 V3 SE | 220 × 220 × 250 mm | yes, add a textured PEI sheet | [Creality](https://www.creality.com/products/creality-ender-3-v3-se) · [Amazon.ca](https://www.amazon.ca/s?k=creality+ender-3+v3+se) | cheapest route; direct drive and auto levelling. Ships with a coated sheet rather than textured PEI, so budget ≈ C$25 for a 235 mm textured PEI sheet |
| 4 | Creality Ender-3 V3 KE | 220 × 220 × 240 mm | yes | [Creality](https://www.creality.com/products/creality-ender-3-v3-ke) · [Amazon.ca](https://www.amazon.ca/s?k=creality+ender-3+v3+ke) | faster, 300 °C hotend; check the listing for which bed sheet is included |

### Pros and cons

#### 1. Bambu Lab A1 Mini (top choice)

| Pros | Cons |
| --- | --- |
| Works out of the box: auto bed levelling, flow and vibration calibration, all automatic | 180 × 180 mm bed clears every SportCam part, but leaves little room to batch them |
| Textured PEI sheet included, so no extras to buy | Open frame, no enclosure or filter: keep it in a room with some fresh air, not a bedroom |
| Tool-free nozzle swap; 0.2 mm nozzle for fine charm detail is a click-in part | 80 °C bed max: fine for PLA, PETG and TPU, rules out ABS/ASA |
| Direct drive handles TPU | Bambu ecosystem: slicer, firmware and spare parts come from Bambu; cloud by default (LAN-only mode available) |
| Quiet, small footprint, built-in camera to watch long prints | Its cantilevered gantry is stiff for its size, but it is not a printer to grow into large parts |
| Optional AMS Lite for multi-colour charms | Cheapest at sale price; list price is noticeably higher |

#### 2. Bambu Lab A1

| Pros | Cons |
| --- | --- |
| Everything the A1 Mini has, on a 256 mm cube | Costs more than the Mini for no benefit on SportCam or charms |
| Room to print several SportCam parts, or a tray of charms, at once | Bed slinger: needs roughly twice its depth in clear desk space as the bed moves |
| 100 °C bed | Same Bambu-ecosystem and open-frame points as the Mini |
| Room for future projects bigger than 180 mm | Had a heated-bed cable recall in 2024; units sold now ship with the fixed cable, but check a second-hand one |

#### 3. Creality Ender-3 V3 SE

| Pros | Cons |
| --- | --- |
| Usually the cheapest printer on this list | Doesn't come with a textured PEI sheet, so add ≈ C$25 for one |
| Large 220 × 220 × 250 mm volume | Slower, and needs more hands-on tuning to print well than the Bambu printers |
| Direct drive extruder and auto levelling | No Wi-Fi or camera: prints go over USB stick or SD card |
| Open firmware, huge community, cheap generic spare parts | 260 °C hotend is enough for PETG, but has little margin |
| | Nozzle swaps take tools and a hot hotend; louder than the Bambu printers |

#### 4. Creality Ender-3 V3 KE

| Pros | Cons |
| --- | --- |
| Faster than the SE, with a 300 °C hotend | Costs more than the SE, and gets close to the A1 Mini, which needs less setup |
| Wi-Fi and Klipper-based firmware for remote control and tuning | Creality's firmware and app are less polished than Bambu's |
| Large 220 × 220 × 240 mm volume | Bed sheet type varies by listing: check that it includes textured PEI |
| Direct drive and auto levelling | Camera costs extra; louder than the Bambu printers |

**Recommendation: Bambu Lab A1 Mini** (purchased): meets every requirement
out of the box, lowest price, least setup. The A1 if larger prints are
needed.
