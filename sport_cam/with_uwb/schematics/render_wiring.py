#!/usr/bin/env python3
"""Render the full build, every part wired up, top-down, and its interactive page.

  → docs/with_uwb/images/full-wiring.png               a picture to copy, wire for wire
  → with_uwb/schematics/interactive/wiring.html        the same picture beside the
                                                        connection table: click a row
                                                        to light up its wire

Each lead is tagged with its number in docs/with_uwb/setup/12-wiring.md, and
the table below (CONNECTIONS) is that guide's connection list. Not to scale;
parts are placed for clear wiring, not where they sit in the enclosure.

Usage:  python3 with_uwb/schematics/render_wiring.py
"""
import html
import io
import json
import math
import os
import re
from contextlib import contextmanager

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle, Wedge

from render_bench import (BGBOX, BLACK, GOLD, GREY, INK, METAL, PCB_DARK, RED, RIBBON, SCL, SDA, USB,
                          along, board, camera, note, pi4, pin_end, tag, wire)

BUILD = "with_uwb"
UWB = True

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = os.path.join(HERE, "..", "..", "docs", BUILD, "images", "full-wiring.png")
PAGE = os.path.join(HERE, "interactive", "wiring.html")

V12 = "#c0392b"      # 12 V side, before the buck
SIGNAL = "#7d3cbd"   # latch and Pi control lines
DATA = "#16a085"     # ring data
PWM = "#e67e22"      # servo PWM
PERF = "#c8a26b"     # perfboard
TRACE = "#9aa3b2"    # perfboard ground strip

plt.rcParams["svg.fonttype"] = "none"   # text stays text in the page
plt.rcParams["svg.hashsalt"] = "sportcam"


# ----------------------------------------------------------------------------
# The connection list: docs/<build>/setup/12-wiring.md, one row per lead.
# ----------------------------------------------------------------------------
CONNECTIONS = [
    ("Power, 12 V side", [
        ("P1", "Power bank USB-C", "PD trigger USB-C", "30 cm C-to-C cable (BOM 14). A charge-only or A-to-C cable leaves the trigger at 5 V"),
        ("P2", "PD trigger +12 V", "power latch IN", "18 AWG. The latch switches the positive line only"),
        ("P3", "power latch OUT", "gauge VIN+ (IN+ on an INA226)", "18 AWG. The gauge sits in series on the positive line"),
        ("P4", "gauge VIN− (IN−)", "buck IN+", "18 AWG"),
        ("P5", "PD trigger GND", "buck IN−", "18 AWG"),
        ("P6", "power latch GND", "buck IN−", "22 AWG. The latch only references its transistors to it"),
    ]),
    ("Switch and Pi signals", [
        ("S1", "latch IN (+12 V, always live)", "rocker terminal 1", "22 AWG, signal only: under 1 mA"),
        ("S2", "rocker terminal 2", "latch SW", "22 AWG"),
        ("S3", "latch HOLD", "Pi pin 11 (GPIO17)", "Dupont. The Pi's \"keep the power on\" line"),
        ("S4", "latch SENSE", "Pi pin 13 (GPIO27)", "Dupont. 2.8 V: check it's under 3.3 V before plugging it in"),
    ]),
    ("Power, 5 V rail", [
        ("R1", "buck OUT+ / OUT−", "470 µF capacitor", "across the output, stripe (−) to OUT−"),
        ("R2", "buck OUT+ / OUT−", "USB-C pigtail → Pi USB-C", "18 AWG, short. ≈ 1.2 A average, 2 A peaks"),
        ("R3", "buck OUT+ / OUT−", "PTZ controller 5V / GND", "18–22 AWG. Not the Pi's 5 V pin"),
        ("R4", "buck OUT+ / OUT−", "LED ring 5V / GND", "22 AWG"),
        ("R5", "buck OUT+ / OUT−", "74AHCT125 VCC (pin 14) / GND (pin 7)", "22 AWG"),
        ("R6", "buck OUT+ / OUT−", "panel barrel jack", "22 AWG. Optional 5 V service tap, centre positive"),
        ("R7", "buck OUT+ / OUT−", "servo headers + / −", "20–22 AWG. ≈ 0.7 A when both servos stall"),
    ]),
    ("I2C bus", [
        ("I1", "Pi pin 3 (GPIO2, SDA)", "PTZ controller SDA and gauge SDA", "PTZ controller 0x0C, gauge 0x40"),
        ("I2", "Pi pin 5 (GPIO3, SCL)", "PTZ controller SCL and gauge SCL", ""),
        ("I3", "Pi pin 1 (3.3 V)", "gauge VCC", "3.3 V, not 5 V: the gauge's pull-ups go to its VCC"),
        ("I4", "Pi pin 9 (GND)", "gauge GND", ""),
    ]),
    ("LED ring", [
        ("L1", "Pi pin 19 (GPIO10, SPI0 MOSI)", "74AHCT125 1A (pin 2)", "3.3 V data in"),
        ("L2", "74AHCT125 1Y (pin 3)", "ring DIN", "5 V data out. Keep it short. DIN, not DOUT"),
        ("L3", "74AHCT125 1OE (pin 1)", "GND", "active-low enable, tied low"),
        ("L4", "74AHCT125 4A (pin 12) and 4OE (pin 13)", "GND", "the unused gate: a floating input oscillates"),
    ]),
    ("Servos", [
        ("M1", "Pi pin 32 (GPIO12, PWM0)", "74AHCT125 2A (pin 5)", "pan signal, 3.3 V"),
        ("M2", "Pi pin 33 (GPIO13, PWM1)", "74AHCT125 3A (pin 9)", "tilt signal, 3.3 V"),
        ("M3", "74AHCT125 2OE (pin 4) and 3OE (pin 10)", "GND", "active-low enables, tied low"),
        ("M4", "74AHCT125 2Y (pin 6)", "pan header S", "5 V pulses"),
        ("M5", "74AHCT125 3Y (pin 8)", "tilt header S", ""),
        ("M6", "both headers + and −", "the 5 V rail (R7)", "links the second header to the first"),
        ("M7", "pan and tilt servo leads", "pan and tilt headers", "off the PTZ controller. Brown/black = GND, red = +5 V"),
    ]),
    ("Camera and PTZ" + (", anchors" if UWB else ""), [
        ("C1", "camera ribbon (15-pin)", "Pi CSI connector", "silver contacts toward the HDMI ports"),
        ("C2", "PTZ controller lens leads", "zoom and focus motors", "factory-wired, as the kit came"),
    ] + ([
        ("U1", "anchor A1 (arm, +Y)", "Pi USB-A, via a 50 cm extension", "the data anchor: /dev/ttyUSB0"),
        ("U2", "anchor A2 (arm, −Y)", "Pi USB-A, via a 50 cm extension", "power only"),
        ("U3", "anchor A3 (mast)", "Pi USB-A, via a 50 cm extension", "power only"),
    ] if UWB else [])),
] + ([("Wearable tag", [
    ("W1", "tag ULA1 USB-A plug", "small USB bank (2 500 mAh)", "the whole circuit"),
])] if UWB else [])


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
@contextmanager
def conn(ax, cid):
    """Tag every artist drawn inside the block as connection `cid`, so the
    page can find the wire again."""
    before = {id(a) for a in ax.get_children()}
    yield
    for a in ax.get_children():
        if id(a) not in before:
            a.set_gid(f"w-{cid}")


