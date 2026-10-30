# 10 — Bill of materials (bench test, without UWB)

The least you need to run the camera on a bench, off a USB-C wall adapter,
and test the phone app end to end: live view, control, recording, upload,
sign-in and each person's own library. It runs the camera-only software.

Everything else is left out, and nothing printed is needed. The full parts
list is the [camera-only build's](../setup/10-bill-of-materials.md);
**#** numbers below are the same parts there, and **B** numbers are bench-only.

| Left out | Why the test doesn't need it | What the software does instead |
| --- | --- | --- |
| power bank, PD trigger, USB-C cable (items 9, 10, 14) | a USB-C wall adapter powers the Pi | — |
| buck, capacitor, power wire (11, 19, part of 18) | the adapter makes the 5 V, and the PTZ controller takes it from the Pi's header | — |
| battery gauge (12) | no battery to measure | `POWER_MONITOR = "none"`: no battery warnings |
| rocker switch and power latch (13, 13a) | you unplug the adapter | the Pi isn't told to shut down: stop the software first ([14](14-software-setup.md)) |
| LED ring and level shifter (7, 8) | the app shows the same state | the ring code finds nothing to drive and carries on |
| Pi-driven servos: extension leads and headers (part of 18) | the kit's own servo drive works | `SERVO_DRIVER = "arducam"`: whole-degree steps, a little less smooth |
| panel barrel jack, standoffs, screws, inserts, tripod, filament, strap, epoxy (18, 21–27) | no enclosure | the head stands on the bench on its own metal base |

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

## Power

| # | Status | Part | Qty | ≈ CAD | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| B1 |  | **Raspberry Pi 15 W USB-C power supply (5.1 V, 3 A)** | 1 | $15 | [Amazon.ca](https://www.amazon.ca/s?k=raspberry+pi+4+official+usb-c+power+supply) | powers everything: the Pi, and through its header the PTZ controller. The official one, or another 5.1 V 3 A adapter: a phone charger that sags under the motors browns the Pi out ([wiring](12-wiring.md#why-this-works-on-the-bench-and-not-in-the-full-build)) |

## Wiring

| # | Status | Part | Qty | ≈ CAD | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| B2 | A | Female-to-female jumper wires (Dupont), 20 cm (optional) | 6 | $5 (pack) | [Amazon.ca](https://www.amazon.ca/s?k=female+to+female+dupont+jumper+wires) | spares only. The Arducam kit's 6-wire cable runs from the PTZ controller straight onto the Pi's header ([wiring](12-wiring.md#connections)); these stand in for it if a wire is too short or its end is a bare lead |

**Tools you also need:** none for the wiring. A multimeter helps if
something doesn't work.

## Totals (CAD)

| | ≈ CAD |
| --- | --- |
| New for the bench (B1), if you don't already have it; B2 only if the kit's cable won't do | **≈ $15** |
| Already owned (items 1–4) | — |

The adapter stays on the bench: the full build runs off its power bank,
through the buck ([wiring](../setup/12-wiring.md)).
