#!/usr/bin/env python3
"""Render the bench rig, every part wired up, top-down → docs/with_uwb/images/bench-wiring.png.

A picture to copy, wire for wire: the USB-C adapter, the Pi, the jumpers to
the PTZ controller, the camera and the anchors, each lead labelled with its
number in docs/with_uwb/bench/12-wiring.md. Not to scale.

Usage:  python3 with_uwb/schematics/render_bench.py
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, PathPatch, Rectangle
from matplotlib.path import Path

BUILD = "with_uwb"
UWB = True

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "docs", BUILD, "images")
os.makedirs(OUT, exist_ok=True)

INK = "#1a2233"
GREY = "#8a93a6"
BGBOX = "#f4f6fb"
PCB_GREEN = "#2f7d4f"
PCB_DARK = "#24324a"
METAL = "#c9ced6"
GOLD = "#d9b44a"
# Wire colours: the ones the guide uses where it names one.
RED = "#d64541"
BLACK = "#222222"
SDA = "#2f6fed"
SCL = "#e0a100"
RIBBON = "#b8bec9"
USB = "#5b6475"

PITCH = 2.54  # header pin pitch, mm


# ----------------------------------------------------------------------------
# Drawing helpers
# ----------------------------------------------------------------------------
def board(ax, x, y, w, h, fc, title=None, sub=None, ec=INK, tc="white", fs=10, r=1.5, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=1.2, zorder=z))
    if title:
        ax.text(x + w / 2, y + h / 2 + (1.6 if sub else 0), title, ha="center", va="center",
                fontsize=fs, fontweight="bold", color=tc, zorder=z + 0.5)
    if sub:
        ax.text(x + w / 2, y + h / 2 - 2.2, sub, ha="center", va="center",
                fontsize=fs - 2.5, color=tc, zorder=z + 0.5)


def wire(ax, pts, color, lw=2.6, z=6, label=None, at=0.5, ls="-", outline=True):
    """A wire through `pts`, rounded at each corner, with an optional tag."""
    verts, codes = [pts[0]], [Path.MOVETO]
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        r = 2.0
        d0 = max(abs(x1 - x0), abs(y1 - y0)) or 1
        d2 = max(abs(x2 - x1), abs(y2 - y1)) or 1
        a = (x1 - (x1 - x0) * min(r, d0 / 2) / d0, y1 - (y1 - y0) * min(r, d0 / 2) / d0)
        b = (x1 + (x2 - x1) * min(r, d2 / 2) / d2, y1 + (y2 - y1) * min(r, d2 / 2) / d2)
        verts += [a, (x1, y1), b]
        codes += [Path.LINETO, Path.CURVE3, Path.CURVE3]
    verts.append(pts[-1])
    codes.append(Path.LINETO)
    path = Path(verts, codes)
    if outline:
        ax.add_patch(PathPatch(path, fc="none", ec="white", lw=lw + 1.6, zorder=z, capstyle="round"))
    ax.add_patch(PathPatch(path, fc="none", ec=color, lw=lw, zorder=z + 0.1, capstyle="round",
                           linestyle=ls, joinstyle="round"))
    if label:
        tag(ax, along(pts, at), label, color, z=z + 0.5)


def along(pts, t):
    """The point a fraction `t` of the way along a polyline."""
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    lens = [abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in segs]
    goal = sum(lens) * t
    for (a, b), n in zip(segs, lens):
        if goal <= n and n:
            f = goal / n
            return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        goal -= n
    return pts[-1]


def tag(ax, xy, text, color, z=8):
    ax.text(xy[0], xy[1], text, ha="center", va="center", fontsize=8, fontweight="bold",
            color="white" if color not in (SCL, RIBBON, METAL) else INK, zorder=z,
            bbox=dict(boxstyle="round,pad=0.25", fc=color, ec="white", lw=0.8))


def note(ax, x, y, text, ha="left", fs=8, color=INK, va="top"):
    ax.text(x, y, text, ha=ha, va=va, fontsize=fs, color=color, zorder=9, linespacing=1.35)


def pin_end(ax, xy, color, z=7):
    """A jumper's plug end: a small black housing on the pin."""
    ax.add_patch(Rectangle((xy[0] - 0.9, xy[1] - 0.9), 1.8, 1.8, fc=BLACK, ec=color, lw=1.0, zorder=z))