def pair(ax, pts, d=(0.9, 0.9), head=((), ()), tail=((), ()), lw=2.2, label=None, at=0.5):
    """A red/black pair along `pts`, red offset by +d and black by −d. `head`
    and `tail` are (red, black) points to start from and end at, for the
    short fans onto a terminal."""
    red = [(x + d[0], y + d[1]) for x, y in pts]
    blk = [(x - d[0], y - d[1]) for x, y in pts]
    wire(ax, list(head[1]) + blk + list(tail[1]), BLACK, lw=lw)
    wire(ax, list(head[0]) + red + list(tail[0]), RED, lw=lw)
    if label:
        tag(ax, along(pts, at), label, RED)


def dot(ax, xy, color):
    ax.add_patch(Circle(xy, 0.9, fc=color, ec="white", lw=0.6, zorder=7.5))


def pad(ax, xy, name, side="left", fs=5.5, color="white"):
    """A labelled solder pad; the label sits inside the board, on `side`'s opposite."""
    ax.add_patch(Rectangle((xy[0] - 1.1, xy[1] - 1.1), 2.2, 2.2, fc=GOLD, ec=INK, lw=0.5, zorder=3.2))
    off = {"left": (2, 0, "left", "center"), "right": (-2, 0, "right", "center"),
           "top": (0, -2, "center", "top"), "bottom": (0, 2, "center", "bottom")}[side]
    ax.text(xy[0] + off[0], xy[1] + off[1], name, ha=off[2], va=off[3], fontsize=fs, color=color, zorder=3.3)
    return xy


# ----------------------------------------------------------------------------
# Parts
# ----------------------------------------------------------------------------
def ptz_ctrl(ax, x, y):
    """The PTZ controller: 5V, GND, SDA, SCL along the bottom edge (match yours
    by its labels), the lens and servo sockets along the top."""
    w, h = 40, 24
    board(ax, x, y, w, h, PCB_DARK, "Arducam PTZ controller", "I2C 0x0C", fs=8.5)
    pins = {}
    for i, n in enumerate(["5V", "GND", "SDA", "SCL"]):
        px = x + 6 + i * 4
        ax.add_patch(Rectangle((px - 0.6, y + 2), 1.2, 1.2, fc=GOLD, ec="none", zorder=3))
        ax.text(px, y + 4, n, ha="center", va="bottom", fontsize=5.5, color="white", zorder=3, rotation=90)
        pins[n] = (px, y + 2.6)
    for i, n in enumerate(["PAN", "TILT", "ZOOM", "FOCUS"]):
        px = x + 8 + i * 8
        fc = "#555b66" if n in ("PAN", "TILT") else "white"
        ax.add_patch(Rectangle((px - 2.2, y + h - 3.6), 4.4, 2.6, fc=fc, ec=INK, lw=0.6, zorder=3))
        ax.text(px, y + h - 4.3, n, ha="center", va="top", fontsize=5.5, color="white", zorder=3)
        pins[n] = (px, y + h - 1)
    note(ax, x + 8, y + h + 2.5, "PAN, TILT: empty (M7)", fs=6, color=GREY, va="bottom")
    return pins


def power_bank(ax, x, y):
    board(ax, x, y, 34, 22, "#5d6676", "Power bank (#9)", "USB-C PD, 92 Wh", fs=8)
    ax.add_patch(Rectangle((x + 34, y + 9), 2.5, 4, fc=METAL, ec=INK, lw=0.6, zorder=3))
    return (x + 36.5, y + 11)


def trigger(ax, x, y):
    board(ax, x, y, 24, 16, "#2d3e66", "PD trigger", "(#10) set to 12 V", fs=7)
    ax.add_patch(Rectangle((x - 2, y + 5), 3, 5, fc=METAL, ec=INK, lw=0.6, zorder=3))
    return {"in": (x - 2, y + 7.5), "+12V": pad(ax, (x + 24, y + 12), "+12V", "right"),
            "GND": pad(ax, (x + 24, y + 4), "GND", "right")}


