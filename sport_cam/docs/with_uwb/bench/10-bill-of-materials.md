# 10 — Bill of materials (bench test, with UWB)

The least you need to run the camera on a bench, off a mains power supply,
and test the phone app end to end: live view, control, recording, upload,
sign-in, pairing a tag, a tag-started recording that belongs to its wearer,
and each person's own library. It runs the UWB build's software.

Everything else is left out, and nothing printed is needed. The full parts
list is the [UWB build's](../setup/10-bill-of-materials.md);
**#** numbers below are the same parts there, and **B** numbers are bench-only.

| Left out | Why the test doesn't need it | What the software does instead |
| --- | --- | --- |
| power bank, PD trigger, USB-C cable (items 9, 10, 14) | the 12 V comes from the bench supply | — |
| battery gauge (12) | no battery to measure | `POWER_MONITOR = "none"`: no battery warnings |
| rocker switch and power latch (13, 13a) | you unplug the supply | the Pi isn't told to shut down: stop the software first ([14](14-software-setup.md)) |
| LED ring and level shifter (7, 8) | the app shows the same state | the ring code finds nothing to drive and carries on |
| Pi-driven servos: extension leads and headers (part of 18) | the kit's own servo drive works | `SERVO_DRIVER = "arducam"`: whole-degree steps, a little less smooth |
| the third anchor, A3, and its mast (one of the four item 6 radios, 27a) | it only adds elevation: the bearing, and whose tag it is, come from A1 and A2 | `UWB_ANCHORS = 2`: tilt follows the person detector alone |
| the tag's armband (17) | you hold the tag, or put it in a pocket | — |
| panel barrel jack, standoffs, screws, inserts, tripod, filament, strap, epoxy (18, 21–27) | no enclosure | the head stands on the bench on its own metal base, and the anchors are taped to a stick (B8) |

Prices: approximate CAD street prices, Oct 2026, ±15 %.

## Camera

| # | Status | Part | Qty | ≈ CAD | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | A | **Arducam IMX477 12 MP PTZ camera with metal pan-tilt base (B0167B12)** | 1 | — | as the full build | used as it comes: the servo leads stay on the PTZ controller |

## Compute

| # | Status | Part | Qty | ≈ CAD | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | A | **Raspberry Pi 4 Model B, 4 GB** | 1 | — | as the full build | |
| 3 | A | Pi 4 heatsink + fan case, or heatsinks | 1 | — | as the full build | on an open bench, stick-on heatsinks are plenty |
| 4 | A | microSD 64 GB A2 | 1 | — | as the full build | |

## Tracking

| # | Status | Part | Qty | ≈ CAD | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 6 | | **Haorutech ULA1 UWB module (ESP32 + DWM1000)** | 3 | — | as the full build | two anchors, A1 and A2, and the tag. Flashed from your computer over their USB plugs ([14, step 1](14-software-setup.md#1-flash-the-radios-on-your-computer)) |
| 15 | | Slim USB power bank, 2 500–5 000 mAh | 1 | — | as the full build | powers the tag. Any USB-A power bank or phone charger does on the bench |

## Power

| # | Status | Part | Qty | ≈ CAD | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | A | **BOSYTRO 12 V 40 A (480 W) switching power supply** | 1 | — | owned | stands in for the bank and the PD trigger. The camera draws ≈ 1 A of it: 40 A is far more than needed, so **the fuse (B3) matters** — a short on this supply melts wire before the supply notices. Mains goes on screw terminals: see [wiring](12-wiring.md#mains) |
| B2 | A | **Mains cord, 3-prong** | 1 | — | came with the supply | wall to the supply's **L / N / ⏚** terminals. Check it has the ground pin and a green (or green-yellow) wire: ground goes to ⏚, which earths the supply's metal case |
| 11 | A | 12 V → 5 V 8 A buck, **adjustable** | 1 | — | as the full build | trimmed to 5.1 V under load before the Pi is connected, exactly as in the full build |

## Wiring and fasteners

| # | Status | Part | Qty | ≈ CAD | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| B3 | | **Inline blade-fuse holder, 16 AWG, with 5 A fuses** | 1 | $10 | [Amazon.ca](https://www.amazon.ca/s?k=inline+atc+blade+fuse+holder+16+awg) | in the +12 V lead, right at the supply. 5 A is several times what the camera draws and far below what melts 18 AWG |
| 18 | | 18 AWG silicone wire, red and black, and heatshrink | ≈ 1 m each | — | from the full build's kit (item 18) | supply → fuse → buck, and buck → the 5 V connectors |
| 19 | | 470 µF electrolytic capacitor, 10 V or higher | 1 | — | as the full build | across the buck output, stripe (−) to OUT−: smooths the dips when the zoom motors start |
| B4 | | **Lever-nut connectors, 3-way (Wago 221-413 or similar)** | 2 | $12 (pack) | [Amazon.ca](https://www.amazon.ca/s?k=wago+221-413) | one for +5 V and one for GND: the buck's output, the Pi's pigtail and the PTZ controller meet in them. **Not the breadboard's rails**: they're rated about 1 A, and the 5 V side carries 2–3 A |
| B5 | | **USB-C plug power pigtail (USB-C male to bare leads), 20 AWG or heavier** | 1 | $10 | [Amazon.ca](https://www.amazon.ca/s?k=usb+c+male+pigtail+power+cable+20awg) | 5 V into the Pi from the lever nuts. The Pi 4 needs no PD negotiation, just 5 V on VBUS. Thin "data" pigtails (28 AWG power wires) drop too much voltage: check the listing |
| B6 | | **Half-size breadboard with jumper wires (M-M, M-F, F-F)** | 1 | $12 | [Amazon.ca](https://www.amazon.ca/s?k=half+size+breadboard+jumper+wire+kit) | for the signals only: the PTZ controller's I2C (SDA, SCL) to the Pi's header. Power doesn't go through it (B4) |
| 20 | | USB-A male-to-female extension cables, 50 cm | 2 | — | as the full build (item 20) | A1 and A2 into the Pi's USB-A ports, so the boards can sit 40 cm apart |
| B8 | | **Anchor bar:** a straight stick of wood, ≥ 50 cm (a wooden ruler, a dowel or a slat), and masking tape | 1 | — | owned | holds A1 and A2 **400 mm apart** (`UWB_BASELINE_M`), level, in front of the camera. **Wood, not metal**: metal near an antenna detunes it |
| B7 | | **Dummy load: 1.2 Ω 50 W aluminium-housed resistor** | 1 | $8 | [Amazon.ca](https://www.amazon.ca/s?k=1.2+ohm+50w+aluminum+resistor) | ≈ 4.2 A at 5.1 V, for trimming the buck under load ([wiring, step 2](12-wiring.md#wiring-order-with-checks)). It gets hot: lay it on something metal and connect it for no more than 30 s at a time. Already have an electronic load? Use that |

**Tools you also need:** a multimeter, a small flat screwdriver (supply and
lever-nut terminals, buck trim pot), wire strippers, and a crimper if the cord's
ends need fork terminals. No soldering iron, unless your pigtail or buck needs it. A computer with the
Arduino IDE, to flash the radios.

## Totals (CAD)

| | ≈ CAD |
| --- | --- |
| New for the bench (B3–B7) | **≈ $52** |
| Already owned (items 1–4, 6, 11, 15, 18–20, the supply and its cord, a stick) | — |

Two of these go on into the full build: the USB-C pigtail (B5) powers the
Pi there too ([wiring, R2](../setup/12-wiring.md)), and
the dummy load (B7) is the full build's first bench job as well, and the
radios, the tag bank and the extensions go in as they are. The rest stays on
the bench.
