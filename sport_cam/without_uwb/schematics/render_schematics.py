#!/usr/bin/env python3
"""Render electrical schematics for SportCam with schemdraw → docs/without_uwb/images/*.png.

Usage:  python3 schematics/render_schematics.py
"""
import os

import schemdraw
import schemdraw.elements as elm

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "without_uwb", "images")
os.makedirs(OUT, exist_ok=True)


def pin(name, side, slot, label=None):
    return elm.IcPin(name=name, side=side, slot=slot, anchorname=label or name)


def save(d, name):
    d.save(os.path.join(OUT, name), dpi=150)
    print("wrote", name)


# ----------------------------------------------------------------------------
# Camera unit schematic — everything lives on the Pi now
# ----------------------------------------------------------------------------
def head_schematic():
    """Signals only — the power tree (docs/without_uwb/images/power-tree.png) covers rails."""
    with schemdraw.Drawing(show=False) as d:
        d.config(fontsize=11)
        pi = d.add(elm.Ic(
            pins=[
                pin("PWM0 G12", "left", "6/6", "PWMPAN"),
                pin("PWM1 G13", "left", "5/6", "PWMTILT"),
                pin("SPI MOSI G10", "left", "4/6", "MOSI"),
                pin("HOLD G17", "left", "3/6", "HOLD"),
                pin("SENSE G27", "left", "2/6", "SENSE"),
                pin("USB-C 5V", "left", "1/6", "USBC"),
                pin("CSI", "right", "4/4"),
                pin("SDA G2", "right", "3/4", "SDA"),
                pin("SCL G3", "right", "2/4", "SCL"),
                pin("GND", "right", "1/4", "GND2"),
            ],
            edgepadW=1.8, edgepadH=1.4, pinspacing=1.5,
        ).label("Raspberry Pi 4 — the whole camera unit", "bottom", ofst=(0, -0.5), fontsize=10))

        cam = d.add(elm.Ic(
            pins=[pin("CSI", "left", "2/2"), pin("GND", "left", "1/2", "GND")],
            edgepadW=1.4, edgepadH=0.9, pinspacing=1.3,
        ).at((11.0, pi.CSI[1])).anchor("CSI").label("Arducam IMX477\n+ motorized zoom lens", "top", ofst=(0, 0.35), fontsize=10))
        d.add(elm.Wire("-").at(pi.CSI).to(cam.CSI).label("15-pin FFC", "top", fontsize=9))
        d.add(elm.Wire("|-").at(pi.GND2).to(cam.GND))

        ptz = d.add(elm.Ic(
            pins=[
                pin("SDA", "left", "2/2"),
                pin("SCL", "left", "1/2"),
                pin("zoom motor  0x00", "right", "2/2", "ZOOM"),
                pin("focus motor  0x01", "right", "1/2", "FOCUS"),
            ],
            edgepadW=4.0, edgepadH=1.0, pinspacing=1.3,
            at=(11.0, -4.2),
        ).label("Arducam PTZ controller — I2C 0x0C, lens only\n(5 V from the rail, not the GPIO header)",
                "bottom", ofst=(0, -0.5), fontsize=10))
        d.add(elm.Wire("-|").at(pi.SDA).to(ptz.SDA))
        d.add(elm.Wire("-|").at(pi.SCL).to(ptz.SCL).label("I2C", "top", fontsize=9))

        d.add(elm.Line().at(pi.MOSI).left(5)
              .label("SPI0 MOSI → 74AHCT125 → DIN", "top", fontsize=8.5))
        d.add(elm.Dot(open=True).label("WS2812B ring ×16\n(SPI, so nothing runs as root)",
                                       "left", fontsize=9))

        d.add(elm.Line().at(pi.HOLD).left(5)
              .label("HOLD → latch: power on until halted", "top", fontsize=8.5))
        d.add(elm.Dot(open=True))
        d.add(elm.Line().at(pi.SENSE).left(5)
              .label("SENSE ← rocker switch, 2.8 V", "top", fontsize=8.5))
        d.add(elm.Dot(open=True).label("power latch\n(12 V, docs/04)", "left", fontsize=9))

        d.add(elm.Vdd().at(pi.USBC).label("+5 V rail (see power tree)", fontsize=9))

        # Pan and tilt: the Pi's hardware PWM, through the shifter's spare
        # gates, straight to the servos (docs/04, "Servo drive").
        d.add(elm.Line().at(pi.PWMPAN).left(5)
              .label("hardware PWM → 74AHCT125 gate 2", "top", fontsize=8.5))
        d.add(elm.Dot(open=True).label("pan servo\n(5 V from the rail)", "left", fontsize=9))
        d.add(elm.Line().at(pi.PWMTILT).left(5)
              .label("hardware PWM → 74AHCT125 gate 3", "top", fontsize=8.5))
        d.add(elm.Dot(open=True).label("tilt servo\n(5 V from the rail)", "left", fontsize=9))
    save(d, "schematic-head.png")


if __name__ == "__main__":
    head_schematic()