def latch(ax, x, y):
    w, h = 36, 26
    board(ax, x, y, w, h, PERF, ec="#8b6a3e")
    ax.text(x + w / 2, y + 12, "Power latch (#13a)", ha="center", fontsize=7.5, fontweight="bold", color=INK, zorder=3)
    ax.text(x + w / 2, y + 8, "IRF4905 + 2 × 2N3904", ha="center", fontsize=6, color=INK, zorder=3)
    p = {
        "IN": pad(ax, (x, y + 20), "IN", "left", color=INK),
        "GND": pad(ax, (x, y + 4), "GND", "left", color=INK),
        "OUT": pad(ax, (x + w, y + 20), "OUT", "right", color=INK),
        "SW": pad(ax, (x + 10, y + h), "SW", "top", color=INK),
        "SENSE": pad(ax, (x + 20, y + h), "SENSE", "top", color=INK),
        "HOLD": pad(ax, (x + 29, y + h), "HOLD", "top", color=INK),
    }
    return p


def rocker(ax, x, y):
    board(ax, x, y, 20, 9, "#1c1c1c", "Rocker (#13)", fs=6.5, r=1)
    return {"1": pad(ax, (x + 4, y), "1", "bottom"), "2": pad(ax, (x + 16, y), "2", "bottom")}


def gauge(ax, x, y):
    w, h = 26, 18
    board(ax, x, y, w, h, "#1f3f8a")
    ax.text(x + w / 2, y + 6.5, "INA260 gauge", ha="center", fontsize=7, fontweight="bold", color="white", zorder=3)
    ax.text(x + w / 2, y + 3, "(#12) 0x40", ha="center", fontsize=6, color="white", zorder=3)
    p = {"VIN+": pad(ax, (x, y + 9), "VIN+", "left", fs=5), "VIN-": pad(ax, (x + w, y + 9), "VIN−", "right", fs=5)}
    for i, n in enumerate(["GND", "SCL", "SDA", "VCC"]):
        p[n] = pad(ax, (x + 6 + i * 4.6, y + h), n, "top", fs=4.5)
    return p


def buck(ax, x, y):
    w, h = 44, 22
    board(ax, x, y, w, h, "#2b4d7a")
    ax.text(x + 16, y + 12, "Buck 12 → 5.1 V", ha="center", fontsize=7.5, fontweight="bold", color="white", zorder=3)
    ax.text(x + 16, y + 8, "(#11) set under load", ha="center", fontsize=6, color="white", zorder=3)
    p = {"IN+": pad(ax, (x, y + 15), "IN+", "left", fs=5), "IN-": pad(ax, (x, y + 6), "IN−", "left", fs=5),
         "OUT+": pad(ax, (x + 34, y + h), "OUT+", "top", fs=5), "OUT-": pad(ax, (x + 40, y + h), "OUT−", "top", fs=5)}
    return p


def capacitor(ax, xy):
    """470 µF, standing, seen from above: a can with its stripe."""
    ax.add_patch(Circle(xy, 3.2, fc="#25386b", ec=INK, lw=0.8, zorder=6.5))
    ax.add_patch(Wedge(xy, 3.2, -50, 50, fc="#dde3ee", ec="none", zorder=6.6))
    ax.text(xy[0] - 4, xy[1], "470 µF", ha="right", va="center", fontsize=5.5, color="white", zorder=6.6)


def pigtail(ax, xy):
    """The USB-C plug of the 5 V pigtail, in the Pi's USB-C port."""
    ax.add_patch(FancyBboxPatch((xy[0] - 3, xy[1] - 8), 6, 8, boxstyle="round,pad=0,rounding_size=1",
                                fc="#2b2f36", ec=INK, lw=1, zorder=8))
    return (xy[0], xy[1] - 8)


def barrel(ax, x, y):
    ax.add_patch(FancyBboxPatch((x, y), 14, 10, boxstyle="round,pad=0,rounding_size=1.5",
                                fc="#2b2f36", ec=INK, lw=1, zorder=3))
    ax.add_patch(Circle((x + 7, y + 5), 2.5, fc="#14181f", ec=METAL, lw=1, zorder=3.1))
    note(ax, x + 16, y + 5, "barrel jack,\noptional (#18)", fs=6, va="center")
    return {"+": (x + 4, y), "-": (x + 10, y)}


def shifter(ax, x, y):
    """The 74AHCT125 on its perfboard, with the two servo headers.
    Pins 1–7 along the bottom row (pin 1 at the left, by the notch),
    14–8 along the top row, so pin 14 sits over pin 1."""
    w, h = 76, 42
    board(ax, x, y, w, h, PERF, ec="#8b6a3e")
    ax.text(x + w - 2, y + 1.5, "Shifter perfboard", ha="right", va="bottom", fontsize=7, fontweight="bold", color=INK, zorder=3)
    P = 4.0
    cx, by, ty = x + 10, y + 14, y + 24
    ax.add_patch(FancyBboxPatch((cx - 2, by + 1.6), 6 * P + 4, ty - by - 3.2, boxstyle="round,pad=0,rounding_size=0.6",
                                fc="#14181f", ec=INK, lw=0.8, zorder=3))
    ax.add_patch(Wedge((cx - 2, (by + ty) / 2), 1.2, -90, 90, fc=PERF, ec="none", zorder=3.1))
    ax.text(cx + 3 * P, (by + ty) / 2, "74AHCT125 (#8)", ha="center", va="center", fontsize=6, color="white", zorder=3.2)
    p = {}
    for i in range(7):
        p[i + 1] = (cx + i * P, by)
        p[14 - i] = (cx + i * P, ty)
    for n, (px, py) in p.items():
        ax.add_patch(Rectangle((px - 0.7, py - 0.7), 1.4, 1.4, fc=METAL, ec=INK, lw=0.4, zorder=3.3))
        ax.text(px, py + (-1.4 if py == by else 1.4), str(n), ha="center", va="top" if py == by else "bottom",
                fontsize=4.5, color=INK, zorder=3.3)
    # Ground strips, top and bottom, joined and tied to pin 7
    gb, gt = by - 6, ty + 6
    for yy in (gb, gt):
        ax.add_patch(Rectangle((cx - 3, yy - 0.6), 6 * P + 6, 1.2, fc=TRACE, ec="none", zorder=2.8))
    ax.add_patch(Rectangle((cx + 6 * P + 2.4, gb - 0.6), 1.2, gt - gb + 1.2, fc=TRACE, ec="none", zorder=2.8))
    ax.add_patch(Rectangle((p[7][0] - 0.6, gb), 1.2, by - gb, fc=TRACE, ec="none", zorder=2.8))
    p["gb"], p["gt"] = gb, gt
    # Servo headers: three pins each, S at the bottom (labelled in render())
    hdr = {}
    for name, hx in (("tilt", x + 50), ("pan", x + 62)):
        ax.add_patch(Rectangle((hx - 1.8, y + 13), 3.6, 14, fc="#14181f", ec=INK, lw=0.6, zorder=3))
        for pn, py in (("S", y + 16), ("+", y + 20), ("-", y + 24)):
            ax.add_patch(Rectangle((hx - 0.6, py - 0.6), 1.2, 1.2, fc=GOLD, ec="none", zorder=3.2))
            hdr[(name, pn)] = (hx, py)
    p.update(hdr)
    return p


