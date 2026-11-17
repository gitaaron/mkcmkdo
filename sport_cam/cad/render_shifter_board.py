#!/usr/bin/env python3
"""Draw the level shifter's perfboard layout, hole by hole, for the shifter guide.

  → docs/setup/images/level-shifter-board.png           servos on the Pi (SERVO_DRIVER = "pigpio")
  → docs/setup/images/level-shifter-board-arducam.png   servos left on the PTZ controller ("arducam")

Two views of the 2 × 8 cm double-sided board (BOM 13a.10, 28 × 6 holes): the
parts side, as you place the parts, and the solder side, flipped left to right
as you see it with the board turned over, with every solder link and the leads
off the board tagged with their numbers in docs/<build>/setup/12-wiring.md.

The 74AHCT125 lies along the board with its pins in rows B and E. The holes
under its body (rows C and D) carry two ground buses on the solder side.
With the servos on the Pi, gates 2 and 3 drive two 3-pin servo headers at the
right-hand end; with them on the PTZ controller, those gates' inputs are
bridged to ground instead and there are no headers.

The layout is checked before it is drawn, like the power latch's: every link
and every leg is joined up and compared with the netlist, so a link that
shorts two nets, a net left open, or a leg under the chip or a standoff stops
the script.

Usage:  python3 cad/render_shifter_board.py
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "docs", "setup", "images", "level-shifter-board{}.png")

# ---- the board -----------------------------------------------------------------
BW, BH = 80.0, 20.0          # mm, the kit's 2 × 8 cm board
COLS, ROWS = 28, 6           # holes (168)
P = 2.54
X0 = (BW - (COLS - 1) * P) / 2
Y0 = (BH - (ROWS - 1) * P) / 2
CORNER = 2.0                 # mounting holes, in from each edge
KEEP = 4.0                   # standoff and screw head radius round a corner hole
ROWNAMES = "ABCDEF"

INK = "#1a2233"
GREY = "#8a93a6"
PERF = "#3f9a4a"
PERF_EDGE = "#2a6b33"
COPPER = "#d9b44a"
SOLDER = "#b9c0cb"
V5 = "#d64541"
GND = "#222222"
DATA = "#16a085"
PWM = "#e67e22"
SERVO5 = "#c0392b"

NET_COLOR = {"GND": GND, "VCC": V5, "L1": DATA, "L2": DATA, "M1": PWM, "M2": PWM, "PAN": PWM, "TILT": PWM,
             "SVP": SERVO5, "SVN": GND}

# ---- the parts -----------------------------------------------------------------
# The chip: notch to the left, pins 1–7 along row B (columns 4–10, left to right),
# pins 8–14 along row E (columns 10–4, right to left). (col, row), 0-based.
CHIP = {n: (2 + n, 1) for n in range(1, 8)}
CHIP.update({n: (17 - n, 4) for n in range(8, 15)})
CHIP_PINS = {1: "1OE", 2: "1A", 3: "1Y", 4: "2OE", 5: "2A", 6: "2Y", 7: "GND",
             8: "3Y", 9: "3A", 10: "3OE", 11: "4Y", 12: "4A", 13: "4OE", 14: "VCC"}
CAP = {"a": (2, 4), "b": (2, 3)}                 # 100 nF across the supply, beside pin 14
HEADERS = {"HP": {"S": (21, 1), "+": (21, 2), "-": (21, 3)},   # pan
           "HT": {"S": (24, 1), "+": (24, 2), "-": (24, 3)}}   # tilt


def under_chip(c, r):
    return 3 <= c <= 9 and 2 <= r <= 3


# Leads off the board: name → (hole, wiring-guide tag, where it goes, colour)
LEADS_COMMON = {
    "VCC": ((3, 5), "R5", "+5 V (buck OUT+)", V5),
    "GND": ((10, 2), "R5", "GND (buck OUT−)", GND),
    "L1": ((4, 0), "L1", "Pi pin 19 (GPIO10)", DATA),
    "L2": ((5, 0), "L2", "ring DIN", DATA),
}
LEADS_PIGPIO = {
    "M1": ((7, 0), "M1", "Pi pin 32 (GPIO12)", PWM),
    "M2": ((8, 5), "M2", "Pi pin 33 (GPIO13)", PWM),
    "SVP": ((22, 2), "R7", "+5 V (buck OUT+)", SERVO5),
    "SVN": ((22, 3), "R7", "GND (buck OUT−)", GND),
}

# Solder links on the underside: id → (net, [holes along it])
LINKS_COMMON = {
    "W1": ("GND", [(3, 2), (10, 2)]),             # ground bus under the chip, row C, to the GND lead
    "W2": ("GND", [(3, 1), (3, 2)]),              # 1OE
    "W3": ("GND", [(6, 1), (6, 2)]),              # 2OE
    "W4": ("GND", [(9, 1), (9, 2)]),              # pin 7, GND
    "W5": ("GND", [(2, 3), (8, 3)]),              # ground bus, row D, from the capacitor
    "W6": ("GND", [(4, 2), (4, 3)]),              # joins the two buses
    "W7": ("GND", [(4, 4), (4, 3)]),              # 4OE
    "W8": ("GND", [(5, 4), (5, 3)]),              # 4A
    "W9": ("GND", [(7, 4), (7, 3)]),              # 3OE
    "W10": ("VCC", [(2, 4), (3, 4), (3, 5)]),     # capacitor, pin 14, the +5 V lead
    "W11": ("L1", [(4, 0), (4, 1)]),
    "W12": ("L2", [(5, 0), (5, 1)]),
}
LINKS_PIGPIO = {
    "W13": ("M1", [(7, 0), (7, 1)]),
    "W14": ("PAN", [(8, 1), (8, 0), (21, 0), (21, 1)]),
    "W15": ("M2", [(8, 5), (8, 4)]),
    "W16": ("TILT", [(9, 4), (9, 5), (25, 5), (25, 1), (24, 1)]),
    "W17": ("SVP", [(21, 2), (24, 2)]),
    "W18": ("SVN", [(21, 3), (24, 3)]),
}
LINKS_ARDUCAM = {
    "W13": ("GND", [(7, 1), (7, 2)]),             # 2A to the ground bus: gate 2 unused
    "W15": ("GND", [(8, 4), (8, 3)]),             # 3A to the ground bus: gate 3 unused
}


def netlist(servos):
    gnd = {"chip.1", "chip.4", "chip.7", "chip.10", "chip.12", "chip.13", "C1.b", "lead.GND"}
    nets = {"VCC": {"chip.14", "C1.a", "lead.VCC"}, "L1": {"chip.2", "lead.L1"}, "L2": {"chip.3", "lead.L2"},
            "NC4Y": {"chip.11"}}
    if servos == "pigpio":
        nets.update({"M1": {"chip.5", "lead.M1"}, "PAN": {"chip.6", "HP.S"}, "M2": {"chip.9", "lead.M2"},
                     "TILT": {"chip.8", "HT.S"}, "SVP": {"HP.+", "HT.+", "lead.SVP"},
                     "SVN": {"HP.-", "HT.-", "lead.SVN"}})
    else:
        gnd |= {"chip.5", "chip.9"}
        nets.update({"NC2Y": {"chip.6"}, "NC3Y": {"chip.8"}})
    nets["GND"] = gnd
    return nets


def design(servos):
    leads = dict(LEADS_COMMON, **(LEADS_PIGPIO if servos == "pigpio" else {}))
    links = dict(LINKS_COMMON, **(LINKS_PIGPIO if servos == "pigpio" else LINKS_ARDUCAM))
    links = dict(sorted(links.items(), key=lambda kv: int(kv[0][1:])))
    pins = {f"chip.{n}": h for n, h in CHIP.items()}
    pins.update({f"C1.{k}": h for k, h in CAP.items()})
    if servos == "pigpio":
        for hn, hp in HEADERS.items():
            pins.update({f"{hn}.{k}": h for k, h in hp.items()})
    pins.update({f"lead.{k}": v[0] for k, v in leads.items()})
    return leads, links, pins


# ---- checks --------------------------------------------------------------------
def cells(path):
    out = [path[0]]
    for (c0, r0), (c1, r1) in zip(path, path[1:]):
        assert c0 == c1 or r0 == r1, f"link {path} must run along the grid"
        n = max(abs(c1 - c0), abs(r1 - r0))
        for i in range(1, n + 1):
            out.append((c0 + (c1 - c0) * i // n, r0 + (r1 - r0) * i // n))
    return out


def check(servos):
    leads, links, pins = design(servos)
    nets = netlist(servos)
    errs = []
    seen = {}
    for k, h in pins.items():
        if h in seen:
            errs.append(f"{k} and {seen[h]} share hole {h}")
        seen[h] = k
        c, r = h
        if not (0 <= c < COLS and 0 <= r < ROWS):
            errs.append(f"{k} is off the board")
        if under_chip(c, r):
            errs.append(f"{k} is under the chip")
        x, y = X0 + c * P, Y0 + r * P
        for cx in (CORNER, BW - CORNER):
            for cy in (CORNER, BH - CORNER):
                if (x - cx) ** 2 + (y - cy) ** 2 < KEEP ** 2:
                    errs.append(f"{k} is under a standoff")
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    link_net = {}
    for lid, (net, path) in links.items():
        cs = cells(path)
        for h in cs:
            parent[find(h)] = find(cs[0])
            if link_net.setdefault(h, net) != net:
                errs.append(f"{lid} ({net}) shares hole {h} with {link_net[h]}")
            x, y = X0 + h[0] * P, Y0 + h[1] * P
            for cx in (CORNER, BW - CORNER):
                for cy in (CORNER, BH - CORNER):
                    if (x - cx) ** 2 + (y - cy) ** 2 < KEEP ** 2:
                        errs.append(f"{lid} runs under a standoff")
    for net, members in nets.items():
        if len({find(pins[m]) for m in members}) != 1:
            errs.append(f"net {net} is not joined up: {sorted(members)}")
    roots = [find(pins[next(iter(m))]) for m in nets.values()]
    if len(set(roots)) != len(roots):
        errs.append("two nets are shorted together")
    listed = set().union(*nets.values())
    if listed != set(pins):
        errs.append(f"legs not in the netlist: {sorted(set(pins) ^ listed)}")
    for k, h in pins.items():
        net = next(n for n, m in nets.items() if k in m)
        if h in link_net and link_net[h] != net:
            errs.append(f"{k} ({net}) sits on a {link_net[h]} link")
    if errs:
        sys.exit(f"level shifter layout ({servos}):\n  " + "\n  ".join(errs))
    return leads, links, pins


# ---- drawing -------------------------------------------------------------------
def tag(ax, xy, text, color, fs=7.0, z=9):
    ax.text(xy[0], xy[1], text, ha="center", va="center", fontsize=fs, fontweight="bold",
            color="white", zorder=z, bbox=dict(boxstyle="round,pad=0.22", fc=color, ec="white", lw=0.8))


class View:
    def __init__(self, ax, ox, oy, flip):
        self.ax, self.ox, self.oy, self.flip = ax, ox, oy, flip

    def xy(self, x, y):
        return (self.ox + (BW - x if self.flip else x), self.oy + y)

    def hole(self, c, r):
        return self.xy(X0 + c * P, Y0 + r * P)


def draw_board(v, title):
    ax = v.ax
    ax.add_patch(FancyBboxPatch((v.ox, v.oy), BW, BH, boxstyle="round,pad=0,rounding_size=1",
                                fc=PERF, ec=PERF_EDGE, lw=1.4, zorder=1))
    for cx in (CORNER, BW - CORNER):
        for cy in (CORNER, BH - CORNER):
            px, py = v.xy(cx, cy)
            ax.add_patch(Circle((px, py), KEEP, fc="#ffffff", ec=GREY, lw=0.8, ls="--", alpha=0.45, zorder=1.5))
            ax.add_patch(Circle((px, py), 1.6, fc="white", ec=PERF_EDGE, lw=1.0, zorder=2))
    for c in range(COLS):
        for r in range(ROWS):
            px, py = v.hole(c, r)
            ax.add_patch(Circle((px, py), 0.72, fc=COPPER, ec="#a8862e", lw=0.4, zorder=2))
            ax.add_patch(Circle((px, py), 0.38, fc="#1b3a20", ec="none", zorder=2.1))
    for c in range(COLS):
        px, _ = v.hole(c, 0)
        ax.text(px, v.oy - 1.0, str(c + 1), ha="center", va="top", fontsize=4.6, color=GREY)
    for r in range(ROWS):
        _, py = v.hole(0, r)
        ax.text(v.ox - 1.2, py, ROWNAMES[r], ha="right", va="center", fontsize=4.6, color=GREY)
    ax.text(v.ox, v.oy + BH + 12, title, ha="left", va="bottom", fontsize=10, fontweight="bold", color=INK)


def draw_link(v, lid, net, path, solid):
    pts = [v.hole(*h) for h in path]
    color = NET_COLOR[net]
    xs, ys = zip(*pts)
    if not solid:
        v.ax.plot(xs, ys, color=color, lw=1.2, ls=(0, (2, 1.5)), alpha=0.5, zorder=3)
        return
    v.ax.plot(xs, ys, color="white", lw=3.6, solid_capstyle="round", solid_joinstyle="round", zorder=5)
    v.ax.plot(xs, ys, color=SOLDER, lw=2.6, solid_capstyle="round", solid_joinstyle="round", zorder=5.1)
    v.ax.plot(xs, ys, color=color, lw=1.0, solid_capstyle="round", solid_joinstyle="round", zorder=5.2)
    for h in cells(path):
        v.ax.add_patch(Circle(v.hole(*h), 0.95, fc=SOLDER, ec=color, lw=0.6, zorder=5.3))
    segs = list(zip(pts, pts[1:]))
    (a, b) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    off = LINK_TAG.get(lid, (0, 1.6) if abs(b[0] - a[0]) > abs(b[1] - a[1]) else (1.8, 0))
    off = (-off[0], off[1]) if v.flip else off
    tag(v.ax, (mx + off[0], my + off[1]), lid, color, fs=5.2, z=9)


# Where a link's tag goes, from the middle of its longest run (mm, parts-side x).
LINK_TAG = {"W1": (4.5, 1.3), "W2": (-1.6, 0), "W3": (-1.6, 0), "W4": (1.6, 0), "W5": (-2.5, -1.3),
            "W6": (-1.6, 0.4), "W7": (-1.6, 0.2), "W8": (1.5, 0.2), "W9": (-1.6, 0), "W10": (-1.6, 0),
            "W11": (-1.6, -0.4), "W12": (1.5, -0.4), "W13": (-1.6, 0), "W14": (0, -1.6),
            "W15": (1.6, 0), "W16": (0, 1.6), "W17": (0, 1.3), "W18": (0, -1.3)}


def draw_chip(v, faint=False):
    ax = v.ax
    a = 0.3 if faint else 1
    (x0, y0), (x1, y1) = v.hole(3, 1), v.hole(9, 4)
    xa, xb = sorted((x0, x1))
    ax.add_patch(Rectangle((xa - 1.6, y0 + 1.0), xb - xa + 3.2, y1 - y0 - 2.0, fc="#1c1c1c", ec=INK, lw=0.7,
                           zorder=6.4, alpha=a))
    nx = x0 - (1.6 if not v.flip else -1.6)
    ax.add_patch(Circle((nx, (y0 + y1) / 2), 1.0, fc=PERF if not faint else "#1c1c1c", ec=INK, lw=0.6,
                        zorder=6.5, alpha=a))
    for n, h in CHIP.items():
        px, py = v.hole(*h)
        ax.add_patch(Rectangle((px - 0.5, py - 0.6), 1.0, 1.2, fc="#c9ced6", ec=INK, lw=0.4, zorder=6.45, alpha=a))
        if not faint:   # pin number and name, just inside the body
            ax.text(px, py + (-2.0 if h[1] == 4 else 2.0), f"{n}\n{CHIP_PINS[n]}", ha="center",
                    va="center", fontsize=3.5, color="white", zorder=7.5, linespacing=1.0)
    if not faint:
        ax.text((xa + xb) / 2, (y0 + y1) / 2 - 0.1, "74AHCT125", ha="center", va="center", fontsize=5.6,
                fontweight="bold", color="white", zorder=7)
        ax.text(nx + (2.2 if not v.flip else -2.2), (y0 + y1) / 2 - 2.2, "notch", ha="left", va="center",
                fontsize=3.8, color="#c9ced6", zorder=7)


def draw_cap(v, faint=False):
    (xa, ya), (xb, yb) = v.hole(*CAP["a"]), v.hole(*CAP["b"])
    a = 0.3 if faint else 1
    v.ax.add_patch(Circle(((xa + xb) / 2 - (1.6 if not v.flip else -1.6), (ya + yb) / 2), 1.6, fc="#e0a100",
                          ec=INK, lw=0.6, zorder=6.4, alpha=a))
    for (x, y) in ((xa, ya), (xb, yb)):
        v.ax.plot([x, (xa + xb) / 2 - (1.6 if not v.flip else -1.6)], [y, (ya + yb) / 2], color="#9aa0a8",
                  lw=0.9, zorder=6.3, alpha=a)
    if not faint:
        v.ax.text((xa + xb) / 2 - 5.2, (ya + yb) / 2, "C1\n100 nF", ha="center", va="center", fontsize=4.6,
                  fontweight="bold", color=INK, zorder=9, linespacing=1.05,
                  bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))


def draw_headers(v, faint=False):
    a = 0.3 if faint else 1
    for hn, hp in HEADERS.items():
        xs, ys = zip(*(v.hole(*h) for h in hp.values()))
        v.ax.add_patch(Rectangle((min(xs) - 1.27, min(ys) - 1.27), 2.54, max(ys) - min(ys) + 2.54, fc="#1c1c1c",
                                 ec=INK, lw=0.6, zorder=6.4, alpha=a))
        for k, h in hp.items():
            px, py = v.hole(*h)
            v.ax.add_patch(Rectangle((px - 0.35, py - 0.35), 0.7, 0.7, fc=COPPER, ec="none", zorder=6.5, alpha=a))
            if not faint:
                v.ax.text(px + (1.9 if not v.flip else -1.9), py, {"S": "S", "+": "+", "-": "−"}[k], ha="center",
                          va="center", fontsize=5.2, fontweight="bold", color="white", zorder=9)
        if not faint:
            v.ax.text(xs[0], max(ys) + 2.6, "pan" if hn == "HP" else "tilt", ha="center", va="bottom",
                      fontsize=5.6, fontweight="bold", color="white", zorder=9)


# Leads: how each runs off the board (holes; fractions run between them), ending at its tag.
LEAD_PATH = {
    "VCC": [(3, 5), (2.5, 5.5), (2.5, 8.2), (1, 8.8), (1, 9.6)],
    "GND": [(10, 2), (10.5, 2.5), (10.5, 8.2), (12, 8.8), (12, 9.6)],
    "L1": [(4, 0), (3.5, -0.5), (3.5, -2.4), (2, -3.0), (2, -3.8)],
    "L2": [(5, 0), (5.5, -0.5), (5.5, -2.4), (7, -3.0), (7, -3.8)],
    "M1": [(7, 0), (7.5, -0.5), (7.5, -2.0), (12, -2.6), (12, -3.8)],
    "M2": [(8, 5), (7.5, 5.5), (7.5, 8.2), (6.5, 8.8), (6.5, 9.6)],
    "SVP": [(22, 2), (22.5, 1.5), (22.5, -2.0), (21, -2.6), (21, -3.8)],
    "SVN": [(22, 3), (22.5, 3.5), (22.5, 8.2), (21, 8.8), (21, 9.6)],
}


def hole_f(v, c, r):
    return v.xy(X0 + c * P, Y0 + r * P)


def draw_leads(v, leads):
    for name, (h, tg, where, color) in leads.items():
        pts = [hole_f(v, *q) for q in LEAD_PATH[name]]
        xs, ys = zip(*pts)
        v.ax.plot(xs, ys, color="white", lw=3.6, solid_capstyle="round", solid_joinstyle="round", zorder=7)
        v.ax.plot(xs, ys, color=color, lw=2.0, solid_capstyle="round", solid_joinstyle="round", zorder=7.1)
        v.ax.add_patch(Circle(pts[0], 1.0, fc=color, ec="white", lw=0.6, zorder=7.2))
        ex, ey = pts[-1]
        up = ey > pts[0][1]
        tag(v.ax, (ex, ey + (1.5 if up else -1.5)), tg, color, fs=6.2)
        v.ax.text(ex, ey + (3.2 if up else -3.2), where, ha="center", va="bottom" if up else "top",
                  fontsize=5.2, color=INK, zorder=9)


def lead_rings(v, leads):
    for name, (h, tg, where, color) in leads.items():
        x, y = v.hole(*h)
        v.ax.add_patch(Circle((x, y), 1.15, fc="none", ec=color, lw=1.6, zorder=8))


def render(servos):
    leads, links, pins = check(servos)
    W, H = 118, 118
    fig = plt.figure(figsize=(W / 9.8, H / 9.8), dpi=170)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")
    which = ("servos on the Pi (SERVO_DRIVER = \"pigpio\")" if servos == "pigpio"
             else "servos on the PTZ controller (SERVO_DRIVER = \"arducam\")")
    ax.text(5, H - 4, "Level shifter (#8) on the 2 × 8 cm perfboard, hole by hole", fontsize=12,
            fontweight="bold", color=INK, va="top")
    ax.text(5, H - 9.5,
            f"Both builds, {which}. R5, R7, L1, L2, M1, M2 are the leads in docs/<build>/setup/12-wiring.md;\n"
            "W1–W18 are the solder links in docs/setup/12b-level-shifter.md. Holes are named by row letter and "
            "column number (B4 = row B, column 4).\nDashed circles: the standoffs and their screw heads; keep them clear.",
            fontsize=6.0, color=GREY, va="top", linespacing=1.45)

    top = View(ax, 22, 68, flip=False)
    draw_board(top, "1 · Parts side: place the parts like this")
    for lid, (net, path) in links.items():
        draw_link(top, lid, net, path, solid=False)
    draw_chip(top)
    draw_cap(top)
    if servos == "pigpio":
        draw_headers(top)
    draw_leads(top, leads)

    bot = View(ax, 22, 22, flip=True)
    draw_board(bot, "2 · Solder side, board turned over left to right: make the links like this")
    draw_chip(bot, faint=True)
    draw_cap(bot, faint=True)
    if servos == "pigpio":
        draw_headers(bot, faint=True)
    for lid, (net, path) in links.items():
        draw_link(bot, lid, net, path, solid=True)
    lead_rings(bot, leads)

    ky = 15
    rows = [(GND, "GND (W1–W9: the two buses under the chip and the stubs to them)"), (V5, "+5 V to the chip"),
            (DATA, "LED ring data, 3.3 V in, 5 V out")]
    if servos == "pigpio":
        rows += [(PWM, "servo PWM, 3.3 V in, 5 V out to the headers"), (SERVO5, "+5 V to the servo headers")]
    for i, (col, txt) in enumerate(rows):
        yy = ky - i * 2.8
        x = 8 if i < 3 else 62
        yy = ky - (i if i < 3 else i - 3) * 2.8
        ax.plot([x, x + 7], [yy, yy], color=SOLDER, lw=2.6, solid_capstyle="round")
        ax.plot([x, x + 7], [yy, yy], color=col, lw=1.0)
        ax.text(x + 9, yy, txt, fontsize=5.8, color=INK, va="center")

    out = OUT.format("" if servos == "pigpio" else "-arducam")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=170, facecolor="white")
    print("wrote", os.path.relpath(out))


if __name__ == "__main__":
    for s in ("pigpio", "arducam"):
        render(s)
