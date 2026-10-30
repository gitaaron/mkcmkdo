#!/usr/bin/env python3
"""Render the bench rig, every part wired up, top-down → docs/with_uwb/images/bench-wiring.png.

A picture to copy, wire for wire: the USB-C adapter, the Pi, the kit's 6-wire
cable to the PTZ controller, the servo and lens leads, the camera and the
anchors, each lead labelled with its
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
# The kit cable's own colours, as in Arducam's quick start and in the kit
# (Arducam: the order can vary, so go by position)
K_RED, K_BLACK, K_WHITE, K_BROWN, K_YELLOW, K_ORANGE = (
    "#e53935", "#222222", "#c4c7cc", "#7b4a2a", "#f2c200", "#f57c00")
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
        edge = GREY if color == K_WHITE else "white"
        ax.add_patch(PathPatch(path, fc="none", ec=edge, lw=lw + 1.6, zorder=z, capstyle="round"))
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
            color="white" if color not in (SCL, RIBBON, METAL, K_WHITE, K_YELLOW) else INK, zorder=z,
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


# The controller's 6-pin XH connector, by position: the servo supply pair,
# the board's 5 V pair, then I2C (Arducam's PTZ quick start).
CABLE = [(1, "SERVO VCC", K_RED), (2, "GND", K_BLACK), (3, "5V", K_WHITE),
         (4, "GND", K_BROWN), (5, "SCL", K_YELLOW), (6, "SDA", K_ORANGE)]
SERVO_LEAD = ("#7b4a2a", RED, "#e6c200")   # brown (GND), red (V+), yellow (signal)


def ptz(ax, x, y):
    """The PTZ controller: the 6-pin cable connector along the bottom edge;
    the pan and tilt servo sockets and the lens cable along the top."""
    w, h = 54, 26
    board(ax, x, y, w, h, PCB_DARK, "Arducam PTZ controller", "I2C 0x0C", fs=8.5)
    pins = {}
    ax.add_patch(Rectangle((x + 4, y + 0.6), 6 * 4.4 + 1, 3.4, fc="white", ec=INK, lw=0.6, zorder=2.9))
    for i, (n, name, _c) in enumerate(CABLE):
        px = x + 6.5 + i * 4.4
        ax.add_patch(Rectangle((px - 0.6, y + 1.7), 1.2, 1.2, fc=GOLD, ec="none", zorder=3))
        ax.text(px, y + 4.6, f"{n} {name}", ha="center", va="bottom", fontsize=5.2, color="white",
                zorder=3, rotation=90)
        pins[n] = (px, y + 2.3)
    note(ax, x + w - 1.5, y + 2.4, "6-pin\ncable", ha="right", fs=5.5, color="white", va="center")
    for name, sx in (("PAN", x + 8), ("TILT", x + 20)):
        ax.add_patch(Rectangle((sx - 3, y + h - 3.6), 6, 2.6, fc="white", ec=INK, lw=0.6, zorder=3))
        ax.text(sx, y + h - 4.3, name, ha="center", va="top", fontsize=5.5, color="white", zorder=3)
        pins[name] = [(sx - 1.6 + k * 1.6, y + h - 1) for k in range(3)]
    ax.add_patch(Rectangle((x + 36, y + h - 3.6), 9, 2.6, fc="white", ec=INK, lw=0.6, zorder=3))
    ax.text(x + 40.5, y + h - 4.3, "LENS", ha="center", va="top", fontsize=5.5, color="white", zorder=3)
    pins["LENS"] = (x + 40.5, y + h - 1)
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


def camera(ax, x, y, servos=False):
    """The PTZ camera head on its metal pan-tilt base, top-down; with `servos`,
    the pan and tilt servos' plug ends too."""
    ax.add_patch(Circle((x, y), 16, fc="#3a3f47", ec=INK, lw=1.2, zorder=2))  # base
    ax.add_patch(Circle((x, y), 11, fc="#4b515b", ec=INK, lw=1, zorder=2.1))
    ax.add_patch(FancyBboxPatch((x - 9, y - 6), 18, 12, boxstyle="round,pad=0,rounding_size=1",
                                fc="#1e2228", ec=INK, lw=1, zorder=2.2))
    ax.add_patch(Circle((x - 11.5, y), 5, fc="#14181f", ec="#6b7380", lw=1.5, zorder=2.3))  # lens
    ax.text(x + 18, y + (6 if servos else 14), "PTZ camera (#1):\nIMX477 + zoom lens\non its pan-tilt base",
            ha="left", va="center", fontsize=8, fontweight="bold", color=INK, zorder=3)
    # The two servos' plug ends, drawn where their leads come off the base
    ends = {}
    for name, sx in () if not servos else (("pan", x - 9), ("tilt", x + 7)):
        ax.add_patch(Rectangle((sx - 5, y + 17), 10, 5, fc="#1e2228", ec=INK, lw=0.8, zorder=2.4))
        ax.text(sx, y + 19.5, f"{name} servo", ha="center", va="center", fontsize=5.5, color="white", zorder=2.5)
        ends[name] = (sx, y + 22)
    return {"ribbon": (x - 5, y - 6), "lens": (x - 10, y + 6), **ends}


