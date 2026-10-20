# 11 — 3D printing: requirements, materials and settings

Printed parts, printer requirements, materials and settings for both builds.
Any stock desktop FDM printer of Ender 3 / Prusa Mini / Bambu A1 class is
sufficient.

| Build | Parts | PETG | Machine time |
| --- | --- | --- | --- |
| [With UWB](#with-uwb) | 10 (5 common + 2 arms, mast foot, mast cradle, wearable pod) | ≈ 420 g | ≈ 40 h |
| [Without UWB](#without-uwb) | 5 (the common parts) | ≈ 280 g | ≈ 26 h |

| Topic | Reference |
| --- | --- |
| Sizes | for the part sizes assumed in [`cad/ordered_parts.toml`](../../cad/ordered_parts.toml). `cad/fit.py` resizes the enclosure, shelf, lid and diffuser to measured parts; current figures in [`cad/FIT_REPORT.md`](../../cad/FIT_REPORT.md) |
| Sources | `<build>/cad/` ([with UWB](../../with_uwb/cad/), [without UWB](../../without_uwb/cad/)); STL workflow in [Appendix A](../appendix/appendix-a-cad-parts.md) |
| Part roles | [03 — Mechanical design](../design/03-mechanical-design.md) |
| Croc charms (separate project, same printer) | [Croc charms](#croc-charms-jibbitz), [One printer for both](#one-printer-for-both) |

## Printer requirements

| Requirement | Minimum | Why |
| --- | --- | --- |
| Technology | FDM / FFF | all parts are designed for it |
| Build volume | **160 × 155 × 90 mm** | the battery tray is 155 mm long; the with-UWB enclosure is 147 × 149 mm and 84 mm tall |
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
| **Automated check** | `python3 cad/fit.py` measures every STL in both builds; fails on oversize or multi-piece parts. Caps the enclosure diameter (162 mm with UWB, where the arm bosses add 8 mm). Runs on every render, on CAD commits, and when a Claude Code session ends with CAD changes ([Appendix A](../appendix/appendix-a-cad-parts.md#fit-the-layout-to-your-parts)) |

Sizes with the assumed parts (bounding box, mm):

| Part | Build | Size | Margin to 170 |
| --- | --- | --- | --- |
| Enclosure | with UWB | 147 × 149 × 84 | 21 |
| Enclosure | without UWB | 139 × 139 × 73 | 31 |
| Pi shelf | <!--both-->with UWB / without<!--/--><!--with_uwb: with UWB--><!--without_uwb: without UWB--> | <!--with_uwb-->132 × 117 × 3<!--/--><!--both--> / <!--/--><!--without_uwb-->128 × 87 × 3<!--/--> | 38+ |
| Lid | <!--both-->with UWB / without<!--/--><!--with_uwb: with UWB--><!--without_uwb: without UWB--> | <!--with_uwb-->141 × 141 × 11<!--/--><!--both--> / <!--/--><!--without_uwb-->135 × 135 × 11<!--/--> | 29+ |
| LED diffuser band | <!--both-->with UWB / without<!--/--><!--with_uwb: with UWB--><!--without_uwb: without UWB--> | <!--with_uwb-->Ø 145 × 16<!--/--><!--both--> / <!--/--><!--without_uwb-->Ø 139 × 16<!--/--> | 25+ |
| Battery tray | both | 155 × 77 × 12 | 15 |
| Wearable pod | with UWB | 142 × 74 × 31 | 28 |
| Anchor arm, mast foot, mast cradle | with UWB | ≤ 69 mm | 100+ |

- **Build volume is the only hard requirement:** 160 × 155 mm clears every
  part at the assumed sizes; the A1 Mini's 180 × 180 leaves margin.
- Resin printers are unsuitable (structural parts).

## What to buy

| Material | Qty | Notes |
| --- | --- | --- |
| **PETG, 1 kg, any colour** | 1 spool | the structural parts: ≈ <!--with_uwb-->380 g<!--/--><!--both--> with UWB, ≈ <!--/--><!--without_uwb-->240 g<!--/--><!--both--> without<!--/-->. A 1 kg spool leaves plenty for reprints |
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

Every build prints these five; their sizes are in the
[table above](#design-rule-every-part-prints-on-a-bambu-lab-a1-mini).<!--both--> Links go to the UWB build's sources; the
camera-only build has the same files in `without_uwb/cad/`. Masses and times
are the with-UWB ones (camera-only in brackets where they differ).<!--/-->

| Part | Walls | Infill | Layer | Est. mass | Est. time |
| --- | --- | --- | --- | --- | --- |
| [Enclosure](../../with_uwb/cad/base_housing.scad) | 4 | 20 % | 0.2 | <!--with_uwb-->≈ 180 g<!--/--><!--both--> (<!--/--><!--without_uwb: ≈ --><!--without_uwb-->145 g<!--/--><!--both-->)<!--/--> | <!--with_uwb-->≈ 18 h<!--/--><!--both--> (<!--/--><!--without_uwb: ≈ --><!--without_uwb-->14 h<!--/--><!--both-->)<!--/--> |
| [Pi shelf](../../with_uwb/cad/shelf.scad) | 3 | 20 % | 0.2 | ≈ 32 g | ≈ 2.5 h |
| [Lid](../../with_uwb/cad/lid.scad) | **5** | **40 %** | 0.2 | <!--with_uwb-->≈ 65 g<!--/--><!--both--> (<!--/--><!--without_uwb: ≈ --><!--without_uwb-->60 g<!--/--><!--both-->)<!--/--> | ≈ 4 h |
| [LED diffuser band](../../with_uwb/cad/led_diffuser_ring.scad) | **2** | **0 %** | 0.2 | ≈ 6 g | ≈ 1.5 h |
| [Battery tray](../../with_uwb/cad/battery_tray.scad) | 3 | 20 % | 0.2 | ≈ 38 g | ≈ 3.5 h |

Enclosure differences by build: size (solved per build by `fit.py`) and wall. <!--with_uwb-->The UWB one has three bosses for the arms and mast, and
a slot for the anchor cables<!--/--><!--both-->; the camera-only one is plain all round<!--/--><!--without_uwb: The camera-only one is plain all round-->.

Estimates: mass from STL volume at 1.27 g/cm³ (PETG), scaled for walls and
infill; time for a 0.4 mm nozzle at 0.2 mm layers, default speeds. **The
slicer's figures take precedence.**

### Orientation and supports

Every part is modelled in print orientation. Printed as exported from
OpenSCAD, **no supports are needed**<!--with_uwb--> — except under
the UWB enclosure's wall bosses ([below](#with-uwb))<!--/-->.

| Part | Orientation | Supports |
| --- | --- | --- |
| Enclosure | open end up, as modelled | <!--without_uwb-->none<!--/--><!--both--> without UWB<!--/--><!--with_uwb: see [below](#with-uwb) for the bosses; otherwise none-->. The LED window is cut in bays with a thin rib every 22 mm, so the wall above it bridges short spans; the ledge under the window has a 45° underside; the shelf posts grow straight up out of the wall<!--both-->. With UWB, see below<!--/--> |
| Pi shelf | flat, as modelled | none |
| Lid | **flip it: top face on the bed**, locating ring up | none |
| Diffuser band | standing, as modelled | none. **Brim recommended**: it is a tall thin ring with a small footprint |
| Battery tray | flat, as modelled | none |

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
| Check the tripod bore fits your 3/8-16 insert | drill or step bit if it is larger than the bore | enclosure floor |
| Fit heat-set inserts | soldering iron, flat tip, ≈ 200 °C | M3: one in the top of each of the three shelf posts, and four pushed sideways into the lid's ring (7 total) |
| Dry-fit before wiring | — | lid ring in the enclosure mouth; shelf on its posts; diffuser band over the window onto its ledge; the bank in the tray |

The 3/8-16 brass tripod insert is epoxied, not heat-set.<!--with_uwb--> Additional UWB inserts:
[below](#with-uwb).<!--/-->

## Measure before you print

Before printing (lid ≈ 4 h, enclosure ≈ 18 h): measure the bought parts,
enter the values in [`cad/ordered_parts.toml`](../../cad/ordered_parts.toml),
run `python3 cad/fit.py` (re-solves the layout, re-renders, checks fit). What
to measure: first table of **15 — Verification checklist**
([with UWB](../../with_uwb/docs/setup/15-verification.md#before-you-print),
[without UWB](../../without_uwb/docs/setup/15-verification.md#before-you-print)).

## Print order

For building in parallel with printing:

| # | Part | Reason |
| --- | --- | --- |
| 1 | **Enclosure** | longest print; required for all assembly |
| 2 | **Shelf** | carries the LED ring and the Pi |
| 3 | **Lid** | needed when the Arducam base arrives |
| 4 | **Diffuser band** | needed after the LED ring is fitted |
| 5 | **Battery tray** | last; measure the bank first |

<!--with_uwb-->

UWB build: anchor arms and pod order in [Print order, with UWB](#print-order-with-uwb).

<!--/-->

---

## With UWB

Additional parts:

| Part | Walls | Infill | Layer | Est. mass | Est. time |
| --- | --- | --- | --- | --- | --- |
| [Anchor arm](../../with_uwb/cad/anchor_arm.scad) ×2 | 4 | 25 % | 0.2 | ≈ 16 g each | ≈ 1.7 h each |
| [Mast foot](../../with_uwb/cad/anchor_mast.scad) | 4 | 25 % | 0.2 | ≈ 11 g | ≈ 1.5 h |
| [Mast cradle](../../with_uwb/cad/anchor_mast.scad) | 4 | 25 % | 0.2 | ≈ 14 g | ≈ 1.5 h |
| [Wearable pod](../../with_uwb/cad/wearable_case.scad) | 2 | 20 % | 0.2 | ≈ 44 g | ≈ 4 h |

### Orientation and supports, with UWB

| Part | Orientation | Supports |
| --- | --- | --- |
| Enclosure | open end up, as modelled | **Yes, but only under the three wall bosses.** They are 6 mm ledges on the outside wall at ±Y and −X, starting 10 mm up. Paint-on or support-blocker supports just there, or accept a slightly droopy underside nobody sees |
| Anchor arm | flat, as modelled | none |
| Mast foot, mast cradle | socket opening up, as modelled | none |
| Wearable pod | body and lid side by side, as modelled | none |

### After printing, with UWB

| Step | Tool | Where |
| --- | --- | --- |
| Fit heat-set inserts | soldering iron, flat tip, ≈ 200 °C | 2 × M3 in each of the three wall bosses, 1 × M3 in each mast socket (8 more, 15 in all) |
| Dry-fit | — | an arm on each side boss; the foot on the back boss and the dowel in both sockets |

### Print order, with UWB

- **Anchor arms** ×2: after the lid (print while wiring the enclosure).
- **Wearable pod:** no dependencies; any time.

---

## Without UWB

Common parts only: ≈ 280 g PETG, ≈ 26 h. No supports. Sources:
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
| Build volume | 160 × 155 × 90 mm | 150 × 150 × 150 mm | **≥ 160 × 155 × 150 mm** — a 150 × 150 bed is too small for the SportCam battery tray (155 mm long) |
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
