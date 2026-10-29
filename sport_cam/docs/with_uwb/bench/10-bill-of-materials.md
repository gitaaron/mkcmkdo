# 10 — Bill of materials (bench test, with UWB)

The least you need to run the camera on a bench, off a USB-C wall adapter,
and test the phone app end to end: live view, control, recording, upload,
sign-in, pairing a tag, a tag-started recording that belongs to its wearer,
and each person's own library. It runs the UWB build's software.

Everything else is left out, and nothing printed is needed. The full parts
list is the [UWB build's](../setup/10-bill-of-materials.md);
**#** numbers below are the same parts there, and **B** numbers are bench-only.

| Left out | Why the test doesn't need it | What the software does instead |
| --- | --- | --- |
| power bank, PD trigger, USB-C cable (items 9, 10, 14) | a USB-C wall adapter powers the Pi | — |
| buck, capacitor, power wire (11, 19, part of 18) | the adapter makes the 5 V, and the PTZ controller takes it from the Pi's header | — |
| battery gauge (12) | no battery to measure | `POWER_MONITOR = "none"`: no battery warnings |
| rocker switch and power latch (13, 13a) | you unplug the adapter | the Pi isn't told to shut down: stop the software first ([14](14-software-setup.md)) |
| LED ring and level shifter (7, 8) | the app shows the same state | the ring code finds nothing to drive and carries on |
| Pi-driven servos: extension leads and headers (part of 18) | the kit's own servo drive works | `SERVO_DRIVER = "arducam"`: whole-degree steps, a little less smooth |
| the third anchor, A3, and its mast (one of the four item 6 radios, 27a) | it only adds elevation: the bearing, and whose tag it is, come from A1 and A2 | `UWB_ANCHORS = 2`: tilt follows the person detector alone |
| the tag's armband (17) | you hold the tag, or put it in a pocket | — |
| panel barrel jack, standoffs, screws, inserts, tripod, filament, strap, epoxy (18, 21–27) | no enclosure | the head stands on the bench on its own metal base, and the anchors are taped to a stick (B3) |

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
| B1 |  | **Raspberry Pi 15 W USB-C power supply (5.1 V, 3 A)** | 1 | $15 | [Amazon.ca](https://www.amazon.ca/s?k=raspberry+pi+4+official+usb-c+power+supply) | powers everything: the Pi, and through its header the PTZ controller and through its USB the anchors. The official one, or another 5.1 V 3 A adapter: a phone charger that sags under the motors browns the Pi out ([wiring](12-wiring.md#why-this-works-on-the-bench-and-not-in-the-full-build)) |

## Wiring

| # | Status | Part | Qty | ≈ CAD | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| B2 |  | **Female-to-female jumper wires (Dupont), 20 cm** | 4 | $5 (pack) | [Amazon.ca](https://www.amazon.ca/s?k=female+to+female+dupont+jumper+wires) | Pi header to the PTZ controller: 5V, GND, SDA, SCL ([wiring](12-wiring.md#connections)). The Arducam kit may include a cable that does this |
| 20 | | USB-A male-to-female extension cables, 50 cm | 2 | — | as the full build (item 20) | A1 and A2 into the Pi's USB-A ports, so the boards can sit 40 cm apart |
| B3 | | **Anchor bar:** a straight stick of wood, ≥ 50 cm (a wooden ruler, a dowel or a slat), and masking tape | 1 | — | owned | holds A1 and A2 **400 mm apart** (`UWB_BASELINE_M`), level, in front of the camera. **Wood, not metal**: metal near an antenna detunes it |

**Tools you also need:** none for the wiring. A multimeter helps if
something doesn't work. A computer with the Arduino IDE, to flash the radios.

## Totals (CAD)

| | ≈ CAD |
| --- | --- |
| New for the bench (B1, B2), if you don't already have them | **≈ $20** |
| Already owned (items 1–4, 6, 15, 20, a stick) | — |

The radios, the tag bank and the extensions go on into the full build as they are. The adapter stays on the bench: the full build runs off its power bank,
through the buck ([wiring](../setup/12-wiring.md)).