def anchor(ax, x, y, name, sub):
    board(ax, x - 9, y - 4, 18, 8, "#1c1c1c", name, sub, fs=7.5, r=1)
    ax.add_patch(Rectangle((x + 9, y - 1.6), 4, 3.2, fc=METAL, ec=INK, lw=0.6, zorder=3))  # USB-A plug
    return (x + 13, y)


# ----------------------------------------------------------------------------
# The rig
# ----------------------------------------------------------------------------
def render():
    yb = 15 if UWB else 4  # room along the bottom for the anchor bar
    W, H = 205, yb + 152
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
    pz = ptz(ax, 8, yb + 94)
    cam = camera(ax, 150, yb + 104, servos=True)

    # P1: the adapter → Pi USB-C
    out = adapter(ax, 6, yb + 2)
    uc = ports["usbc"]
    ax.add_patch(FancyBboxPatch((uc[0] - 3, uc[1] - 7), 6, 7, boxstyle="round,pad=0,rounding_size=1",
                                fc="#2b2f36", ec=INK, lw=1, zorder=8))
    wire(ax, [out, (uc[0], out[1]), (uc[0], uc[1] - 7)], BLACK, lw=2.6)
    tag(ax, ((out[0] + uc[0]) / 2, out[1]), "P1", BLACK)

    # J1-J4, I1, I2: the kit's 6-wire cable, controller → Pi header. Its
    # female ends go straight on the pins. The order on the connector crosses
    # some wires over; each lane is its own height.
    to_pi = {1: (2, "J3"), 2: (14, "J4"), 3: (4, "J1"), 4: (6, "J2"), 5: (5, "I2"), 6: (3, "I1")}
    lanes = {n: 78.5 + (n - 1) * 2.5 for n in to_pi}   # rightmost pin, highest lane: no crossings at the controller
    for n, name, colour in CABLE:
        num, lab = to_pi[n]
        px, py = pins[num]
        tx, ty = pz[n]
        lane = yb + lanes[n]
        dx = {5: -0.9, 6: 0.9}.get(num, 0)   # pins 5 and 6 share a column
        top = pins[2][1] + 1.6
        wire(ax, [(px, py), (px + dx, top), (px + dx, lane), (tx, lane), (tx, ty)], colour, lw=1.8)
        pin_end(ax, (px, py), colour)
        tag(ax, (41 if n % 2 else 45, lane), lab, colour)
    note(ax, 66, yb + 88, "The kit's 6-wire cable, by position (colours as\nArducam draws them; yours may differ):\n"
         "1 servo VCC (red) → pin 2 (5V)   2 GND (black) → pin 14\n"
         "3 5V (white) → pin 4   4 GND (brown) → pin 6\n"
         "5 SCL (yellow) → pin 5   6 SDA (orange) → pin 3\n"
         "Its female ends go straight onto the Pi's pins.",
         fs=6.8, color=INK, va="center")

    # C1: camera ribbon → Pi CSI, round the right of the Pi
    cx, cy = ports["csi"]
    rx = cam["ribbon"][0]
    wire(ax, [(cx, cy), (cx, yb + 8), (rx, yb + 8), cam["ribbon"]], RIBBON, lw=7, z=4)
    tag(ax, (rx, yb + 70), "C1", RIBBON)
    note(ax, cx + 4, yb + 9.5, "15-pin ribbon: silver contacts toward the HDMI ports", fs=7, va="bottom")

    # K1, K2: the servos' 3-wire plugs in the controller's sockets, as the kit
    # came (pan left, tilt right); K3: the lens cable (zoom, focus), factory-fitted
    for name, lab, lane in (("PAN", "K1", yb + 134), ("TILT", "K2", yb + 130.5)):
        end_pt = cam[name.lower()]
        for k, (sx, sy) in enumerate(pz[name]):
            off = (k - 1) * 0.8
            ex = end_pt[0] + off
            wire(ax, [(sx, sy), (sx, lane - off), (ex, lane - off), (ex, end_pt[1])],
                 SERVO_LEAD[k], lw=1.0, z=5, outline=False)
        tag(ax, (pz[name][1][0] + 30, lane), lab, SERVO_LEAD[0])
    lx, ly = pz["LENS"]
    lane = yb + 124
    wire(ax, [(lx, ly), (lx, lane), (131, lane), (131, cam["lens"][1]), cam["lens"]], "#7a7f8a",
         lw=2.2, z=5, outline=False)
    tag(ax, (lx + 30, lane), "K3", "#7a7f8a")
    note(ax, 168, yb + 103, "K1 pan, K2 tilt: each servo's\n3-wire plug (brown GND, red V+,\n"
         "yellow signal), in the controller's\nsockets as the kit came.\n"
         "K3: the lens-motor and IR-cut\ncables, factory-fitted.", fs=6.5, color=GREY)

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
    legend = [(K_RED, "servo VCC, 5 V"), (K_WHITE, "controller 5 V"), (K_BLACK, "GND, adapter cable"),
              (K_BROWN, "GND"), (K_ORANGE, "I2C SDA"), (K_YELLOW, "I2C SCL"),
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
