# 10 — Bill of materials (Canadian sourcing, Toronto / M2L 2E2)

Parts list for the camera-only build: prices, Canadian sources, printed parts.
No tag or anchors. Main cost item: the Arducam PTZ camera (sensor, zoom lens,
both motion axes). Remainder: Pi, power chain, fasteners. Differences from the
[UWB build](../../with_uwb/setup/10-bill-of-materials.md):
[Compared with the UWB build](#compared-with-the-uwb-build).

Target: delivery to **M2L 2E2 (North York, Toronto) within two weeks**.

| Supplier | Lead time | Use |
| --- | --- | --- |
| **Amazon.ca Prime** | 1–3 days | general parts. Links are searches on the exact part name (listings change); choose a Prime-badged match and avoid "ships from China" sellers (3–4 weeks) |
| **[RobotShop Canada](https://ca.robotshop.com/)** | a few days (Mirabel, QC) | Arducam PTZ kits |
| **[PiShop.ca](https://www.pishop.ca/)** | 1–3 days (Ontario) | official Raspberry Pi reseller; all Pi items |
| **[Digi-Key Canada](https://www.digikey.ca/)** | 1–3 days | backstop for out-of-stock items. Free shipping over C$100 |

Prices: approximate CAD street prices, Oct 2026, ±15 %.

> **Before printing:** complete
> [15 — Verification checklist](15-verification.md#before-you-print).
> Five bought-part measurements determine whether the printed parts fit;
> the enclosure is a 14-hour print.

**Status column:** **A** acquired, **O** ordered, **P** pending, blank = not
ordered. Printed-parts table: tick **Acquired** ☐ when printed.

## Camera

| #   | Status | Part                                                                    | Qty | ≈ CAD | Source                                                                                                                                                                        | Notes                                                                                                                                                                                                                                                                                                                                                                                                                        |
| --- | ------ | ----------------------------------------------------------------------- | --- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | A      | **Arducam IMX477 12 MP PTZ camera with metal pan-tilt base (B0167B12)** | 1   | $293  | [RobotShop CA](https://ca.robotshop.com/products/arducam-imx477-12mp-ptz-camera-w-metal-pan-tilt-base-for-raspberry-pi-jetson-b0167b12) · [Arducam](https://www.arducam.com/) | camera, motorized zoom lens, aluminium base, two digital servos and the I2C controller, assembled. Both axes 0–180°. **Ordered 9 Oct direct from Arducam, order #000009517, express: US$204.99 + US$38 shipping. Arducam prices in USD and ships from China, so the landed cost lands nearer C$340 plus HST on import than the C$293 shown here — that figure is the RobotShop CA shelf price, kept as the planning number |

### Why the IMX477

- The 8 MP IMX219 PTZ kit (B0167B8) is discontinued; the 12 MP IMX477 kit is
  the only option. Design, CAD and software assume it.
- Larger pixels: better in dim gyms.
- Reach: [05 — Camera placement](../design/05-tracking-system.md#camera-placement-envelope).

## Compute and status

| #   | Status | Part                                                   | Qty | ≈ CAD  | Source                                                                                                                                                                                          | Notes                                                                                                                                                                                                                                                                                                   |
| --- | ------ | ------------------------------------------------------ | --- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2   | A      | **Raspberry Pi 4 Model B, 4 GB**                       | 1   | $95    | [PiShop.ca](https://www.pishop.ca/product/raspberry-pi-4-model-b-4gb/) · [Amazon.ca](https://www.amazon.ca/s?k=raspberry+pi+4+model+b+4gb)                                                      | **not a Pi 5.** The Pi 4 has a hardware H.264 encoder; the Pi 5 dropped it and encodes in software, which costs about 4 W and two hours of runtime. See [04](../../design/04-electronics.md#why-a-pi-4-and-not-a-pi-5). Buy the bare board                                                                           |
| 3   | A      | Pi 4 heatsink + fan case, or an aluminium heatsink set | 1   | $12    | [Amazon.ca](https://www.amazon.ca/s?k=raspberry+pi+4+heatsink+fan)                                                                                                                              | the Pi 5 Active Cooler does **not** fit a Pi 4. Passive heatsinks are enough at this load; a fan is cheap insurance in a sealed enclosure                                                                                                                                                               |
| 4   | A      | microSD 64 GB A2 (SanDisk Extreme)                     | 1   | $14    | [Amazon.ca](https://www.amazon.ca/s?k=sandisk+extreme+64gb+microsd+a2)                                                                                                                          | recordings land here at 5.4 GB/h, so 64 GB holds ≈ 10 h — more than one battery charge can produce. 128 or 256 GB only helps if you carry spare banks and stay offline; see [04](../../design/04-electronics.md#the-sd-card). **Buy a known brand**: counterfeit cards are the commonest cause of Pi corruption      |
| 7   | A      | WS2812B LED ring, 16 px                                | 1   | $14    | [Amazon.ca](https://www.amazon.ca/s?k=ws2812b+ring+16+led)                                                                                                                                      | status indicator; `LED_COUNT = 16`. A 16-px ring is 44 mm across — to light the 120 mm window evenly, ~380 mm of 60/m WS2812B **strip** (≈ 23 px) lining the window works better; change `LED_COUNT` if you do                                                                                          |
| 8   | A      | 74AHCT125 level shifter                                | 1   | $6     | [Amazon.ca](https://www.amazon.ca/s?k=74ahct125) · [Digi-Key.ca](https://www.digikey.ca/)                                                                                                       | lifts the Pi's 3.3 V signals to 5 V: SPI data for the ring<!--both-->, and the two servo PWM lines (gates 2 and 3) when the Pi drives the servos<!--/--><!--pigpio:, and the two servo PWM lines (gates 2 and 3)-->. SPI is used instead of the classic PWM/DMA driver so the service need not run as root — see [04](../../design/04-electronics.md#driving-the-ws2812b-ring)                                                                                                         |

## Power

| #   | Status | Part                                                   | Qty | ≈ CAD | Source                                                                                                                                                           | Notes                                                                                                                                                                                                                                                                                                                                                                                        |
| --- | ------ | ------------------------------------------------------ | --- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 9   | A      | **USB-C PD power bank, 25 000 mAh (92 Wh), 65 W+**     | 1   | $80   | [Amazon.ca](https://www.amazon.ca/s?k=25000mah+power+bank+65w+usb+c+pd)                                                                                          | gives **6.2 h** tracking + recording on a Pi 4, after the bank's own conversion loss ([04](../../design/04-electronics.md#runtime)). A 20 000 mAh (74 Wh) bank makes 5.0 h, saves ≈ C$25 and 200 g, and is the better pick unless you want a full day between charges. Whichever you buy, set `BATTERY_WH` to match. Stay under 100 Wh to keep it flyable                                                 |
| 10  | A      | USB-C PD trigger board, 12 V                           | 1   | $10   | [Amazon.ca](https://www.amazon.ca/s?k=usb+c+pd+trigger+board+12v+female)                                                                                                | negotiates 12 V out of the bank. It must have a USB-C **socket** (female) for the bank cable to plug into — not a USB-C plug sticking out of its end. The common button type (5/9/12/15/20 V, "Type-C Female to 2pin Terminal") is a good choice: it saves its setting through power cycles, so it comes back at 12 V after every bank swap, and its S1 pad locks the button ([wiring, step 2](12-wiring.md)). Fixed-12 V boards are fine too. 3 A cables are enough: the camera draws ≈ 36 W at most; most banks cap their 5 V profile at 3 A, and the 5 V rail here also feeds the servos and the ring                                                                                                                                                                                                         |
| 11  | A      | 12 V → 5 V 8 A buck (≥ 40 W), **adjustable**           | 1   | $16   | [Amazon.ca](https://www.amazon.ca/s?k=12v+to+5v+8a+adjustable+buck+converter)                                                                                    | the single 5 V rail. Buy an adjustable unit, not a fixed-5 V one: it must be **trimmed to 5.1 V under a 4 A load before the Pi is ever connected**. Open-circuit voltage tells you nothing — a module that reads 5.1 V unloaded and sags to 4.8 V will brown out a Pi. This is the first bench job in the build. The Schottky diode that comes with it goes on its 12 V input ([12, Input diode](12-wiring.md#input-diode))                                                                             |
| 13  | A      | Round panel-mount rocker switch, threaded              | 1   | $8    | [Amazon.ca](https://www.amazon.ca/s?k=round+rocker+switch+threaded+nut+12v) | the on/off switch, in the enclosure wall. It signals the power latch (13a) rather than carrying the power, so switching off is a clean shutdown: the recording is saved and the head parked before the power goes. A round SPST rocker with a threaded body and a locking ring: the bezel sits on a flat cut into the wall outside and the ring screws up against a flat boss inside. The hole has a flat matching the key flat on the thread, so the switch can't turn. Measure it for `[switch]` before printing; a lit one is fine |
| 13a | O | **Power latch** — built from the parts in [its own table](#power-latch) | 1 | $34 | [below](#power-latch) | keeps the 12 V on after the switch goes off until the Pi has shut down, then cuts it |
| 14  | A      | USB-C to USB-C cable, 30 cm                            | 1   | $10   | [Amazon.ca](https://www.amazon.ca/s?k=short+usb+c+to+usb+c+cable+30cm)                                                                                           | bank to trigger board, inside the build. Any standard C-to-C cable works: the trigger draws ≈ 1.7 A at 12 V, inside the 3 A every C-to-C cable carries, and PD negotiates over the CC wire that even charge-only cables have. 30 cm is for fit; a short phone cable you already own will do. **Not USB-A to C**, which carries no PD                                                         |
| 14a | O | **USB-C plug power pigtail (USB-C male to bare leads), 20 AWG or heavier** | 1 | $10 | [Amazon.ca](https://www.amazon.ca/s?k=usb+c+male+pigtail+power+cable+20awg) | the buck's 5 V into the Pi's USB-C (connection R2 in the [wiring guide](12-wiring.md)). The Pi 4 needs no PD negotiation, just 5 V on VBUS. Thin "data" pigtails (28 AWG power wires) drop too much voltage: check the listing |
| 14b | O | **Dummy load: 1.2 Ω 50 W aluminium-housed resistor** (a tool) | 1 | $8 | [Amazon.ca](https://www.amazon.ca/s?k=1.2+ohm+50w+aluminum+resistor) | ≈ 4.2 A at 5.1 V, for trimming the buck under load before the Pi is connected ([wiring, step 1](12-wiring.md#wiring-order-with-checks)). It gets hot: lay it on something metal and connect it for no more than 30 s at a time. Already have an electronic load? Use that |

Notes:

- Pi power: 5 V rail via the USB-C pigtail (14a). No `config.txt` current flag on a
  Pi 4 (Pi 5 only).
- IMX477 not detected on first boot: add `dtoverlay=imx477`.

## Power latch

Item 13a is a small board you build: it keeps the 12 V on after the rocker goes off until the Pi has
shut down, then cuts it. Circuit, part labels (Q1–Q3, R1–R8) and pinout: [wiring](12-wiring.md#power-latch);
why: [04](../../design/04-electronics.md#power-switch); how to build it, hole by hole: [12a](../../setup/12a-power-latch.md).
Resistors marked *kit* are priced in 13a.9.

| #      | Status | Part | Qty | ≈ CAD | Source | Notes |
| ------ | ------ | ---- | --- | ----- | ------ | ----- |
| 13a.1 | O | **IRF4905 P-channel MOSFET**, TO-220 | 1 | $9 | [Amazon.ca](https://www.amazon.ca/s?k=irf4905) · [Digi-Key.ca](https://www.digikey.ca/en/products/result?keywords=irf4905) | Q1: carries the camera's 12 V (≈ 1.7 A). 0.02 Ω, so it stays cool with no heatsink — leave off the one many packs include. Sold in packs of 10–20. Any P-MOSFET rated ≥ 30 V, ≥ 5 A with R<sub>DS(on)</sub> ≤ 0.05 Ω at −10 V will do |
| 13a.2 | O | **2N3904 NPN transistor**, TO-92 | 2 | $5 | [Amazon.ca](https://www.amazon.ca/s?k=2n3904) · [Digi-Key.ca](https://www.digikey.ca/en/products/result?keywords=2n3904) | Q2 (the Pi's HOLD) and Q3 (the rocker). Sold in packs; a general-purpose NPN kit usually has them |
| 13a.3 | O | Resistor **100 kΩ**, ¼ W metal film | 3 | kit | [Amazon.ca](https://www.amazon.ca/s?k=100k+ohm+resistor+1%2F4w) | R1 (holds Q1 off), R4 and R6 (pull Q3's and Q2's bases down) |
| 13a.4 | O | Resistor **47 kΩ**, ¼ W metal film | 1 | kit | [Amazon.ca](https://www.amazon.ca/s?k=47k+ohm+resistor+1%2F4w) | R3: the rocker's 12 V into Q3's base |
| 13a.5 | O | Resistor **22 kΩ**, ¼ W metal film | 1 | kit | [Amazon.ca](https://www.amazon.ca/s?k=22k+ohm+resistor+1%2F4w) | R7: top half of the SENSE divider (12 V → 2.8 V for the Pi) |
| 13a.6 | O | Resistor **10 kΩ**, ¼ W metal film | 1 | kit | [Amazon.ca](https://www.amazon.ca/s?k=10k+ohm+resistor+1%2F4w) | R2: pulls Q1's gate down when either transistor is on |
| 13a.7 | O | Resistor **6.8 kΩ**, ¼ W metal film | 1 | kit | [Amazon.ca](https://www.amazon.ca/s?k=6.8k+ohm+resistor+1%2F4w) | R8: bottom half of the SENSE divider |
| 13a.8 | O | Resistor **4.7 kΩ**, ¼ W metal film | 1 | kit | [Amazon.ca](https://www.amazon.ca/s?k=4.7k+ohm+resistor+1%2F4w) | R5: the Pi's 3.3 V HOLD into Q2's base |
| 13a.9 | O | ¼ W metal-film resistor assortment kit | 1 | $10 | [Amazon.ca](https://www.amazon.ca/s?k=metal+film+resistor+assortment+kit+1%2F4w) | covers 13a.3–13a.8 in one buy; check the listing has all six values (6.8 k is the one some kits skip). Or buy each value on its own |
| 13a.10 | A | **Double-sided perfboard kit** (ELEGOO or similar: 2×8, 3×7, 4×6, 5×7, 7×9 cm, with a hole in each corner) | 1 | $10 | [Amazon.ca](https://www.amazon.ca/s?k=elegoo+double+sided+pcb+kit) | the latch is built on the **3 × 7 cm** board. It stands on four M3 standoffs (13a.11), and countersunk screws come up through the enclosure floor into them, like the buck. If an M3 screw won't pass its corner holes, drill them to 3.2 mm. Measure it for `[latch]` (`hole_dx`, `hole_dy`). The kit's other boards do for the level shifter (item 8) |
| 13a.11 | O | M3 standoffs, female–female, 8 mm | 4 | — | item 21 | under the latch's corners: M3 screws down through the board into their tops, M3 countersunk screws (item 22) up through the floor into their bottoms. Any length that clears the solder joints underneath works; put it in `[latch] standoff_h` |

## Charging

The bank has a built-in charger; an existing phone charger and cable are
sufficient. Items 28–29 are optional (faster charging) and excluded from the
totals. Tripod bank (item 9), 92 Wh (≈ 108 Wh from the wall), charge time by
charger:

| Charger | Time to full |
| --- | --- |
| Old USB-A cube, 5 V 1–2 A | 12–20 h. Too slow to be useful |
| USB-C phone charger, 20–25 W | ≈ 5 h. Fine overnight |
| USB-C laptop or fast charger, 45 W+ | ≈ 2.5 h |

Cable: **USB-C on both ends** for anything above the first row (USB-A to C
carries 5 V only). A standard C-to-C cable carries 60 W (3 A); only a 65 W
charger exceeds that, by a few minutes.

| #   | Status | Part                                                     | Qty | ≈ CAD | Source                                                                         | Notes                                                                                                                                                                                                                                                                                                                                       |
| --- | ------ | -------------------------------------------------------- | --- | ----- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 28  |        | *Optional:* USB-C PD GaN wall charger, 65 W  | 1   | $40   | [Amazon.ca](https://www.amazon.ca/s?k=65w+gan+charger+usb+c+usb+a+pd)          | USB-C port to the tripod bank (item 9). Only worth it if you have no USB-C charger of 20 W or more, or want ≈ 2 h refills. That needs the bank to accept 65 W *in*. Some 65 W banks only take 30–45 W in, so check the listing. |
| 29  |        | *Optional:* USB-C to USB-C cable, 1 m                    | 1   | $12   | [Amazon.ca](https://www.amazon.ca/s?k=usb+c+to+usb+c+cable+1m)                 | charger to the tripod bank. Item 14 is 30 cm and lives in the build, so it is too short to charge from the wall. Any C-to-C phone cable does this job, and most banks ship with one. Buy only if you have none                                                                                                                              |

- **Pass-through charging** (bank charges and discharges simultaneously;
  stated in the listing): with a USB-C charger, the camera can run from mains
  with no runtime limit.
- **Adafruit 4410** (Micro-Lipo charger, Digi-Key 1528-4410-ND), already
  bought: not used. It charges bare single-cell LiPos; the bank has
  built-in chargers. Return or keep for another project. Excluded from the
  totals.

## Wiring and fasteners

| #   | Status | Part                                                                    | Qty | ≈ CAD | Source                                                                            | Notes                                                                                                                                                                                                                                             |
| --- | ------ | ----------------------------------------------------------------------- | --- | ----- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 18  |        | Barrel jack, JST kit, 18/22 AWG silicone wire, heatshrink, Dupont leads, 2 × 30 cm servo extension leads, male header strip | —   | $25   | [Amazon.ca](https://www.amazon.ca/s?k=jst+connector+kit+22awg+silicone+wire)      | 18 AWG on the 5 V rail — it carries 4 A. The extension leads and two 3-pin headers move the servos onto the Pi's PWM ([12, Servos](12-wiring.md#servos))<!--arducam:: not needed with the servos left on the PTZ controller-->                                                                                                                                                                                                           |
| 19  |        | 470 µF electrolytic capacitor, 10 V or higher (small pack)              | 1   | $10   | [Amazon.ca](https://www.amazon.ca/s?k=470uf+16v+electrolytic+capacitor)           | across the buck output, stripe (−) to OUT− — connection R1 in the [wiring guide](12-wiring.md).                                                                       |
| 21  |        | Nylon standoff kit, M2.5 + M3                                           | 1   | $10   | [Amazon.ca](https://www.amazon.ca/s?k=m2.5+m3+nylon+standoff+kit)                 | Pi on four 6 mm M2.5 standoffs on the shelf. The buck keeps the brass standoffs it comes with; the power latch stands on four 8 mm M3 standoffs from this kit (13a.11); the other power boards are foam-taped down |
| 22  |        | M2.5/M3 screw + nut + brass heat-set insert kit | 1   | $20   | [Amazon.ca](https://www.amazon.ca/s?k=m3+m2.5+screw+nut+assortment) | ≈ 23 × M3: buck and power latch 4 + 4 × M3 × 8 countersunk (up through the floor into their standoffs; the length is in `cad/FIT_REPORT.md`) and 4 × M3 × 6 down through the latch board into its standoffs, PTZ base 4 × M3 × 10–12 (up through the lid into its standoffs, no nuts; `bolt_l` in `ordered_parts.toml`) and the M3 washers under its standoffs if `cad/FIT_REPORT.md` asks for them, lid 4 × M3 × 8 countersunk (in sideways through the wall), shelf 3 × M3 × 8. 8 × M2.5. Inserts: 7 × M3 — 1 in each shelf post, 4 in the lid's ring. Kit price kept at the UWB build's figure |
| 23  |        | 3/8-16 hex nut + 3/8-16 → 1/4-20 reducer bushing                      | 1   | $12   | [Amazon.ca](https://www.amazon.ca/s?k=3%2F8-16+to+1%2F4-20+brass+tripod+bushing) + any hardware store for the nut | tripod interface: the nut is epoxied into a hex pocket in the floor (≈ 14.3 mm across the flats, ≈ 8.3 mm thick — a standard 3/8-16 nut; stainless or zinc-plated). 3/8-16 tripods screw into the nut, 1/4-20 ones into the bushing — so it fits any standard tripod ([C3](../../product/01-requirements.md#non-functional-requirements)). |
| 24  |        | Hook-and-loop strap, 25 mm                                              | 1   | $8    | [Amazon.ca](https://www.amazon.ca/s?k=hook+and+loop+cinch+strap+25mm)             | through the tunnels under the battery tray, round a tripod leg or the centre column. It holds the tray only: the bank clips in, so it stays done up for a swap |
| 25  |        | PETG filament 1 kg                                                      | 1   | $25   | [Amazon.ca](https://www.amazon.ca/s?k=petg+filament+1kg)                          | ~300 g used across the structural parts. Full settings, times and printer requirements: **[3D printing specifications](../../setup/11-3d-printing.md)** |
| 25a |        | PETG filament, **white or natural**, 250 g                              | 1   | $12   | [Amazon.ca](https://www.amazon.ca/s?k=white+petg+filament+250g+sample)            | the LED diffuser band, which has to pass light, and ideally the shelf, whose underside bounces the LED ring's light out — so not your main colour unless that is white. ~40 g used |
| 25b |        | Glue stick (PVA)                                                        | 1   | $4    | [Amazon.ca](https://www.amazon.ca/s?k=glue+stick+3d+printer+bed)                  | a **release agent**, not an adhesive: PETG fuses to bare smooth PEI and tears the sheet                                                                                                                                                           |
| 26  |        | Aluminium tripod (1/4-20 or 3/8-16 head)                                | 1   | $35   | [Amazon.ca](https://www.amazon.ca/s?k=aluminum+camera+tripod)                     | skip if you own one — any standard tripod fits. The head is about 30 cm across and 28 cm tall, so a compact one does                                                                                                                                                                            |
| 27  |        | Build consumables: 2-part epoxy, threadlocker, zip ties, double-sided foam tape, 3 mm foam | —   | $15   | [Amazon.ca](https://www.amazon.ca/s?k=2+part+epoxy+threadlocker+zip+ties)         | epoxy for the 3/8-16 tripod nut; 1 mm foam tape sticks the power boards to the floor and the LED ring under the shelf |

## Printed parts

| Item | Value |
| --- | --- |
| Material | items 25 and 25a, ≈ 280 g |
| Printer | FDM, ≥ 160 × 155 × 90 mm build volume (all parts fit a Bambu Lab A1 Mini), 0.4 mm nozzle, 250 °C hotend, 80 °C bed |
| Machine time | ≈ 26 h |
| Supports | none |
| Settings, orientation, print order | [11 — 3D printing](../../setup/11-3d-printing.md) |
| Printer purchase (not in totals) | Bambu Lab A1 Mini ([Bambu Lab Canada](https://ca.store.bambulab.com/products/a1-mini), ≈ C$249–389); alternatives: [Printers to buy](../../setup/11-3d-printing.md#printers-to-buy) |

STLs, previews and the images below are regenerated by `python3 cad/fit.py`
(also run by `./cad/render_all.sh`).

| Preview | Acquired | Part | Qty | Compiled STL | OpenSCAD source |
| --- | --- | --- | --- | --- | --- |
| <img src="../images/parts/base_housing.png" width="150"> | ☐ | Enclosure | 1 | [base_housing.stl](../../../without_uwb/cad/stl/base_housing.stl) | [base_housing.scad](../../../without_uwb/cad/base_housing.scad) |
| <img src="../images/parts/lid.png" width="150"> | ☐ | Lid (carries the camera) | 1 | [lid.stl](../../../without_uwb/cad/stl/lid.stl) | [lid.scad](../../../without_uwb/cad/lid.scad) |
| <img src="../images/parts/shelf.png" width="150"> | ☐ | Pi shelf | 1 | [shelf.stl](../../../without_uwb/cad/stl/shelf.stl) | [shelf.scad](../../../without_uwb/cad/shelf.scad) |
| <img src="../images/parts/led_diffuser_ring.png" width="150"> | ☐ | LED diffuser band | 1 | [led_diffuser_ring.stl](../../../without_uwb/cad/stl/led_diffuser_ring.stl) | [led_diffuser_ring.scad](../../../without_uwb/cad/led_diffuser_ring.scad) |
| <img src="../images/parts/battery_tray.png" width="150"> | ☐ | Battery tray | 1 | [battery_tray.stl](../../../without_uwb/cad/stl/battery_tray.stl) | [battery_tray.scad](../../../without_uwb/cad/battery_tray.scad) |

## Totals (CAD)

| Configuration | Total |
| --- | --- |
| **Full build** (12 MP PTZ + 92 Wh battery, camera-only), own tripod | **≈ C$751** |
| Full build + tripod (item 26) | ≈ C$786 |
| With a 74 Wh bank instead (6.7 h) | subtract ≈ C$25 |
| Optional charging kit (items 28–29), if your own chargers are too slow | add ≈ C$52 |

(≈ US$537 / US$562 at typical exchange + Canadian markup.)

| Group | Items | ≈ CAD |
| --- | --- | --- |
| Camera and power | 1, 9–11, 13–14b (293 + 80 + 10 + 16 + 8 + 34 + 10 + 10 + 8) | 469 |
| Compute and status | 2–4, 7, 8 (95 + 12 + 14 + 14 + 6) | 141 |
| Wiring, fasteners, filament | 18, 19, 21–25b, 27 (25 + 10 + 10 + 20 + 12 + 8 + 25 + 12 + 4 + 15) | 141 |
| **Total** | | **751** |

Optional charging items 28–29 excluded.

## Two-week delivery plan

Place all orders the same day:

| # | Supplier | Items | Lead time |
| --- | --- | --- | --- |
| 1 | Arducam direct | 1 (camera) | **ordered 9 Oct, express** (longest lead item) |
| 2 | PiShop.ca | 2, 3 | 1–3 days |
| 3 | Amazon.ca Prime | everything else | 1–3 days |

Listing details to verify:

| Item | Check |
| --- | --- |
| Power bank (9) | USB-C output lists **12 V** (without it the trigger stays at 5 V). "65 W" is usually *output*; *input* wattage sets recharge time. Capacity = runtime; don't economise |
| Buck (11) | **adjustable** (must be trimmed); cheap units sag and brown out the Pi |
| USB-C cable (14) | any C-to-C cable carries the 12 V contract |
