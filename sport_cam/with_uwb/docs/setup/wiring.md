# Wiring guide

Every electrical connection in the camera and the tag, in the order you make
them. The [assembly guide](assembly/index.html) tells you *when* in the build
each one happens, and links back here.

**Schematics**, if you want the picture first:

| Diagram | Shows |
| --- | --- |
| [Interactive wiring schematic](../../schematics/interactive/index.html) | the whole system as one clickable graph. Open it in a browser or from `npm run docs` |
| [Head schematic](../images/schematic-head.png) | every signal into and out of the Pi |
| [Power tree](../images/power-tree.png) | the bank → 12 V → 5 V chain and what hangs off it |
| [Wearable schematic](../images/schematic-wearable.png) | the tag, which has no wiring of its own |

The design reasons behind each connection are in
[03 — Electronics](../../../docs/03-electronics.md).

## Before you start

**Tools:** soldering iron, multimeter, heat-shrink, a **4 A dummy load** (a
power resistor or electronic load) for setting the buck, and a USB-C PD bank
for testing the trigger.

**Wire:** 18 AWG silicone for the 12 V and 5 V power runs (the 5 V rail
carries up to 4 A); 22 AWG or Dupont leads for signals (BOM item 18).

**Rules:**
- **One ground.** Every ground in the camera meets at the buck's output
  negative. A signal with no shared ground is not a signal.
- **The Pi's GPIO header powers nothing.** The PTZ controller, the ring and
  the level shifter all take 5 V from the buck. The header carries signals,
  plus 3.3 V for the gauge.
- **Set the buck before anything is connected to it** (step 1).

## Connection list

Pi pin numbers are physical header pins. Pin 1 is at the end of the header
away from the USB ports, and its pad is square.

### Power — 12 V side

| # | From | To | Wire | Notes |
| --- | --- | --- | --- | --- |
| P1 | Power bank USB-C | PD trigger USB-C | 30 cm C-to-C cable (BOM 14) | must be a full C-to-C cable; a charge-only or A-to-C cable leaves the trigger at 5 V |
| P2 | PD trigger **+12 V** | rocker switch | 18 AWG | the switch breaks the positive line only |
| P3 | rocker switch | gauge **VIN+** (INA260; **IN+** on an INA226) | 18 AWG | the gauge sits in series on the positive line, or it measures nothing |
| P4 | gauge **VIN−** (**IN−**) | buck **IN+** | 18 AWG | |
| P5 | PD trigger **GND** | buck **IN−** | 18 AWG | |

### Power — 5 V rail

| # | From | To | Wire | Notes |
| --- | --- | --- | --- | --- |
| R1 | buck **OUT+ / OUT−** | 470 µF capacitor | — | across the output, **stripe (−) to OUT−** |
| R2 | buck OUT+ / OUT− | USB-C pigtail → Pi 4 USB-C | 18 AWG, short | the Pi's power input. ≈ 1.2 A average, 2 A peaks |
| R3 | buck OUT+ / OUT− | Arducam PTZ controller **5V / GND** | 18–22 AWG | not the Pi's 5 V pin: two stalled servos draw ≈ 0.7 A |
| R4 | buck OUT+ / OUT− | WS2812B ring **5V / GND** | 22 AWG | ≈ 1 A at full white; ≈ 0.45 A at the `LED_BRIGHTNESS = 0.45` the code uses |
| R5 | buck OUT+ / OUT− | 74AHCT125 **VCC (pin 14) / GND (pin 7)** | 22 AWG | |
| R6 | buck OUT+ / OUT− | panel barrel jack (−Y wall) | 22 AWG | optional 5 V service tap, centre positive |

The pigtail (R2) carries ground into the Pi, so the Pi's GPIO ground and the
rail are already one net. No separate ground wire to the header is needed.

### I2C bus — Pi GPIO 2/3

Two devices share it: the PTZ controller at **0x0C** and the gauge at
**0x40**.

| # | From | To | Notes |
| --- | --- | --- | --- |
| I1 | Pi **pin 3** (GPIO2, SDA) | PTZ controller **SDA** and gauge **SDA** | |
| I2 | Pi **pin 5** (GPIO3, SCL) | PTZ controller **SCL** and gauge **SCL** | |
| I3 | Pi **pin 1** (3.3 V) | gauge **VCC** | 3.3 V, not 5 V: the breakout's pull-ups go to its VCC, and 5 V on SDA/SCL can damage the Pi |
| I4 | Pi **pin 9** (GND) | gauge **GND** | |

No gauge? Leave out I1–I4 at the gauge end, wire the 12 V straight through
(P3 to P4), and set `POWER_MONITOR = "none"`.

### LED ring — SPI through the level shifter

| # | From | To | Notes |
| --- | --- | --- | --- |
| L1 | Pi **pin 19** (GPIO10, SPI0 MOSI) | 74AHCT125 **1A (pin 2)** | 3.3 V data in |
| L2 | 74AHCT125 **1Y (pin 3)** | ring **DIN** | 5 V data out. Keep it short |
| L3 | 74AHCT125 **1OE (pin 1)** | GND | the enable is active-low: tied low, the gate is always on |
| L4 | 74AHCT125 **2A, 3A, 4A** (pins 5, 9, 12) and **2OE, 3OE, 4OE** (pins 4, 10, 13) | GND | unused gates; floating inputs oscillate |

Use the ring's **DIN** pad, not DOUT. The arrows printed on the ring point
away from DIN.

