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
# Camera unit schematic — everything lives on the Pi now
# ----------------------------------------------------------------------------
def head_schematic():
    """Signals only — the power tree (docs/images/power-tree.png) covers rails."""
    with schemdraw.Drawing(show=False) as d:
        d.config(fontsize=11)
        pi = d.add(elm.Ic(
            pins=[
                pin("USB A1", "left", "7/7", "USBA1"),
                pin("USB A2", "left", "6/7", "USBA2"),
                pin("USB A3", "left", "5/7", "USBA3"),
                pin("SPI MOSI G10", "left", "4/7", "MOSI"),
                pin("HOLD G17", "left", "3/7", "HOLD"),
                pin("SENSE G27", "left", "2/7", "SENSE"),
                pin("USB-C 5V", "left", "1/7", "USBC"),
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
            at=(11.0, 3.6),
        ).label("Arducam IMX477\n+ motorized zoom lens", "top", ofst=(0, 0.35), fontsize=10))
        d.add(elm.Wire("-").at(pi.CSI).to(cam.CSI).label("15-pin FFC", "top", fontsize=9))
        d.add(elm.Wire("|-").at(pi.GND2).to(cam.GND))

        ptz = d.add(elm.Ic(
            pins=[
                pin("SDA", "left", "4/4"),
                pin("SCL", "left", "3/4"),
                pin("pan servo  0x05", "right", "4/4", "PAN"),
                pin("tilt servo  0x06", "right", "3/4", "TILT"),
                pin("zoom motor  0x00", "right", "2/4", "ZOOM"),
                pin("focus motor  0x01", "right", "1/4", "FOCUS"),
            ],
            edgepadW=1.5, edgepadH=1.0, pinspacing=1.3,
            at=(11.0, -4.2),
        ).label("Arducam PTZ controller — I2C 0x0C\n(5 V from the rail, not the GPIO header)",
                "bottom", ofst=(0, -0.5), fontsize=10))
        d.add(elm.Wire("-|").at(pi.SDA).to(ptz.SDA))
        d.add(elm.Wire("-|").at(pi.SCL).to(ptz.SCL).label("I2C", "top", fontsize=9))

        # Off-board connections as labelled stubs: everything here is a
        # plug-in module, so a straight lead with its name reads better than
        # a box with one pin.
        for slot, name in (("USBA1", "ULA1 anchor A1 — data"),
                           ("USBA2", "ULA1 anchor A2 — power only"),
                           ("USBA3", "ULA1 anchor A3 (mast) — power only")):
            d.add(elm.Line().at(getattr(pi, slot)).left(5)
                  .label("USB — 5 V + serial", "top", fontsize=8.5))
            d.add(elm.Dot(open=True).label(name, "left", fontsize=9))
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
    save(d, "schematic-head.png")


# ----------------------------------------------------------------------------
# Wearable schematic
# ----------------------------------------------------------------------------
def wearable_schematic():
    """The tag is a ULA1 plugged into a small USB bank — no wiring of its own."""
    with schemdraw.Drawing(show=False) as d:
        d.config(fontsize=11)
        tag = d.add(elm.Ic(
            pins=[
                pin("USB-A plug", "left", "1/1", "USB"),
                pin("DWM1000", "right", "1/1", "SPI"),
            ],
            edgepadW=3.0, edgepadH=0.8, pinspacing=1.2,
        ).label("ULA1 tag (ESP32 + DWM1000)\nfirmware: RTLS_Tag, 3 anchors", "bottom", ofst=(0, -0.4), fontsize=10))
        d.add(elm.Line().at(tag.USB).left(4).label("5 V + GND, plugs straight in", "top", fontsize=9))
        d.add(elm.Dot(open=True).label("USB bank, 2 500 mAh\n(USB-A socket)", "left", fontsize=9))
        d.add(elm.Line().at(tag.SPI).right(1.2))
        d.add(elm.Antenna().label("UWB", "right", fontsize=9))
    save(d, "schematic-wearable.png")


if __name__ == "__main__":
    head_schematic()
    wearable_schematic()