# ----------------------------------------------------------------------------
# Parts
# ----------------------------------------------------------------------------
def pi4(ax, x, y):
    """Raspberry Pi 4, top-down: header along the top edge, pin 1 at the left,
    USB-A and Ethernet on the right, USB-C and the micro-HDMIs along the bottom."""
    w, h = 85, 56
    board(ax, x, y, w, h, PCB_GREEN, z=2, r=3)
    ax.text(x + 30, y + 38, "Raspberry Pi 4", ha="center", fontsize=11, fontweight="bold",
            color="white", zorder=3)
    ax.add_patch(Rectangle((x + 22, y + 14), 15, 15, fc="#a6abb3", ec=INK, lw=0.8, zorder=2.5))  # SoC
    # 40-pin header
    pins = {}
    hx, hy = x + 7.4, y + h - 3.5
    ax.add_patch(Rectangle((hx - 1.6, hy - 3.9), 20 * PITCH + 0.6, 5.2, fc="#14181f", ec=INK, lw=0.8, zorder=3))
    for i in range(20):
        for row, num in ((0, 2 * i + 1), (1, 2 * i + 2)):
            px, py = hx + i * PITCH, hy - 2.54 + row * PITCH
            ax.add_patch(Rectangle((px - 0.45, py - 0.45), 0.9, 0.9, fc=GOLD, ec="none", zorder=3.2))
            pins[num] = (px, py)
    ax.add_patch(Rectangle((hx - 0.8, hy - 2.54 - 0.8), 1.6, 1.6, fc="none", ec="white", lw=0.8, zorder=3.3))
    note(ax, hx - 2.4, hy - 2.54, "pin 1", ha="right", fs=7, color="white", va="center")
    note(ax, hx + 21 * PITCH - 1.5, hy, "40-pin header\n(odd pins: inner row)", fs=6.5, color="white", va="center")
    # Ports
    ax.add_patch(Rectangle((x + w - 4, y + 2), 21, 13, fc=METAL, ec=INK, lw=0.8, zorder=2.6))
    ax.add_patch(Rectangle((x + w - 4, y + 20), 21, 13, fc=METAL, ec=INK, lw=0.8, zorder=2.6))
    ax.add_patch(Rectangle((x + w - 4, y + 37.5), 21, 16, fc="#e3e6ea", ec=INK, lw=0.8, zorder=2.6))
    note(ax, x + w + 6.5, y + 45.5, "Ethernet", ha="center", fs=7, va="center")
    note(ax, x + w + 6.5, y + 26.5, "USB-A", ha="center", fs=7, va="center")
    note(ax, x + w + 6.5, y + 8.5, "USB-A", ha="center", fs=7, va="center")
    ports = {"usbA1": (x + w + 17, y + 26.5), "usbA2": (x + w + 17, y + 8.5)}
    ax.add_patch(Rectangle((x + 7.5, y - 1.5), 9, 5, fc=METAL, ec=INK, lw=0.8, zorder=2.6))
    note(ax, x + 12, y + 4.6, "USB-C", ha="center", fs=7, color="white", va="bottom")
    ports["usbc"] = (x + 12, y - 1.5)
    for hx2 in (26, 39.5):
        ax.add_patch(Rectangle((x + hx2 - 3.5, y - 1), 7, 4, fc=METAL, ec=INK, lw=0.8, zorder=2.6))
    note(ax, x + 32.7, y + 4, "micro-HDMI", ha="center", fs=6.5, color="white", va="bottom")
    # CSI camera connector: a strip across the board, between HDMI and audio
    ax.add_patch(Rectangle((x + 44, y + 3.5), 3, 22, fc="#f2f2f2", ec=INK, lw=0.8, zorder=2.7))
    note(ax, x + 49, y + 14.5, "CAMERA\n(CSI)", fs=6.5, color="white", va="center")
    ports["csi"] = (x + 45.5, y + 14.5)
    ax.add_patch(Circle((x + 54, y + 1), 3, fc="#14181f", ec=INK, lw=0.8, zorder=2.6))
    return pins, ports


def ptz(ax, x, y):
    """The PTZ controller: its 5V / SDA / SCL / GND pins along the bottom edge,
    the factory motor leads along the top."""
    w, h = 40, 24
    board(ax, x, y, w, h, PCB_DARK, "Arducam PTZ controller", "I2C 0x0C; motor leads as the kit came", fs=8.5)
    pins = {}
    for i, n in enumerate(["5V", "SDA", "SCL", "GND"]):
        px = x + 5 + i * PITCH * 1.4
        ax.add_patch(Rectangle((px - 0.6, y + 2), 1.2, 1.2, fc=GOLD, ec="none", zorder=3))
        ax.text(px, y + 4, n, ha="center", va="bottom", fontsize=5.5, color="white", zorder=3, rotation=90)
        pins[n] = (px, y + 2.6)
    for i, n in enumerate(["PAN", "TILT", "ZOOM", "FOCUS"]):
        px = x + 8 + i * 8
        ax.add_patch(Rectangle((px - 2.2, y + h - 3.6), 4.4, 2.6, fc="white", ec=INK, lw=0.6, zorder=3))
        ax.text(px, y + h - 4.3, n, ha="center", va="top", fontsize=5.5, color="white", zorder=3)
        pins[n] = (px, y + h - 1)
    return pins