### Camera, PTZ and anchors — plug-in connections

| # | From | To | Notes |
| --- | --- | --- | --- |
| C1 | camera ribbon (15-pin, from the Arducam kit) | Pi **CSI** connector | silver contacts **toward the HDMI ports**; lift the latch, insert fully, press the latch down. Leave ≈ 80 mm of slack coiled under the lid |
| C2 | PTZ controller's servo and lens leads | as fitted in the Arducam kit | factory-wired; only R3, I1 and I2 are yours |
| U1 | anchor **A1** (arm, +Y) | Pi USB-A, via a 50 cm extension | the **data** anchor: shows up as `/dev/ttyUSB0` |
| U2 | anchor **A2** (arm, −Y) | Pi USB-A, via a 50 cm extension | power only |
| U3 | anchor **A3** (mast) | Pi USB-A, via a 50 cm extension | power only. Tie it down the dowel with slack at the foot so the mast can be pulled |

A1 is the data anchor by convention; not A3, whose cable is the longest. Any
anchor works: the tag broadcasts each RangeData frame to all of them, and the
one on USB prints it (ULA1 manual §5–6, "monitoring mode"). Confirm it streams
`mc 07 …` frames ([software setup, step 5b](software_setup.md#5-bench-checks-motion-and-radios)).

### Wearable tag

| # | From | To | Notes |
| --- | --- | --- | --- |
| W1 | tag ULA1 USB-A plug | small USB bank (2 500 mAh) | that is the whole circuit ([schematic](../images/schematic-wearable.png)) |

## Pi header, pins used

```
  I3 gauge VCC    3.3V  [ 1] [ 2]  5V     ← 5 V pins: not used, nothing is powered from the header
  I1 SDA         GPIO2  [ 3] [ 4]  5V
  I2 SCL         GPIO3  [ 5] [ 6]  GND
                        [ 7] [ 8]
  I4 gauge GND     GND  [ 9] [10]
                        ...
                        [17] [18]
  L1 ring data  GPIO10  [19] [20]  GND
```

## Wiring order, with checks

Each step points at the assembly-guide step it belongs to.

1. **Set the buck, alone** ([assembly: power](assembly/index.html#power)).
   Feed it 12 V from a bench supply or the trigger. Put the 4 A dummy load on
   the output and trim it to **5.1 V under load**. Open-circuit voltage tells
   you nothing: a unit that reads 5.1 V unloaded can sag to 4.8 V and brown
   the Pi out.
2. **Set the trigger to 12 V** (solder jumper or resistor, per its
   silkscreen). Check it with a meter on the real bank and the real cable
   (P1).
3. **Build the 12 V chain**, P2–P5, and fit the capacitor (R1). **Check:**
   switch on and measure **12 V** at the buck input and **5.1 V** at its
   output, with nothing else connected.
4. **5 V rail out to the Pi** (R2) ([assembly: Pi](assembly/index.html#pi)).
   **Check:** before plugging in the Pi, measure **5.0–5.1 V** at the pigtail
   end, correct polarity. Then boot the Pi.
5. **Gauge on the bus** (I1–I4). **Check:** `i2cdetect -y 1` shows **40**.
6. **LED ring** (R4, R5, L1–L4)
   ([assembly: LED](assembly/index.html#led)). **Check:** the ring cycles
   blue, green and red. A ring that stays dark usually has its data on DOUT
   or a floating 1OE.
7. **PTZ controller and camera** (R3, I1, I2, C1, C2) — when the lid goes on
   ([assembly: lid on](assembly/index.html#lid-on)). **Check:**
   `i2cdetect -y 1` shows **0c** and **40**; `rpicam-hello -t 2000` shows a
   picture.
8. **Anchors** (U1–U3)
   ([assembly: arms](assembly/index.html#arms),
   [mast](assembly/index.html#mast)). **Check:**
   `ls /dev/ttyUSB*` shows `/dev/ttyUSB0`.
9. **Dress the cables** ([assembly: cabling](assembly/index.html#cabling)).
   Sweep both axes by hand to their limits and watch the ribbon and leads.
   Nothing may hang where a tripod leg folds or reach the pan axis.

Then carry on with the [software setup](software_setup.md).

## If something is wrong

| Symptom | Likely wire | Fix |
| --- | --- | --- |
| Pi reboots under load, or shows a lightning bolt | R2, or the buck setting | re-trim to 5.1 V **under load**; shorten R2 and keep it 18 AWG |
| Trigger stays at 5 V | P1 | use a full USB-C to USB-C cable; check the bank has a 12 V PD profile |
| `0c` missing from `i2cdetect` | R3 or I1/I2 | PTZ controller unpowered, or SDA/SCL swapped |
| `40` missing | I1–I4 | gauge VCC or GND, or swapped SDA/SCL. Or run without it: `POWER_MONITOR = "none"` |
| Ring dark | L1–L4, R4, R5 | data on DOUT, 1OE not grounded, or the shifter unpowered |
| Ring flickers random colours | L2, L4 | long data lead, or unused shifter inputs left floating |
| No `/dev/ttyUSB0` | U1 | the data anchor is not plugged into the Pi, or its extension is not seated |
| Gauge reads 0 W while the camera runs | P3/P4 | the gauge is wired in parallel or on the ground line, not in series on 12 V+ |

The full bench checklist is in
[10 — Verification](../10-verification.md#on-the-bench-before-the-first-session).
