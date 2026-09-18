#!/usr/bin/env python3
"""Render electrical schematics for SportCam with schemdraw → docs/images/*.png.

Usage:  python3 schematics/render_schematics.py
"""
import os

import schemdraw
import schemdraw.elements as elm

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "images")
os.makedirs(OUT, exist_ok=True)


def pin(name, side, slot, anchor=None):
    return elm.IcPin(name=name, side=side, slot=slot, anchorname=anchor or name)


def save(d, name):
    d.save(os.path.join(OUT, name), dpi=150)
    print("wrote", name)


# ----------------------------------------------------------------------------
# Base controller schematic
# ----------------------------------------------------------------------------
def base_schematic():
    with schemdraw.Drawing(show=False) as d:
        d.config(fontsize=11)
        esp = d.add(elm.Ic(
            pins=[
                pin("5V", "left", "3/3", "VIN"),
                pin("GND", "left", "2/3"),
                pin("EN", "left", "1/3"),
                pin("G25 STEP", "right", "5/5", "STEP"),
                pin("G26 DIR", "right", "4/5", "DIR"),
                pin("G27 nEN", "right", "3/5", "NEN"),
                pin("G17 UART", "right", "2/5", "UART"),
                pin("G18 LED", "right", "1/5", "LED"),
            ],
            edgepadW=1.2, edgepadH=0.6, pinspacing=1.1,
        ).label("ESP32 DevKitC (base ctrl)", "bottom", ofst=(0, -0.4), fontsize=10))
        tmc = d.add(elm.Ic(
            pins=[
                pin("STEP", "left", "5/5", "STEP"),
                pin("DIR", "left", "4/5", "DIR"),
                pin("nEN", "left", "3/5", "NEN"),
                pin("PDN/UART", "left", "2/5", "UART"),
                pin("GND", "left", "1/5", "GND"),
                pin("VM 12V", "top", "1/1", "VM"),
                pin("A1", "right", "4/4"),
                pin("A2", "right", "3/4"),
                pin("B1", "right", "2/4"),
                pin("B2", "right", "1/4"),
            ],
            edgepadW=1.1, edgepadH=0.5, pinspacing=1.1,
            at=(8.0, 0),
        ).label("TMC2209 stepper driver", "bottom", ofst=(0, -0.4), fontsize=10))
        d.add(elm.Wire("-").at(esp.STEP).to(tmc.STEP))
        d.add(elm.Wire("-").at(esp.DIR).to(tmc.DIR))
        d.add(elm.Wire("-").at(esp.NEN).to(tmc.NEN))
        d.add(elm.Wire("-").at(esp.UART).to(tmc.UART).label("115200 8N1", "bottom", fontsize=9))

        motor = d.add(elm.Ic(
            pins=[
                pin("A1", "left", "4/4"),
                pin("A2", "left", "3/4"),
                pin("B1", "left", "2/4"),
                pin("B2", "left", "1/4"),
            ],
            edgepadW=0.8, edgepadH=0.4, pinspacing=1.1,
            at=(14.0, 0),
        ).label("NEMA17 pan stepper", "bottom", ofst=(0, -0.4), fontsize=10))
        for p in ("A1", "A2", "B1", "B2"):
            d.add(elm.Wire("-").at(getattr(tmc, p)).to(getattr(motor, p)))

        led = d.add(elm.Ic(
            pins=[
                pin("DIN", "left", "3/3"),
                pin("5V", "left", "2/3", "V5"),
                pin("GND", "left", "1/3", "GND"),
            ],
            edgepadW=0.9, edgepadH=0.4, pinspacing=1.1,
            at=(8.0, -5.0),
        ).label("WS2812B ring ×16", "bottom", ofst=(0, -0.4), fontsize=10))
        d.add(elm.Resistor().at(esp.LED).to(led.DIN).label("330 Ω", fontsize=9))

        d.add(elm.Line().at(tmc.VM).up().length(0.8).label("+12 V", "right"))
        d.add(elm.Vdd().at(esp.VIN).label("+5 V (buck #1)", fontsize=9))
        d.add(elm.Vdd().at(led.V5).label("+5 V", fontsize=9))
        d.add(elm.Ground().at(tmc.GND))
        d.add(elm.Ground().at(esp.GND))
        d.add(elm.Ground().at(led.GND))
    save(d, "schematic-base.png")