def ring(ax, xy, r=17):
    ax.add_patch(Circle(xy, r, fc="#1c1c1c", ec=INK, lw=1.2, zorder=2))
    ax.add_patch(Circle(xy, r - 6, fc="white", ec=INK, lw=0.8, zorder=2.1))
    for k in range(16):
        a = 2 * math.pi * k / 16
        ax.add_patch(Rectangle((xy[0] + (r - 3) * math.cos(a) - 1.2, xy[1] + (r - 3) * math.sin(a) - 1.2),
                               2.4, 2.4, fc="#f4f1e8", ec="#888", lw=0.4, zorder=2.2))
    ax.text(xy[0], xy[1] + 1.5, "LED ring", ha="center", va="center", fontsize=7, fontweight="bold", color=INK, zorder=2.3)
    ax.text(xy[0], xy[1] - 2.5, "WS2812B (#7)", ha="center", va="center", fontsize=5.5, color=INK, zorder=2.3)
    y0 = xy[1] - r - 2.5   # the pads, on a tab below the ring
    return {"DIN": pad(ax, (xy[0] - 6, y0), "DIN", "right", fs=5, color=INK),
            "5V": pad(ax, (xy[0], y0), "5V", "bottom", fs=5),
            "GND": pad(ax, (xy[0] + 6, y0), "GND", "left", fs=5, color=INK)}


def ula1(ax, x, y, name, sub):
    """A ULA1 radio with its USB-A plug on the left."""
    board(ax, x, y - 5, 22, 10, "#1c1c1c", name, sub, fs=7, r=1)
    ax.add_patch(Rectangle((x - 4, y - 1.6), 4, 3.2, fc=METAL, ec=INK, lw=0.6, zorder=3))
    return (x - 4, y)


# ----------------------------------------------------------------------------
# The interactive page
# ----------------------------------------------------------------------------
PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>SportCam wiring, __LABEL__</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><text y='13' font-size='13'>📷</text></svg>" />
<!--
  GENERATED by __BUILD__/schematics/render_wiring.py: edit that, not this.
  The full build wired up (docs/__BUILD__/images/full-wiring.png) beside the
  connection list of docs/__BUILD__/setup/12-wiring.md. Click a row, or a
  wire, to light that connection up. Serve it with the docs viewer:

      npm run docs   → http://localhost:8090/__BUILD__/schematics/interactive/wiring.html
