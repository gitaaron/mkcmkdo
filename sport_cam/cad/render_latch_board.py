#!/usr/bin/env python3
"""Draw the power latch's perfboard layout, hole by hole, for the latch guide.

  → docs/setup/images/power-latch-board.png

Two views of the 3 × 7 cm double-sided board (BOM 13a.10, 24 × 10 holes):
the parts side, as you place the parts, and the solder side, flipped left to
right as you see it with the board turned over, with every solder link (W1–
W18) and the leads off the board tagged with their numbers in
docs/<build>/setup/12-wiring.md. The circuit is the same in both builds.

The layout is checked before it is drawn: every link and every part's legs
are joined up and compared with the latch's netlist (the circuit in
12-wiring.md), so a link that shorts two nets, a net left open, or a leg in
a hole under another part stops the script.

Usage:  python3 cad/render_latch_board.py
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle, Wedge

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "docs", "setup", "images", "power-latch-board.png")

# ---- the board -----------------------------------------------------------------
BW, BH = 70.0, 30.0          # mm, the kit's 3 × 7 cm board
COLS, ROWS = 24, 10          # holes
P = 2.54                     # pitch
X0 = (BW - (COLS - 1) * P) / 2
Y0 = (BH - (ROWS - 1) * P) / 2
CORNER = 2.0                 # mounting holes, in from each edge
KEEP = 4.6                   # standoff and screw head radius round a corner hole

INK = "#1a2233"
GREY = "#8a93a6"
PERF = "#c8a26b"
PERF_EDGE = "#8b6a3e"
COPPER = "#d9b44a"
SOLDER = "#b9c0cb"
V12 = "#c0392b"
OUTC = "#e67e22"
GND = "#222222"
SIGNAL = "#7d3cbd"
NODE = "#2f6fed"
BODY = "#e9dcc0"

NET_COLOR = {"IN": V12, "OUT": OUTC, "GND": GND, "GATE": NODE, "C": NODE, "Q3B": NODE, "Q2B": NODE,
             "SW": SIGNAL, "HOLD": SIGNAL, "SENSE": SIGNAL}

# ---- the parts: name → (kind, value, {pin: (col, row)}) ------------------------
# Q1 lies flat, label side down, metal tab up, its legs bent down into column
# 11; its body covers columns 3–10, rows 2–6. The 2N3904s stand up.
PARTS = {
    "Q1": ("to220", "IRF4905", {"S": (11, 3), "D": (11, 4), "G": (11, 5)}),
    "Q2": ("to92+x", "2N3904", {"E": (16, 2), "B": (16, 3), "C": (16, 4)}),
    "Q3": ("to92-x", "2N3904", {"C": (16, 6), "B": (16, 7), "E": (16, 8)}),
    "R1": ("res", "100k", {"a": (12, 1), "b": (12, 5)}),
    "R2": ("res", "10k", {"a": (11, 6), "b": (15, 6)}),
    "R3": ("res", "47k", {"a": (11, 7), "b": (15, 7)}),
    "R4": ("res", "100k", {"a": (15, 8), "b": (11, 8)}),
    "R5": ("res", "4.7k", {"a": (18, 7), "b": (18, 3)}),
    "R6": ("res", "100k", {"a": (17, 1), "b": (21, 1)}),
    "R7": ("res", "22k", {"a": (10, 7), "b": (6, 7)}),
    "R8": ("res", "6.8k", {"a": (6, 8), "b": (2, 8)}),
}

# Leads off the board: name → (hole, wiring-guide tag, where it goes, colour, thick)
LEADS = {
    "IN": ((11, 1), "P2", "PD trigger +12 V", V12, True),
    "S1": ((13, 1), "S1", "rocker terminal 1", V12, False),
    "OUT": ((13, 4), "P3", "buck IN+ (via diode)", OUTC, True),
    "GND": ((21, 5), "P5", "buck IN−", GND, False),
    "SW": ((10, 8), "S2", "rocker terminal 2", SIGNAL, False),
    "SENSE": ((7, 8), "S4", "Pi pin 13 (GPIO27)", SIGNAL, False),
    "HOLD": ((19, 7), "S3", "Pi pin 11 (GPIO17)", SIGNAL, False),
}

# Solder links on the underside: id → (net, [holes along it], thick)
LINKS = {
    "W1": ("IN", [(11, 3), (11, 1)], True),
    "W2": ("IN", [(11, 1), (13, 1)], False),
    "W3": ("OUT", [(11, 4), (13, 4)], True),
    "W4": ("GATE", [(11, 5), (12, 5)], False),
    "W5": ("GATE", [(11, 5), (11, 6)], False),
    "W6": ("C", [(15, 6), (16, 6), (16, 4)], False),
    "W7": ("SW", [(11, 7), (10, 7), (10, 8)], False),
    "W8": ("Q3B", [(16, 7), (15, 7), (15, 8)], False),
    "W9": ("SENSE", [(6, 7), (6, 8), (7, 8)], False),
    "W10": ("Q2B", [(16, 3), (18, 3)], False),
    "W11": ("Q2B", [(17, 3), (17, 1)], False),
    "W12": ("HOLD", [(18, 7), (19, 7)], False),
    "W13": ("GND", [(2, 9), (21, 9)], False),
    "W14": ("GND", [(2, 8), (2, 9)], False),
    "W15": ("GND", [(11, 8), (11, 9)], False),
    "W16": ("GND", [(16, 8), (16, 9)], False),
    "W17": ("GND", [(21, 9), (21, 0)], False),
    "W18": ("GND", [(16, 2), (16, 0), (21, 0)], False),
}

# The circuit (12-wiring.md, "Power latch"): net → the legs and leads on it.
NETLIST = {
    "IN": {"Q1.S", "R1.a", "lead.IN", "lead.S1"},
    "OUT": {"Q1.D", "lead.OUT"},
    "GATE": {"Q1.G", "R1.b", "R2.a"},
    "C": {"R2.b", "Q3.C", "Q2.C"},
    "SW": {"lead.SW", "R3.a", "R7.a"},
    "Q3B": {"Q3.B", "R3.b", "R4.a"},
    "Q2B": {"Q2.B", "R5.b", "R6.a"},
    "HOLD": {"R5.a", "lead.HOLD"},
    "SENSE": {"R7.b", "R8.a", "lead.SENSE"},
    "GND": {"R4.b", "Q3.E", "Q2.E", "R6.b", "R8.b", "lead.GND"},
}

BANDS = {"100k": ("#7b4a2a", "#111111", "#e6c200"), "10k": ("#7b4a2a", "#111111", "#e67e22"),
         "47k": ("#e6c200", "#8e44ad", "#e67e22"), "22k": ("#d64541", "#d64541", "#e67e22"),
         "6.8k": ("#2f6fed", "#8a93a6", "#d64541"), "4.7k": ("#e6c200", "#8e44ad", "#d64541")}


# ---- checks --------------------------------------------------------------------
def cells(path):
    """Every hole a link passes through, corner to corner along the grid."""
    out = [path[0]]
    for (c0, r0), (c1, r1) in zip(path, path[1:]):
        assert c0 == c1 or r0 == r1, f"link {path} must run along the grid"
        n = max(abs(c1 - c0), abs(r1 - r0))
        for i in range(1, n + 1):
            out.append((c0 + (c1 - c0) * i // n, r0 + (r1 - r0) * i // n))
    return out


def under_q1(c, r):
    return 3 <= c <= 10 and 2 <= r <= 6


def check():
    errs = []
    pins = {}
    for name, (_, _, legs) in PARTS.items():
        for pin, h in legs.items():
            pins[f"{name}.{pin}"] = h
    for name, (h, *_rest) in LEADS.items():
        pins[f"lead.{name}"] = h
    holes = {}
    for k, h in pins.items():
        if not k.startswith("lead.") and h in holes.values():
            errs.append(f"two legs in hole {h}")
        holes[k] = h
    for k, (c, r) in pins.items():
        if not (0 <= c < COLS and 0 <= r < ROWS):
            errs.append(f"{k} is off the board")
        if under_q1(c, r):
            errs.append(f"{k} is under Q1's body")
        x, y = X0 + c * P, Y0 + r * P
        for cx in (CORNER, BW - CORNER):
            for cy in (CORNER, BH - CORNER):
                if (x - cx) ** 2 + (y - cy) ** 2 < KEEP ** 2:
                    errs.append(f"{k} is under a standoff")
    # Bodies over holes: a resistor's body covers the holes between its legs.
    covered = {}
    for name, (kind, _, legs) in PARTS.items():
        if kind == "res":
            (c0, r0), (c1, r1) = legs["a"], legs["b"]
            for h in cells([legs["a"], legs["b"]])[1:-1]:
                covered[h] = name
    for k, h in pins.items():
        if h in covered and not k.startswith(covered[h] + "."):
            errs.append(f"{k} is in hole {h}, under {covered[h]}")
    # Join everything up.
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    link_net = {}
    for lid, (net, path, _) in LINKS.items():
        cs = cells(path)
        for h in cs:
            if under_q1(*h):
                errs.append(f"{lid} solders a pad under Q1 (its tab is +12 V)")
            union(cs[0], h)
            if link_net.setdefault(h, net) != net:
                errs.append(f"{lid} ({net}) shares hole {h} with {link_net[h]}")
    for net, members in NETLIST.items():
        roots = {find(pins[m]) for m in members}
        if len(roots) != 1:
            errs.append(f"net {net} is not joined up: {sorted(members)}")
    roots = {net: find(pins[next(iter(m))]) for net, m in NETLIST.items()}
    if len(set(roots.values())) != len(roots):
        errs.append("two nets are shorted together")
    listed = set().union(*NETLIST.values())
    if listed != set(pins):
        errs.append(f"legs not in the netlist: {sorted(set(pins) ^ listed)}")
    for k, h in pins.items():
        net = next(n for n, m in NETLIST.items() if k in m)
        if h in link_net and link_net[h] != net:
            errs.append(f"{k} ({net}) sits on a {link_net[h]} link")
    if errs:
        sys.exit("power latch layout:\n  " + "\n  ".join(errs))


# ---- drawing -------------------------------------------------------------------
def tag(ax, xy, text, color, fs=7.5, z=9):
    ax.text(xy[0], xy[1], text, ha="center", va="center", fontsize=fs, fontweight="bold",
            color="white", zorder=z, bbox=dict(boxstyle="round,pad=0.22", fc=color, ec="white", lw=0.8))


class View:
    def __init__(self, ax, ox, oy, flip):
        self.ax, self.ox, self.oy, self.flip = ax, ox, oy, flip

    def xy(self, x, y):
        return (self.ox + (BW - x if self.flip else x), self.oy + y)

    def hole(self, c, r):
        return self.xy(X0 + c * P, Y0 + r * P)


def draw_board(v, title, title_dy=3.2):
    ax = v.ax
    x, y = v.xy(0, 0) if not v.flip else v.xy(BW, 0)
    ax.add_patch(FancyBboxPatch((x, y), BW, BH, boxstyle="round,pad=0,rounding_size=1",
                                fc=PERF, ec=PERF_EDGE, lw=1.4, zorder=1))
    for cx in (CORNER, BW - CORNER):
        for cy in (CORNER, BH - CORNER):
            px, py = v.xy(cx, cy)
            ax.add_patch(Circle((px, py), KEEP, fc="#ffffff", ec=GREY, lw=0.8, ls="--", alpha=0.55, zorder=1.5))
            ax.add_patch(Circle((px, py), 1.6, fc="white", ec=PERF_EDGE, lw=1.0, zorder=2))
    for c in range(COLS):
        for r in range(ROWS):
            px, py = v.hole(c, r)
            ax.add_patch(Circle((px, py), 0.72, fc=COPPER, ec="#a8862e", lw=0.4, zorder=2))
            ax.add_patch(Circle((px, py), 0.38, fc="#3a2c1a", ec="none", zorder=2.1))
    # Column and row numbers, to count holes by.
    for c in range(0, COLS, 1):
        px, _ = v.hole(c, 0)
        ax.text(px, v.oy - 1.6, str(c + 1), ha="center", va="top", fontsize=4.6, color=GREY)
    for r in range(ROWS):
        _, py = v.hole(0, r)
        lx = v.ox - 1.2 if not v.flip else v.ox - 1.2
        ax.text(lx, py, "ABCDEFGHIJ"[r], ha="right", va="center", fontsize=4.6, color=GREY)
    ax.text(v.ox, v.oy + BH + title_dy, title, ha="left", va="bottom", fontsize=10, fontweight="bold", color=INK)


def draw_link(v, lid, net, path, thick, solid, label=True):
    pts = [v.hole(*h) for h in path]
    color = NET_COLOR[net]
    xs, ys = zip(*pts)
    if solid:
        v.ax.plot(xs, ys, color="white", lw=(5.2 if thick else 3.6), solid_capstyle="round",
                  solid_joinstyle="round", zorder=5)
        v.ax.plot(xs, ys, color=SOLDER, lw=(4.2 if thick else 2.6), solid_capstyle="round",
                  solid_joinstyle="round", zorder=5.1)
        v.ax.plot(xs, ys, color=color, lw=1.0, solid_capstyle="round", solid_joinstyle="round", zorder=5.2)
        for h in cells(path):
            v.ax.add_patch(Circle(v.hole(*h), 0.95, fc=SOLDER, ec=color, lw=0.6, zorder=5.3))
        if label:
            # the tag sits off the link, beside its longest straight run
            segs = list(zip(pts, pts[1:]))
            (a, b) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            dx, dy = (0, 1.7) if abs(b[0] - a[0]) > abs(b[1] - a[1]) else (2.0, 0)
            off = flipx(v, LABEL_NUDGE.get(lid, (dx, dy)))
            tag(v.ax, (mx + off[0], my + off[1]), lid, color, fs=5.6, z=9)
    else:
        v.ax.plot(xs, ys, color=color, lw=1.2, ls=(0, (2, 1.5)), alpha=0.55, zorder=3)


# Where a link's tag goes, from the middle of its longest run (mm, parts-side x).
LABEL_NUDGE = {"W1": (-1.9, 0), "W2": (0, -1.6), "W3": (0.4, -1.45), "W4": (0, -1.5), "W5": (-1.9, 0),
               "W6": (2.0, 0.6), "W7": (-1.9, 0), "W8": (-2.0, 0), "W9": (-1.9, 0), "W10": (0.6, -1.6),
               "W11": (-2.0, 0.2), "W12": (0, -1.5), "W13": (0, 1.6), "W14": (-2.0, 0), "W15": (-2.0, 0),
               "W16": (-2.0, 0), "W17": (2.1, 0), "W18": (0, -1.6)}


def flipx(v, off):
    return (-off[0], off[1]) if v.flip else off


def resistor(v, name, val, a, b, faint=False):
    ax = v.ax
    (x0, y0), (x1, y1) = v.hole(*a), v.hole(*b)
    alpha = 0.28 if faint else 1
    ax.plot([x0, x1], [y0, y1], color="#9aa0a8", lw=1.1, zorder=6, alpha=alpha)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    horiz = abs(x1 - x0) > abs(y1 - y0)
    L, W = 6.2, 2.3
    w, h = (L, W) if horiz else (W, L)
    ax.add_patch(FancyBboxPatch((mx - w / 2, my - h / 2), w, h, boxstyle="round,pad=0,rounding_size=1.0",
                                fc=BODY, ec=INK, lw=0.7, zorder=6.2, alpha=alpha))
    if not faint:
        for i, col in enumerate(BANDS[val] + ("#c9a227",)):
            t = -2.0 + i * 1.25 if i < 3 else 2.2
            bx, by = (mx + t, my) if horiz else (mx, my + t)
            bw, bh = (0.55, W) if horiz else (W, 0.55)
            # read the bands from leg a, like the parts list
            if horiz and x1 < x0:
                bx = mx - t
            if not horiz and y1 < y0:
                by = my - t
            ax.add_patch(Rectangle((bx - bw / 2, by - bh / 2), bw, bh, fc=col, ec="none", zorder=6.3))
        off = flipx(v, RES_LABEL.get(name, (0, 2.3) if horiz else (2.3, 0)))
        ax.text(mx + off[0], my + off[1], f"{name} {val}", ha="center", va="center", fontsize=5.4,
                fontweight="bold", color=INK, zorder=9,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.8))


RES_LABEL = {"R1": (-2.5, 0.0), "R2": (0, -1.75), "R3": (0, 0.0), "R4": (0, 1.75), "R5": (2.6, 0),
             "R6": (0, -1.9), "R7": (0, -1.75), "R8": (0, -1.75)}


def to92(v, name, val, legs, facing, faint=False):
    """A 2N3904 standing up, its flat face toward `facing` (+1: +x, −1: −x,
    parts-side directions)."""
    ax = v.ax
    alpha = 0.28 if faint else 1
    xs = [v.hole(*legs[p]) for p in "EBC"]
    cx, cy = xs[1]
    f = facing * (-1 if v.flip else 1)
    r = 2.4
    # D shape: the flat along the legs, offset a little toward the flat face
    fx = cx + f * 0.7
    theta = 90 if f > 0 else -90
    ax.add_patch(Wedge((fx, cy), r, theta, theta + 180, fc="#1c1c1c", ec=INK, lw=0.6, zorder=6.4, alpha=alpha))
    for p in "EBC":
        px, py = v.hole(*legs[p])
        ax.plot([px, fx], [py, py], color="#9aa0a8", lw=1.0, zorder=6.3, alpha=alpha)
        if not faint:
            ax.text(fx + f * 1.1, py, p, ha="center", va="center", fontsize=4.6, fontweight="bold",
                    color=INK, zorder=9)
    if not faint:
        ax.text(fx - f * 4.6, cy, f"{name}\n{val}", ha="center", va="center", fontsize=5.4,
                fontweight="bold", color=INK, zorder=9, linespacing=1.1,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.8))
        ax.text(fx + f * 2.9, cy, "flat", ha="left" if f > 0 else "right", va="center", fontsize=4.2,
                color=GREY, rotation=0, zorder=9)


def to220(v, legs, faint=False):
    """Q1 lying flat, label down, metal tab up, legs bent down into column 11."""
    ax = v.ax
    alpha = 0.28 if faint else 1
    gx, _ = v.hole(*legs["D"])
    _, yd = v.hole(*legs["D"])
    sgn = -1 if v.flip else 1          # body runs toward −x on the parts side
    body_end = gx - sgn * 2.6
    # tab and body, seen from above: the metal back (and the tab past it)
    x_far = body_end - sgn * 18.2
    xa, xb = sorted((body_end, x_far))
    ax.add_patch(Rectangle((xa, yd - 5.1), xb - xa, 10.2, fc="#1c1c1c", ec=INK, lw=0.6, zorder=6.4, alpha=alpha))
    tab_a, tab_b = sorted((body_end - sgn * 2.5, x_far))
    ax.add_patch(Rectangle((tab_a, yd - 5.0), tab_b - tab_a, 10.0, fc="#c9ced6", ec=INK, lw=0.6,
                           zorder=6.5, alpha=alpha))
    hx = x_far + sgn * 3.0
    ax.add_patch(Circle((hx, yd), 1.8, fc=PERF, ec=INK, lw=0.6, zorder=6.6, alpha=alpha))
    for p in "SDG":
        px, py = v.hole(*legs[p])
        ax.plot([px, body_end], [py, py], color="#9aa0a8", lw=1.4, zorder=6.3, alpha=alpha)
        if not faint:
            ax.text(px + sgn * 1.4, py, p, ha="center", va="center", fontsize=5.0, fontweight="bold",
                    color=INK, zorder=9)
    if not faint:
        mx = (tab_a + tab_b) / 2
        ax.text(mx, yd + 1.2, "Q1 IRF4905", ha="center", va="center", fontsize=6.5, fontweight="bold",
                color=INK, zorder=9)
        ax.text(mx, yd - 1.6, "label side DOWN\nmetal tab up = D = OUT", ha="center", va="center",
                fontsize=4.6, color=INK, zorder=9, linespacing=1.15)


def draw_parts(v, faint=False):
    for name, (kind, val, legs) in PARTS.items():
        if kind == "res":
            resistor(v, name, val, legs["a"], legs["b"], faint)
        elif kind == "to220":
            to220(v, legs, faint)
        else:
            to92(v, name, val, legs, +1 if kind.endswith("+x") else -1, faint)


# Leads: the way each runs off the board, in holes (columns, rows; fractions
# run between holes), ending where its tag goes.
LEAD_PATH = {
    "IN": [(11, 1), (10.5, 0.5), (10.5, -2), (7, -2.6), (7, -3.6)],
    "S1": [(13, 1), (13, -3.6)],
    "OUT": [(13, 4), (13.5, 3.5), (13.5, -2), (19, -2.6), (19, -3.6)],
    "GND": [(21, 5), (21.5, 5.5), (25.6, 5.5)],
    "SENSE": [(7, 8), (6.5, 8.5), (6.5, 10.9), (4, 11.5), (4, 12.4)],
    "SW": [(10, 8), (10.5, 8.5), (10.5, 10.9), (12, 11.5), (12, 12.4)],
    "HOLD": [(19, 7), (19.5, 7.5), (19.5, 10.9), (20, 11.5), (20, 12.4)],
}
# Where a lead's tag sits on the solder side, from its hole (holes).
LEAD_TAG = {"IN": (-0.5, -0.55), "S1": (0.5, -0.55), "OUT": (0.55, -0.5), "GND": (0.6, 0.5),
            "SENSE": (0.55, 0.5), "SW": (-0.5, 0.55), "HOLD": (0.55, 0.5)}


def hole_f(v, c, r):
    return v.xy(X0 + c * P, Y0 + r * P)


def draw_leads(v):
    for name, (h, tg, where, color, thick) in LEADS.items():
        pts = [hole_f(v, *q) for q in LEAD_PATH[name]]
        xs, ys = zip(*pts)
        lw = 3.4 if thick else 2.0
        v.ax.plot(xs, ys, color="white", lw=lw + 1.6, solid_capstyle="round", solid_joinstyle="round", zorder=7)
        v.ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round", solid_joinstyle="round", zorder=7.1)
        v.ax.add_patch(Circle(pts[0], 1.0, fc=color, ec="white", lw=0.6, zorder=7.2))
        ex, ey = pts[-1]
        label = ("IN" if name == "S1" else name) + " → " + where
        if name == "GND":
            tag(v.ax, (ex + 2.0, ey), tg, color, fs=6.5)
            v.ax.text(ex + 4.2, ey, label, ha="left", va="center", fontsize=5.8, color=INK, zorder=9)
            continue
        up = ey > pts[0][1]
        tag(v.ax, (ex, ey + (1.5 if up else -1.5)), tg, color, fs=6.5)
        v.ax.text(ex, ey + (3.3 if up else -3.3), label, ha="center", va="bottom" if up else "top",
                  fontsize=5.8, color=INK, zorder=9)


def lead_tags(v):
    for name, (h, tg, where, color, thick) in LEADS.items():
        x, y = v.hole(*h)
        v.ax.add_patch(Circle((x, y), 1.15, fc="none", ec=color, lw=1.6, zorder=8))
        dx, dy = LEAD_TAG[name]
        dx = -dx if v.flip else dx
        tag(v.ax, (x + dx * P, y + dy * P), tg, color, fs=5.2, z=9.5)


def render():
    check()
    W, H = 132, 158
    fig = plt.figure(figsize=(W / 9.8, H / 9.8), dpi=170)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(5, H - 4, "Power latch (#13a) on the 3 × 7 cm perfboard, hole by hole",
            fontsize=12, fontweight="bold", color=INK, va="top")
    ax.text(5, H - 9.5,
            "Both builds. P2, P3, P6 and S1–S4 are the leads in docs/<build>/setup/12-wiring.md; "
            "W1–W18 are the solder links in docs/setup/12a-power-latch.md.\n"
            "Holes are named by row letter and column number (C12 = row C, column 12). "
            "Dashed circles: the standoffs and their screw heads; keep them clear.",
            fontsize=6.3, color=GREY, va="top", linespacing=1.45)

    top = View(ax, 24, 94, flip=False)
    draw_board(top, "1 · Parts side: place the parts like this", title_dy=15)
    for lid, (net, path, thick) in LINKS.items():
        draw_link(top, lid, net, path, thick, solid=False)
    draw_parts(top)
    draw_leads(top)

    bot = View(ax, 24, 39, flip=True)
    draw_board(bot, "2 · Solder side, board turned over left to right: make the links like this")
    draw_parts(bot, faint=True)
    for lid, (net, path, thick) in LINKS.items():
        draw_link(bot, lid, net, path, thick, solid=True)
    lead_tags(bot)

    kx, ky = 8, 31
    ax.add_patch(FancyBboxPatch((kx, ky - 22), 116, 22, boxstyle="round,pad=0,rounding_size=1.5",
                                fc="#f4f6fb", ec=GREY, lw=0.8, zorder=1))
    ax.text(kx + 3, ky - 2.5, "Links on the solder side", fontsize=7.5, fontweight="bold", color=INK, va="top")
    rows = [(V12, "+12 V in (W1 and W3, thick, carry the camera's 1.7 A)"), (OUTC, "switched +12 V out"),
            (GND, "GND"), (NODE, "inside the latch: gate, collectors, bases"), (SIGNAL, "rocker and Pi signals")]
    for i, (col, txt) in enumerate(rows):
        yy = ky - 6.5 - i * 2.9
        ax.plot([kx + 4, kx + 11], [yy, yy], color=SOLDER, lw=2.6, solid_capstyle="round")
        ax.plot([kx + 4, kx + 11], [yy, yy], color=col, lw=1.0)
        ax.text(kx + 13, yy, txt, fontsize=6.2, color=INK, va="center")
    ax.text(kx + 62, ky - 6,
            "A link is bare tinned wire (a cut resistor leg)\nlaid along the holes, soldered at each one.\n\n"
            "Q1's metal tab is its drain: +12 V while the\ncamera is on. Nothing may touch it, and no pad\n"
            "under Q1 is soldered.",
            fontsize=6, color=INK, va="top", linespacing=1.4)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, dpi=170, facecolor="white")
    print("wrote", os.path.relpath(OUT))


if __name__ == "__main__":
    render()