def adapter(ax, x, y):
    """The USB-C wall adapter, its plug pins up. Returns where its cable leaves."""
    ax.add_patch(FancyBboxPatch((x, y), 22, 14, boxstyle="round,pad=0,rounding_size=2",
                                fc="white", ec=INK, lw=1.2, zorder=3))
    for dx in (7, 15):
        ax.add_patch(Rectangle((x + dx - 0.6, y + 14), 1.2, 4, fc=METAL, ec=INK, lw=0.6, zorder=2.9))
    ax.text(x + 11, y + 9, "USB-C adapter", ha="center", fontsize=7.5, fontweight="bold", color=INK, zorder=4)
    ax.text(x + 11, y + 5, "5.1 V 3 A  (B1)", ha="center", fontsize=7, color=INK, zorder=4)
    ax.text(x + 11, y + 21, "to the wall", ha="center", fontsize=6.5, color=GREY, zorder=4)
    return (x + 22, y + 7)


def camera(ax, x, y):
    """The PTZ camera head on its metal pan-tilt base, top-down."""
    ax.add_patch(Circle((x, y), 16, fc="#3a3f47", ec=INK, lw=1.2, zorder=2))  # base
    ax.add_patch(Circle((x, y), 11, fc="#4b515b", ec=INK, lw=1, zorder=2.1))
    ax.add_patch(FancyBboxPatch((x - 9, y - 6), 18, 12, boxstyle="round,pad=0,rounding_size=1",
                                fc="#1e2228", ec=INK, lw=1, zorder=2.2))
    ax.add_patch(Circle((x - 11.5, y), 5, fc="#14181f", ec="#6b7380", lw=1.5, zorder=2.3))  # lens
    ax.text(x + 18, y + 14, "PTZ camera (#1):\nIMX477 + zoom lens\non its pan-tilt base",
            ha="left", va="center", fontsize=8, fontweight="bold", color=INK, zorder=3)
    return {"ribbon": (x - 5, y - 6), "leads": (x - 3, y + 6)}


def anchor(ax, x, y, name, sub):
    board(ax, x - 9, y - 4, 18, 8, "#1c1c1c", name, sub, fs=7.5, r=1)
    ax.add_patch(Rectangle((x + 9, y - 1.6), 4, 3.2, fc=METAL, ec=INK, lw=0.6, zorder=3))  # USB-A plug
    return (x + 13, y)