-->
<style>
  :root { --ink: #1a2233; --grey: #6b7486; --line: #dde2ea; --hi: #ffd400; --row: #fff7cc; }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; font-family: system-ui, sans-serif; color: var(--ink); background: #fff; }
  header { display: flex; align-items: center; gap: 12px; padding: 10px 16px; background: #1a2233; color: #fff; }
  header h1 { margin: 0; font-size: 16px; font-weight: 600; flex: 1; }
  header button { font: inherit; font-size: 13px; padding: 4px 10px; border-radius: 6px; border: 1px solid #56607a;
                  background: #2b3550; color: #fff; cursor: pointer; }
  main { display: grid; grid-template-columns: minmax(0, 1fr) 440px; height: calc(100% - 46px); }
  #pic { position: relative; overflow: hidden; background: #fff; cursor: grab; touch-action: none; }
  #pic.drag { cursor: grabbing; }
  #pic svg { width: 100%; height: 100%; display: block; }
  #pic svg text { font-family: "DejaVu Sans", system-ui, sans-serif !important; }
  #hint { position: absolute; left: 12px; bottom: 10px; font-size: 12px; color: var(--grey); background: #fffd;
          padding: 3px 8px; border-radius: 6px; pointer-events: none; }
  .wire { cursor: pointer; transition: opacity .15s; }
  svg.focus .wire { opacity: .12; }
  svg.focus .wire.on { opacity: 1; filter: drop-shadow(0 0 1.2px var(--hi)) drop-shadow(0 0 1.2px var(--hi)); }
  svg:not(.focus) .wire.peek { filter: drop-shadow(0 0 1px var(--hi)) drop-shadow(0 0 1px var(--hi)); }
  aside { border-left: 1px solid var(--line); display: flex; flex-direction: column; min-height: 0; }
  #tools { padding: 10px 12px; border-bottom: 1px solid var(--line); display: flex; gap: 8px; }
  #q { flex: 1; font: inherit; font-size: 14px; padding: 6px 9px; border: 1px solid var(--line); border-radius: 6px; }
  #list { overflow: auto; flex: 1; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th { position: sticky; top: 0; background: #f4f6fb; text-align: left; font-size: 12px; color: var(--grey);
       padding: 6px 8px; border-bottom: 1px solid var(--line); z-index: 1; }
  tr.sec td { background: #eef1f7; font-weight: 600; font-size: 12px; padding: 6px 8px; color: #3b4560; }
  tr.c td { padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  tr.c { cursor: pointer; }
  tr.c:hover td { background: #f7f9fc; }
  tr.c.on td { background: var(--row); }
  td.id { font-weight: 700; white-space: nowrap; }
  td.id span { display: inline-block; min-width: 2.2em; text-align: center; padding: 1px 5px; border-radius: 5px; color: #fff; }
  td.n { color: var(--grey); font-size: 12px; }
  @media (max-width: 900px) {
    main { grid-template-columns: 1fr; grid-template-rows: 55vh 1fr; height: auto; }
    aside { border-left: 0; border-top: 1px solid var(--line); max-height: 60vh; }
  }
</style>
</head>
<body>
<header><h1>SportCam full build, __LABEL__: wiring</h1><button id="fit" type="button">Fit</button></header>
<main>
  <div id="pic">__SVG__<div id="hint">Click a row or a wire. Drag to pan, wheel to zoom, Esc to clear.</div></div>
  <aside>
    <div id="tools"><input id="q" type="search" placeholder="Filter: R3, SDA, pin 11, gauge…" aria-label="Filter connections" /></div>
    <div id="list"><table><thead><tr><th>#</th><th>From</th><th>To</th><th>Notes</th></tr></thead><tbody id="rows"></tbody></table></div>
  </aside>
</main>
<script>
const SECTIONS = __DATA__;
const svg = document.querySelector("#pic svg");
const rows = document.getElementById("rows");
const wiresOf = (id) => svg.querySelectorAll(`.wire[data-c="${id}"]`);

for (const [title, conns] of SECTIONS) {
  rows.insertAdjacentHTML("beforeend", `<tr class="sec"><td colspan="4">${title}</td></tr>`);
  for (const [id, from, to, notes, colour] of conns) {
    const tr = document.createElement("tr");
    tr.className = "c"; tr.dataset.c = id; tr.tabIndex = 0;
    tr.innerHTML = `<td class="id"><span>${id}</span></td><td>${from}</td><td>${to}</td><td class="n">${notes}</td>`;
    tr.querySelector("span").style.background = colour;
    if (["#e0a100", "#b8bec9"].includes(colour)) tr.querySelector("span").style.color = "#1a2233";
    rows.append(tr);
  }
}

let current = null;
function select(id, scroll) {
  current = id === current ? null : id;
  svg.classList.toggle("focus", !!current);
  svg.querySelectorAll(".wire.on").forEach((g) => g.classList.remove("on"));
  rows.querySelectorAll("tr.on").forEach((r) => r.classList.remove("on"));
  if (!current) return;
  wiresOf(current).forEach((g) => { g.classList.add("on"); g.parentNode.append(g); });
  const tr = rows.querySelector(`tr[data-c="${current}"]`);
  if (tr) { tr.classList.add("on"); if (scroll) tr.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
}
rows.addEventListener("click", (e) => { const tr = e.target.closest("tr.c"); if (tr) select(tr.dataset.c); });
rows.addEventListener("keydown", (e) => {
  const tr = e.target.closest("tr.c");
  if (!tr) return;
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(tr.dataset.c); }
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    const all = [...rows.querySelectorAll("tr.c")].filter((r) => r.style.display !== "none");
    const next = all[all.indexOf(tr) + (e.key === "ArrowDown" ? 1 : -1)];
    if (next) { next.focus(); current = null; select(next.dataset.c, true); }
  }
});
rows.addEventListener("mouseover", (e) => {
  const tr = e.target.closest("tr.c");
  svg.querySelectorAll(".wire.peek").forEach((g) => g.classList.remove("peek"));
  if (tr) wiresOf(tr.dataset.c).forEach((g) => g.classList.add("peek"));
});
rows.addEventListener("mouseleave", () => svg.querySelectorAll(".wire.peek").forEach((g) => g.classList.remove("peek")));
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && current) select(current); });

document.getElementById("q").addEventListener("input", (e) => {
  const q = e.target.value.trim().toLowerCase();
  let sec = null, any = false;
  const flush = () => { if (sec) sec.style.display = any ? "" : "none"; };
  for (const tr of rows.children) {
    if (tr.classList.contains("sec")) { flush(); sec = tr; any = false; continue; }
    const hit = !q || tr.textContent.toLowerCase().includes(q);
    tr.style.display = hit ? "" : "none";
    any ||= hit;
  }
  flush();
});

// Pan and zoom by moving the viewBox; a click without a drag picks a wire
const pic = document.getElementById("pic");
const home = svg.viewBox.baseVal;
let vb = [home.x, home.y, home.width, home.height];
const show = () => svg.setAttribute("viewBox", vb.join(" "));
const toSvg = (cx, cy) => {
  const r = svg.getBoundingClientRect();
  const s = Math.max(vb[2] / r.width, vb[3] / r.height);
  return [vb[0] + vb[2] / 2 + (cx - r.left - r.width / 2) * s, vb[1] + vb[3] / 2 + (cy - r.top - r.height / 2) * s, s];
};
const fit = () => { vb = [home.x, home.y, home.width, home.height]; show(); };
document.getElementById("fit").addEventListener("click", fit);
svg.removeAttribute("width"); svg.removeAttribute("height");
fit();
pic.addEventListener("wheel", (e) => {
  e.preventDefault();
  const [x, y] = toSvg(e.clientX, e.clientY);
  const k = Math.exp(e.deltaY * 0.0015);
  const w = Math.min(home.width * 1.5, Math.max(home.width / 12, vb[2] * k));
  const f = w / vb[2];
  vb = [x - (x - vb[0]) * f, y - (y - vb[1]) * f, vb[2] * f, vb[3] * f];
  show();
}, { passive: false });
let drag = null;
pic.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY, vb: [...vb], moved: false }; pic.setPointerCapture(e.pointerId); });
pic.addEventListener("pointermove", (e) => {
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (!drag.moved && Math.hypot(dx, dy) < 4) return;
  drag.moved = true; pic.classList.add("drag");
  const s = toSvg(0, 0)[2];
  vb = [drag.vb[0] - dx * s, drag.vb[1] - dy * s, vb[2], vb[3]];
  show();
});
pic.addEventListener("pointerup", (e) => {
  pic.classList.remove("drag");
  const was = drag; drag = null;
  if (!was || was.moved) return;
  const hit = document.elementsFromPoint(e.clientX, e.clientY).map((el) => el.closest && el.closest(".wire")).find(Boolean);
  if (hit) select(hit.dataset.c, true);
  else if (current) select(current);
});
</script>
</body>
</html>
"""


def write_page(svg_text, chips):
    """Inline the picture's SVG, its wires tagged by connection, beside the table."""
    svg_text = svg_text[svg_text.index("<svg"):]
    svg_text = re.sub(r'id="w-([A-Z]\d+)"', r'class="wire" data-c="\1"', svg_text)
    data = [[t, [[html.escape(c) for c in row] + [chips.get(row[0], INK)] for row in rows]] for t, rows in CONNECTIONS]
    out = (PAGE_HTML.replace("__SVG__", svg_text).replace("__DATA__", json.dumps(data, ensure_ascii=False))
           .replace("__BUILD__", BUILD).replace("__LABEL__", "with UWB" if UWB else "without UWB"))
    with open(PAGE, "w") as f:
        f.write(out)
    print("wrote", os.path.relpath(PAGE))