# ----------------------------------------------------------------------------
# Head unit schematic
# ----------------------------------------------------------------------------
def head_schematic():
    with schemdraw.Drawing(show=False) as d:
        d.config(fontsize=11)
        pi = d.add(elm.Ic(
            pins=[
                pin("USB-C 5V", "left", "4/4", "USBC"),
                pin("GND", "left", "3/4", "GND"),
                pin("USB A1", "left", "2/4", "USBA1"),
                pin("USB A2", "left", "1/4", "USBA2"),
                pin("CSI", "right", "6/6"),
                pin("SDA G2", "right", "5/6", "SDA"),
                pin("SCL G3", "right", "4/6", "SCL"),
                pin("PWM G18", "right", "3/6", "PWM"),
                pin("5V pin", "right", "2/6", "V5"),
                pin("GND2", "right", "1/6", "GND2"),
            ],
            edgepadW=1.3, edgepadH=0.8, pinspacing=1.1,
        ).label("Raspberry Pi 5 (head)", "bottom", ofst=(0, -0.4), fontsize=10))
        cam = d.add(elm.Ic(
            pins=[
                pin("CSI", "left", "4/4"),
                pin("SDA", "left", "3/4"),
                pin("SCL", "left", "2/4"),
                pin("GND", "left", "1/4", "GND"),
            ],
            edgepadW=1.0, edgepadH=0.5, pinspacing=1.1,
            at=(9.0, 2.0),
        ).label("Arducam IMX219 + motorized zoom lens", "top", ofst=(0, 0.3), fontsize=10))
        d.add(elm.Wire("-").at(pi.CSI).to(cam.CSI).label("22-pin FFC", "top", fontsize=9))
        d.add(elm.Wire("-").at(pi.SDA).to(cam.SDA))
        d.add(elm.Wire("-").at(pi.SCL).to(cam.SCL).label("I2C lens ctrl (0x0C)", "bottom", fontsize=9))
        d.add(elm.Wire("|-").at(pi.GND2).to(cam.GND))

        servo = d.add(elm.Ic(
            pins=[
                pin("SIG", "left", "3/3"),
                pin("5V", "left", "2/3", "V5"),
                pin("GND", "left", "1/3", "GND"),
            ],
            edgepadW=0.9, edgepadH=0.4, pinspacing=1.1,
            at=(9.0, -4.0),
        ).label("DS3225 270° tilt servo", "bottom", ofst=(0, -0.4), fontsize=10))
        d.add(elm.Wire("|-").at(pi.PWM).to(servo.SIG).label("50 Hz PWM", "bottom", ofst=(0, -0.3), fontsize=9))
        d.add(elm.Vdd().at(servo.V5).label("+5 V servo rail\n(buck #3)", fontsize=8))
        d.add(elm.Ground().at(servo.GND))

        for slot, ypos, name in (("USBA1", 1.6, "UWB anchor A1\nESP32+DW1000"),
                                 ("USBA2", -1.8, "UWB anchor A2\nESP32+DW1000")):
            uwb = d.add(elm.Ic(
                pins=[pin("USB", "right", "1/1")],
                edgepadW=0.9, edgepadH=0.4, pinspacing=1.1,
                at=(-6.0, ypos),
            ).label(name, "left", ofst=(-0.3, 0), fontsize=10))
            d.add(elm.Wire("-").at(uwb.USB).to(getattr(pi, slot)).label("USB (5V + serial)", "top", fontsize=8))

        buck = d.add(elm.Ic(
            pins=[
                pin("12V IN", "left", "2/2", "VIN"),
                pin("GND", "left", "1/2", "GNDI"),
                pin("5V 5A", "right", "2/2", "VOUT"),
                pin("GNDo", "right", "1/2", "GNDO"),
            ],
            edgepadW=0.9, edgepadH=0.4, pinspacing=1.1,
            at=(-6.0, -5.2),
        ).label("Buck #2 12→5 V 5 A (on head)", "bottom", ofst=(0, -0.4), fontsize=10))
        d.add(elm.Line().at(buck.VIN).left().length(1.4).label("from slip ring", "left", fontsize=9))
        d.add(elm.Wire("|-").at(buck.VOUT).to(pi.USBC).label("USB-C 5 A", "bottom", fontsize=9))
        d.add(elm.Wire("|-").at(buck.GNDO).to(pi.GND))
    save(d, "schematic-head.png")


# ----------------------------------------------------------------------------
# Wearable schematic
# ----------------------------------------------------------------------------
def wearable_schematic():
    with schemdraw.Drawing(show=False) as d:
        d.config(fontsize=11)
        tag = d.add(elm.Ic(
            pins=[
                pin("BAT+", "left", "4/4", "BAT"),
                pin("GND", "left", "3/4", "GND"),
                pin("G13 BTN", "left", "2/4", "BTN"),
                pin("G2 LED", "left", "1/4", "LED"),
                pin("SPI bus → DW1000 (on-board)", "right", "1/1", "SPI"),
            ],
            edgepadW=1.2, edgepadH=0.6, pinspacing=1.1,
        ).label("ESP32-UWB tag", "bottom", ofst=(0, -0.4), fontsize=10))
        chg = d.add(elm.Ic(
            pins=[
                pin("USB-C", "left", "2/2", "USB"),
                pin("GNDi", "left", "1/2", "GNDI"),
                pin("B+", "right", "2/2", "BP"),
                pin("B-", "right", "1/2", "BM"),
            ],
            edgepadW=0.9, edgepadH=0.4, pinspacing=1.1,
            at=(-10.0, 1.6),
        ).label("TP4056 charger + protect", "bottom", ofst=(0, -0.4), fontsize=10))
        bat = d.add(elm.Battery().at((-6.2, 3.4)).right().label("LiPo 3.7 V 1000 mAh", "top", fontsize=9))
        d.add(elm.Wire("-|").at(chg.BP).to(bat.start))
        d.add(elm.Wire("-|").at(bat.end).to(tag.BAT))
        d.add(elm.Wire("-|").at(chg.BM).to(tag.GND))

        btn = d.add(elm.Button().endpoints((-6.2, -3.0), (-4.6, -3.0)).label("pair / record\nbutton", "bottom", fontsize=9))
        d.add(elm.Wire("-|").at(btn.end).to(tag.BTN))
        d.add(elm.Ground().at(btn.start))

        d.add(elm.Resistor().at(tag.LED).left().label("220 Ω", "top", fontsize=9))
        d.add(elm.LED().left().label("status LED", "bottom", fontsize=9))
        d.add(elm.Ground())
    save(d, "schematic-wearable.png")


if __name__ == "__main__":
    base_schematic()
    head_schematic()
    wearable_schematic()