# ----------------------------------------------------------------------------
# The rig
# ----------------------------------------------------------------------------
def render():
    yb = 15 if UWB else 4  # room along the bottom for the anchor bar
    W, H = 205, yb + 142
    fig, ax = plt.subplots(figsize=(W / 12.5, H / 12.5), dpi=150)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")

    title = "SportCam bench rig, " + ("with UWB" if UWB else "without UWB") + ": everything wired up"
    ax.text(4, H - 3, title, fontsize=15, fontweight="bold", color=INK, va="top")
    ax.text(4, H - 10, f"Tags are the connection numbers in docs/{BUILD}/bench/12-wiring.md. "
            "Top-down, not to scale. Wire with the adapter unplugged.",
            fontsize=8.5, color=GREY, va="top")

    pins, ports = pi4(ax, 40, yb + 20)
    pz = ptz(ax, 14, yb + 92)
    cam = camera(ax, 150, yb + 104)

    # P1: the adapter → Pi USB-C
    out = adapter(ax, 6, yb + 2)
    uc = ports["usbc"]
    ax.add_patch(FancyBboxPatch((uc[0] - 3, uc[1] - 7), 6, 7, boxstyle="round,pad=0,rounding_size=1",
                                fc="#2b2f36", ec=INK, lw=1, zorder=8))
    wire(ax, [out, (uc[0], out[1]), (uc[0], uc[1] - 7)], BLACK, lw=2.6)
    tag(ax, ((out[0] + uc[0]) / 2, out[1]), "P1", BLACK)

    # J1, J2, I1, I2: four F-F jumpers, Pi header → PTZ controller. The
    # inner-row pin 5 and the outer-row pin 6 share a column, so their leads
    # leave a little apart.
    jumpers = ((2, "5V", RED, "J1", 0, yb + 80), (3, "SDA", SDA, "I1", 0, yb + 82.5),
               (5, "SCL", SCL, "I2", -0.9, yb + 85), (6, "GND", BLACK, "J2", 0.9, yb + 87.5))
    for num, name, colour, lab, dx, lane in jumpers:
        px, py = pins[num]
        tx, ty = pz[name]
        top = pins[2][1] + 1.6
        wire(ax, [(px, py), (px + dx, top), (px + dx, lane), (tx, lane), (tx, ty)], colour, lw=2)
        pin_end(ax, (px, py), colour)
        pin_end(ax, (tx, ty), colour)
        tag(ax, (tx + 4 + 3.5 * jumpers.index((num, name, colour, lab, dx, lane)), lane), lab, colour)
    note(ax, 60, yb + 88, "pin 2 → 5V,  pin 3 → SDA,\npin 5 → SCL,  pin 6 → GND\n"
         "(F-F jumpers, B2). Match the\ncontroller end by its labels.", fs=7, color=INK, va="center")

    # C1: camera ribbon → Pi CSI, round the right of the Pi
    cx, cy = ports["csi"]
    rx = cam["ribbon"][0]
    wire(ax, [(cx, cy), (cx, yb + 8), (rx, yb + 8), cam["ribbon"]], RIBBON, lw=7, z=4)
    tag(ax, (rx, yb + 70), "C1", RIBBON)
    note(ax, cx + 4, yb + 9.5, "15-pin ribbon: silver contacts toward the HDMI ports", fs=7, va="bottom")

    # Factory leads, PTZ controller → camera
    for i, n in enumerate(["PAN", "TILT", "ZOOM", "FOCUS"]):
        sx, sy = pz[n]
        lane = yb + 126 - i * 1.6
        lx = cam["leads"][0] - 4 + i * 1.6
        wire(ax, [(sx, sy), (sx, lane), (lx, lane), (lx, cam["leads"][1])],
             ["#e07b39", "#c9a227", "#7a7f8a", "#7a7f8a"][i], lw=1.1, z=5, outline=False)

    # --- Anchors and tag ------------------------------------------------------
    if UWB:
        ax.add_patch(Rectangle((40, 3), 98, 5, fc="#c89b62", ec="#8b6a3e", lw=1, zorder=1.5))
        note(ax, 88, 5.5, "anchor bar (B3): wood", ha="center", fs=6.5, color="#5a4326", va="center")
        a1 = anchor(ax, 56, 5.5, "A1", "data")
        a2 = anchor(ax, 116, 5.5, "A2", "power")
        ax.annotate("", (56, 11.5), (116, 11.5), arrowprops=dict(arrowstyle="<->", color=INK, lw=0.8))
        ax.text(94, 12, "400 mm, centre to centre", ha="center", fontsize=7, color=INK, va="bottom")
        for a, port, lab, lane, up in ((a1, "usbA1", "U1", yb + 1.5, 157), (a2, "usbA2", "U2", yb + 3, 153)):
            ux, uy = ports[port]
            wire(ax, [a, (a[0] + 3, a[1]), (a[0] + 3, lane), (up, lane), (up, uy), (ux, uy)], USB, lw=2.4)
            tag(ax, (up, (lane + uy) / 2), lab, USB)
        note(ax, 166, 30, "U1, U2: 50 cm USB\nextensions (#20). A1 is\nthe data anchor\n"
             "(/dev/ttyUSB0). Keep the\nantennas 30 cm from\nthe Pi and adapter.", fs=6.5, color=GREY)
        board(ax, 150, 2, 18, 8, "#1c1c1c", "Tag", "flashed ULA1", fs=7.5, r=1)
        board(ax, 174, 2, 22, 8, "#5d6676", "USB bank (#15)", fs=7, r=1)
        wire(ax, [(168, 6), (174, 6)], USB, lw=2.4, label="W1", at=0.5)

    # --- Legend ---------------------------------------------------------------
    legend = [(RED, "+5 V"), (BLACK, "GND, adapter cable"), (SDA, "I2C SDA"), (SCL, "I2C SCL"),
              (RIBBON, "camera ribbon")] + ([(USB, "USB")] if UWB else [])
    lx, ly = 166, yb + 72
    ax.add_patch(FancyBboxPatch((lx, ly - len(legend) * 4.2 - 1), 34, len(legend) * 4.2 + 5.5,
                                boxstyle="round,pad=0,rounding_size=1.2", fc=BGBOX, ec=GREY, lw=0.8, zorder=1))
    ax.text(lx + 2, ly + 2.5, "Wires", fontsize=8, fontweight="bold", color=INK, va="center")
    for i, (c, t) in enumerate(legend):
        yy = ly - 2 - i * 4.2
        ax.plot([lx + 2, lx + 8], [yy, yy], color=c, lw=2.8 if c != RIBBON else 5, solid_capstyle="round")
        ax.text(lx + 10, yy, t, fontsize=7.5, color=INK, va="center")

    out = os.path.join(OUT, "bench-wiring.png")
    fig.savefig(out, facecolor="white", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print("wrote", os.path.relpath(out))


if __name__ == "__main__":
    render()