# ----------------------------------------------------------------------------
# The build
# ----------------------------------------------------------------------------
LEGEND = [(V12, "+12 V"), (RED, "+5 V"), (BLACK, "GND"), ("#e67e7e", "+3.3 V (I3)"), (SDA, "I2C SDA"),
          (SCL, "I2C SCL"), (SIGNAL, "latch HOLD / SENSE"), (DATA, "ring data"), (PWM, "servo PWM"),
          ("#8d5524", "servo lead"), (RIBBON, "camera ribbon"), (USB, "USB")]


def render():
    W, H = (334 if UWB else 334), 250
    fig, ax = plt.subplots(figsize=(W / 12.5, H / 12.5), dpi=150)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")

    title = "SportCam full build, " + ("with UWB" if UWB else "without UWB") + ": everything wired up"
    ax.text(4, H - 3, title, fontsize=15, fontweight="bold", color=INK, va="top")
    ax.text(4, H - 10, f"Tags are the connection numbers in docs/{BUILD}/setup/12-wiring.md. "
            "Top-down, not to scale, and not where the parts sit in the enclosure.\nPin orders on the "
            "breakouts are illustrative: match each lead by the labels on yours.",
            fontsize=8.5, color=GREY, va="top")

    # --- Parts ---------------------------------------------------------------
    pins, ports = pi4(ax, 150, 75)
    bank = power_bank(ax, 4, 14)
    trg = trigger(ax, 54, 18)
    lat = latch(ax, 94, 14)
    rck = rocker(ax, 84, 44)
    gau = gauge(ax, 140, 18)
    bk = buck(ax, 178, 12)
    bj = barrel(ax, 236, 49)
    pz = ptz_ctrl(ax, 24, 140)
    cam = camera(ax, 45, 204)
    sh = shifter(ax, 168, 142)
    rg = ring(ax, (300, 216))
    rx = W - 8   # the 5 V leads' run up the right-hand edge

    # --- Power, 12 V side ----------------------------------------------------
    with conn(ax, "P1"):
        wire(ax, [bank, trg["in"]], USB, lw=3)
        tag(ax, ((bank[0] + trg["in"][0]) / 2, bank[1] + 3.5), "P1", USB)
    with conn(ax, "P2"):
        wire(ax, [trg["+12V"], (86, trg["+12V"][1]), (86, 33), (lat["IN"][0], 33)], V12, label="P2", at=0.25)
    with conn(ax, "P3"):
        o, i = lat["OUT"], gau["VIN+"]
        wire(ax, [o, (134, o[1]), (134, i[1]), i], V12, label="P3", at=0.2)
    with conn(ax, "P4"):
        wire(ax, [gau["VIN-"], (171, gau["VIN-"][1]), (171, bk["IN+"][1]), bk["IN+"]], V12, label="P4", at=0.3)
    with conn(ax, "P5"):
        g = trg["GND"]
        wire(ax, [g, (82, g[1]), (82, 6), (174, 6), (174, 17), (bk["IN-"][0], 17)], BLACK, label="P5", at=0.3)
    with conn(ax, "P6"):
        g = lat["GND"]
        wire(ax, [g, (90, g[1]), (90, 9), (172, 9), (172, 19.5), (bk["IN-"][0], 19.5)], BLACK, label="P6", at=0.62)

    # --- Switch -----------------------------------------------------------------
    with conn(ax, "S1"):
        wire(ax, [(lat["IN"][0], 35.5), (rck["1"][0], 35.5), rck["1"]], V12, lw=1.6, label="S1", at=0.4)
    with conn(ax, "S2"):
        wire(ax, [rck["2"], (rck["2"][0], 42), (lat["SW"][0], 42), lat["SW"]], V12, lw=1.6)
        tag(ax, (rck["2"][0] + 4.5, 42), "S2", V12)

    # --- Header leads down the corridor left of the Pi, to the gauge and the
    # latch. Nested so that none cross: (pin, colour, lane above the header,
    # corridor x, corner y, target, number, tag y)
    PINK = "#e67e7e"
    corridor = [
        (1, PINK, 132.5, 146.5, 61, gau["VCC"], "I3", 76),
        (3, SDA, 134.8, 144.0, 58.5, gau["SDA"], "I1", 73),
        (5, SCL, 137.1, 141.5, 56, gau["SCL"], "I2", 70),
        (9, BLACK, 139.4, 139.0, 53.5, gau["GND"], "I4", 67),
        (11, SIGNAL, 141.7, 136.5, 50, lat["HOLD"], "S3", 82),
        (13, SIGNAL, 144.0, 134.0, 52.5, lat["SENSE"], "S4", 88),
    ]
    for num, colour, lane, cx, corner, dst, cid, ty in corridor:
        with conn(ax, cid):
            px, py = pins[num]
            wire(ax, [(px, py), (px, lane), (cx, lane), (cx, corner), (dst[0], corner), dst], colour, lw=1.8)
            pin_end(ax, (px, py), colour)
            tag(ax, (cx, ty), cid, colour)
            if cid in ("I1", "I2"):
                # the PTZ controller's branch off the same lead
                by = 122 if cid == "I1" else 125
                tx = pz["SDA" if cid == "I1" else "SCL"]
                wire(ax, [(cx, by), (tx[0], by), tx], colour, lw=1.8)
                dot(ax, (cx, by), colour)
                pin_end(ax, tx, colour)
                tag(ax, (96 + (8 if cid == "I2" else 0), by), cid, colour)

    # --- 5 V rail: every lead starts at the buck's OUT+ / OUT− ------------------
    op, om = bk["OUT+"], bk["OUT-"]
    heads = ((op,), (om,))
    with conn(ax, "R1"):
        cxy = (op[0] + 3, op[1] - 7)
        wire(ax, [op, (op[0], cxy[1] + 1)], RED, lw=1.2, outline=False)
        wire(ax, [om, (om[0], cxy[1] + 1)], BLACK, lw=1.2, outline=False)
        capacitor(ax, cxy)
        tag(ax, (cxy[0] + 9, cxy[1] - 2), "R1", RED)
    note(ax, 180, 32.5, "R1–R7: every red lead to OUT+,\nevery black to OUT−", fs=5.5, color="white")
    plug = pigtail(ax, ports["usbc"])
    with conn(ax, "R2"):
        pair(ax, [(204, 44), (204, 50), (plug[0], 50), plug], head=heads, label="R2", at=0.35)
        note(ax, plug[0] + 4, plug[1] - 1, "USB-C pigtail", fs=6)
    with conn(ax, "R3"):
        pair(ax, [(209, 44), (209, 62), (14, 62), (14, 130), (pz["5V"][0] + 2, 130), (pz["5V"][0] + 2, 136)],
             d=(-0.9, 0.9), head=heads, tail=((pz["5V"],), (pz["GND"],)), label="R3", at=0.3)
    with conn(ax, "R6"):
        pair(ax, [(224, 46.5), (243, 46.5), (243, 47.5)], d=(-0.9, 0.9), head=heads, tail=((bj["+"],), (bj["-"],)))
        tag(ax, (232, 46.5), "R6", RED)
    with conn(ax, "R7"):
        hp, hm = sh[("pan", "+")], sh[("pan", "-")]
        pair(ax, [(224, 43), (rx - 8, 43), (rx - 8, 164), (hp[0] + 4, 164)], d=(0.9, -0.9),
             head=heads, tail=((hp,), (hm,)), label="R7", at=0.62)
    with conn(ax, "R5"):
        p14 = sh[14]
        pair(ax, [(224, 39.5), (rx - 4, 39.5), (rx - 4, 190), (p14[0] - 4, 190), (p14[0] - 4, 168)],
             d=(0.9, 0.9), head=heads, tail=((p14,), ((p14[0] - 3, sh["gb"]),)), label="R5", at=0.5)
    with conn(ax, "R4"):
        pair(ax, [(224, 36), (rx, 36), (rx, 193), (rg["5V"][0] + 3, 193)], d=(-0.9, 0.9),
             head=heads, tail=((rg["5V"],), (rg["GND"],)), label="R4", at=0.55)

    # --- Shifter: the Pi's SPI and PWM in, 5 V signals out -----------------------
    with conn(ax, "L1"):
        a = pins[19]
        wire(ax, [a, (a[0], 146), (sh[2][0], 146), sh[2]], DATA, lw=1.8)
        pin_end(ax, a, DATA)
        tag(ax, (a[0], 137), "L1", DATA)
    with conn(ax, "L2"):
        d = rg["DIN"]
        wire(ax, [sh[3], (sh[3][0], 148), (172, 148), (172, 194), (d[0], 194), d], DATA, lw=1.8, label="L2", at=0.45)
    with conn(ax, "L3"):
        wire(ax, [sh[1], (sh[1][0], sh["gb"])], BLACK, lw=1.4)
        tag(ax, (sh[1][0] - 3.5, sh["gb"] + 3), "L3", BLACK)
    with conn(ax, "L4"):
        for n in (12, 13):
            wire(ax, [sh[n], (sh[n][0], sh["gt"])], BLACK, lw=1.4)
        tag(ax, (sh[13][0] + 2, sh["gt"] + 5.5), "L4", BLACK)
    with conn(ax, "M3"):
        wire(ax, [sh[4], (sh[4][0], sh["gb"])], BLACK, lw=1.4)
        wire(ax, [sh[10], (sh[10][0], sh["gt"])], BLACK, lw=1.4)
        tag(ax, (sh[10][0] - 2.5, sh["gt"] + 5.5), "M3", BLACK)
    with conn(ax, "M1"):
        a = pins[32]
        wire(ax, [a, (a[0], 144.5), (sh[5][0], 144.5), sh[5]], PWM, lw=1.8)
        pin_end(ax, a, PWM)
        tag(ax, (a[0] - 3, 137), "M1", PWM)
    with conn(ax, "M2"):
        a = pins[33]
        wire(ax, [a, (a[0], 143), (207, 143), (207, 176), (sh[9][0], 176), sh[9]], PWM, lw=1.8)
        pin_end(ax, a, PWM)
        tag(ax, (207, 137), "M2", PWM)
    ts, ps = sh[("tilt", "S")], sh[("pan", "S")]
    with conn(ax, "M4"):
        wire(ax, [sh[6], (sh[6][0], 152.5), (ps[0], 152.5), ps], PWM, lw=1.8)
        tag(ax, (ps[0] - 5, 152.5), "M4", PWM)
    with conn(ax, "M5"):
        wire(ax, [sh[8], (210.5, sh[8][1]), (210.5, ts[1]), ts], PWM, lw=1.8)
        tag(ax, (213, sh[8][1] + 3), "M5", PWM)
    with conn(ax, "M6"):
        for k, c in (("+", RED), ("-", BLACK)):
            wire(ax, [sh[("tilt", k)], sh[("pan", k)]], c, lw=1.4)
        tag(ax, (224, 169), "M6", RED)
    note(ax, 247, 186, "Shifter perfboard:\ngrey strips are GND,\njoined to pin 7.\nServo headers, bottom\nto top: S, +, −", fs=5.5, color=GREY)

    # --- Camera ------------------------------------------------------------------
    with conn(ax, "C1"):
        cx, cy = ports["csi"]
        r = cam["ribbon"]
        wire(ax, [(cx, cy), (cx, 58), (8, 58), (8, r[1] - 2), (r[0], r[1] - 2)], RIBBON, lw=7, z=4)
        tag(ax, (8, 100), "C1", RIBBON)
        note(ax, 10, 56, "15-pin ribbon: silver contacts toward the HDMI ports", fs=6, va="top")
    with conn(ax, "C2"):
        for n, c, x2 in (("ZOOM", "#7a7f8a", 47), ("FOCUS", "#7a7f8a", 51)):
            s = pz[n]
            wire(ax, [s, (s[0], 176), (x2, 176), (x2, 189)], c, lw=1.1, outline=False)
        tag(ax, (pz["FOCUS"][0] + 4, 172), "C2", "#7a7f8a")
    with conn(ax, "M7"):
        for name, lane, start in (("pan", 210, (59, 210)), ("tilt", 205, (60, 205))):
            hx = sh[(name, "-")][0]
            wire(ax, [start, (hx, lane), (hx, sh[(name, "-")][1] + 4)], "#8d5524", lw=2.4)
            ax.add_patch(Rectangle((hx - 2.2, sh[(name, "S")][1] - 1.6), 4.4, 13, fc="none", ec="#8d5524", lw=1.4, zorder=7))
            note(ax, hx + 2.6, sh[(name, "-")][1] + 6, name, fs=6, va="center")
        tag(ax, (120, 210), "M7", "#8d5524")
        note(ax, 63, 200, "servo leads, off the PTZ controller", fs=6, color=GREY)

    # --- Anchors and the tag -----------------------------------------------------
    if UWB:
        ux = ports["usbA1"][0]
        for cid, py, ay, name, sub in (("U1", ports["usbA1"][1] + 3, 124, "A1", "data, arm +Y"),
                                       ("U2", ports["usbA1"][1] - 3, 104, "A2", "arm −Y"),
                                       ("U3", ports["usbA2"][1], 84, "A3", "mast")):
            plug_at = ula1(ax, 276, ay, name, sub)
            with conn(ax, cid):
                wire(ax, [(ux - 2, py), (262, py), (262, ay), plug_at], USB, lw=2.4)
                tag(ax, (266.5, ay), cid, USB)
        note(ax, 262, 70, "U1–U3: 50 cm USB extensions.\nA1 is the data anchor (/dev/ttyUSB0)", fs=6, color=GREY)
        board(ax, 262, 6, 18, 8, "#1c1c1c", "Tag", "ULA1", fs=7, r=1)
        board(ax, 288, 6, 26, 8, "#5d6676", "USB bank (#15)", fs=6.5, r=1)
        with conn(ax, "W1"):
            wire(ax, [(280, 10), (288, 10)], USB, lw=2.4, label="W1", at=0.5)
        note(ax, 262, 20, "the wearable tag", fs=6, color=GREY)

    # --- Legend --------------------------------------------------------------------
    lx, ly = 24, 114
    ax.add_patch(FancyBboxPatch((lx, ly - len(LEGEND) * 3.6 - 1), 48, len(LEGEND) * 3.6 + 5.5,
                                boxstyle="round,pad=0,rounding_size=1.2", fc=BGBOX, ec=GREY, lw=0.8, zorder=1))
    ax.text(lx + 2, ly + 2.3, "Wires", fontsize=7.5, fontweight="bold", color=INK, va="center")
    for i, (c, t) in enumerate(LEGEND):
        yy = ly - 1.8 - i * 3.6
        ax.plot([lx + 2, lx + 8], [yy, yy], color=c, lw=2.6 if c != RIBBON else 5, solid_capstyle="round")
        ax.text(lx + 10, yy, t, fontsize=6.5, color=INK, va="center")

    os.makedirs(os.path.dirname(PNG), exist_ok=True)
    fig.savefig(PNG, facecolor="white", bbox_inches="tight", pad_inches=0.15)
    print("wrote", os.path.relpath(PNG))
    # each connection's tag colour, for the table's number chips
    chips = {}
    for t in ax.texts:
        gid, box = t.get_gid(), t.get_bbox_patch()
        if gid and box is not None:
            chips.setdefault(gid[2:], matplotlib.colors.to_hex(box.get_facecolor()))
    buf = io.StringIO()
    fig.savefig(buf, format="svg", facecolor="white", bbox_inches="tight", pad_inches=0.15,
                metadata={"Date": None})
    plt.close(fig)
    write_page(buf.getvalue(), chips)


if __name__ == "__main__":
    render()
