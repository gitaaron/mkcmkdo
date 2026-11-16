#!/usr/bin/env python3
"""Draw what to measure on each bought part, for the "Before you print" table in
docs/*/setup/15-verification.md.

Each drawing is an isometric sketch of the part with its dimensions labelled by
the key they go into in cad/ordered_parts.toml. Proportions come from that
file, so a sketch looks roughly like the part it describes; the labels carry
no numbers, so the drawings stay right after you edit the values.

Usage:  python3 cad/render_measure_diagrams.py      (from sport_cam/)
Writes: docs/with_uwb/images/measure/*.png
        docs/without_uwb/images/measure/*.png       (the parts that build uses)
"""
import math
import os
import tomllib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "..", "docs")
with open(os.path.join(HERE, "ordered_parts.toml"), "rb") as f:
    P = tomllib.load(f)

INK = "#1a2233"
DIM = "#d64541"        # dimension lines and the key names on them
NOTE = "#4a5d85"
PCB = "#2e7d4f"
METAL = "#b8bec9"
DARK = "#3a3f4a"
BLUE = "#8fa8d8"
WOOD = "#d9b27c"
BRASS = "#d4a73c"
WHITE_PLASTIC = "#eceff4"

COS30, SIN30 = math.cos(math.radians(30)), 0.5
VIEW = (1, 1, 1)       # towards the viewer: +x, +y and +z faces show


# Isometric projection: x runs down to the right, y down to the left, z up.
def iso(p):
    x, y, z = p
    return ((x - y) * COS30, z - (x + y) * SIN30)


def depth(p):
    return p[0] + p[1] + p[2]


def shade(color, normal):
    """Flat lighting: the light comes from above, a little left."""
    import matplotlib.colors as mc
    r, g, b = mc.to_rgb(color)
    nx, ny, nz = normal
    k = 0.62 + 0.38 * max(0.0, 0.25 * nx + 0.55 * ny + 0.8 * nz)
    return (min(1, r * k), min(1, g * k), min(1, b * k))


class Scene:
    """A painter's-algorithm isometric scene: solids are lists of faces, drawn
    back to front; dimensions and labels go on top."""

    def __init__(self, ax):
        self.ax = ax
        self.faces = []    # (layer, depth, verts3d, color, edge, lw)
        self.pts = []
        self.layer = 0     # raise it for things that sit on a surface (holes, parts on a board)

    def _add(self, f):
        self.faces.append((self.layer,) + f)

    def face(self, verts, color, normal=None, edge=INK, lw=0.7, bias=0.0):
        if normal is not None and sum(n * v for n, v in zip(normal, VIEW)) <= 1e-9:
            return
        d = sum(depth(v) for v in verts) / len(verts) + bias
        fc = shade(color, normal) if normal is not None else color
        self._add((d, verts, fc, edge, lw))
        self.pts += verts

    def box(self, x0, y0, z0, dx, dy, dz, color, edge=INK, lw=0.7, bias=0.0):
        x1, y1, z1 = x0 + dx, y0 + dy, z0 + dz
        F = [
            ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
            ([(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)], (0, 0, -1)),
            ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
            ([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], (-1, 0, 0)),
            ([(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)], (0, 1, 0)),
            ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
        ]
        # one depth for the whole box keeps its faces together in the sort
        c = depth((x0 + dx / 2, y0 + dy / 2, z0 + dz / 2)) + bias
        for v, n in F:
            if sum(a * b for a, b in zip(n, VIEW)) > 0:
                self._add((c + 0.01 * sum(n), v, shade(color, n), edge, lw))
                self.pts += v

    def cyl(self, c, r, h, color, axis="z", n=48, edge=INK, lw=0.7, bias=0.0):
        """A cylinder from c along +axis for h."""
        cx, cy, cz = c

        def pt(a, t):
            u, v = r * math.cos(a), r * math.sin(a)
            if axis == "z":
                return (cx + u, cy + v, cz + t)
            if axis == "x":
                return (cx + t, cy + u, cz + v)
            return (cx + u, cy + t, cz + v)

        def nrm(a):
            u, v = math.cos(a), math.sin(a)
            return {"z": (u, v, 0), "x": (0, u, v), "y": (u, 0, v)}[axis]

        mid = {"z": (cx, cy, cz + h / 2), "x": (cx + h / 2, cy, cz), "y": (cx, cy + h / 2, cz)}[axis]
        base = depth(mid) + bias
        side = []
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            nm = nrm((a0 + a1) / 2)
            if sum(p * q for p, q in zip(nm, VIEW)) > 0:
                side.append(([pt(a0, 0), pt(a1, 0), pt(a1, h), pt(a0, h)], nm))
        for v, nm in side:
            self._add((base, v, shade(color, nm), shade(color, nm), 0.3))
            self.pts += v
        # silhouette: two outline strokes via the cap edges
        cap_n = {"z": (0, 0, 1), "x": (1, 0, 0), "y": (0, 1, 0)}[axis]
        cap = [pt(2 * math.pi * i / n, h) for i in range(n)]
        bot = [pt(2 * math.pi * i / n, 0) for i in range(n)]
        self._add((base + 0.02, cap, shade(color, cap_n), edge, lw))
        self.pts += cap + bot
        return cap, bot

    def disc(self, c, r, color, axis="z", n=40, bias=0.05, edge=INK, lw=0.6):
        """A flat circle (a hole, a mark) on a face."""
        cx, cy, cz = c
        if axis == "z":
            v = [(cx + r * math.cos(a), cy + r * math.sin(a), cz) for a in self._angles(n)]
        elif axis == "x":
            v = [(cx, cy + r * math.cos(a), cz + r * math.sin(a)) for a in self._angles(n)]
        else:
            v = [(cx + r * math.cos(a), cy, cz + r * math.sin(a)) for a in self._angles(n)]
        self._add((depth(c) + bias, v, color, edge, lw))
        self.pts += v

    def poly(self, verts, color, bias=0.05, edge=INK, lw=0.6):
        self._add((sum(depth(v) for v in verts) / len(verts) + bias, verts, color, edge, lw))
        self.pts += verts

    @staticmethod
    def _angles(n):
        return [2 * math.pi * i / n for i in range(n)]

    def draw(self):
        for _, d, v, fc, ec, lw in sorted(self.faces, key=lambda f: (f[0], f[1])):
            self.ax.add_patch(Polygon([iso(p) for p in v], closed=True, fc=fc, ec=ec, lw=lw,
                                      joinstyle="round", zorder=2))

    # ---- dimensions --------------------------------------------------------

    def dim(self, p1, p2, off, key, note=None, text_off=(0, 0), ha="center", ext=True):
        """A dimension from p1 to p2, drawn displaced by `off` (3D), with
        extension lines back to the part and the key name at the middle."""
        a = tuple(p + o for p, o in zip(p1, off))
        b = tuple(p + o for p, o in zip(p2, off))
        if ext and any(abs(o) > 1e-9 for o in off):
            L = math.sqrt(sum(o * o for o in off))
            over = tuple(o / L * 2 for o in off)
            for p, q in ((p1, a), (p2, b)):
                s = tuple(pp + 0.15 * oo / L * 2 for pp, oo in zip(p, off))
                e = tuple(qq + o for qq, o in zip(q, over))
                self.ax.plot(*zip(iso(s), iso(e)), color=DIM, lw=0.8, zorder=5)
        self.ax.add_patch(FancyArrowPatch(iso(a), iso(b), arrowstyle="<|-|>", mutation_scale=9,
                                          color=DIM, lw=1.1, shrinkA=0, shrinkB=0, zorder=6))
        self.pts += [a, b]
        m = iso(tuple((u + v) / 2 for u, v in zip(a, b)))
        self.label(m, key, note, text_off, ha)

    def label(self, xy, key, note=None, text_off=(0, 0), ha="center", leader=False):
        x, y = xy[0] + text_off[0], xy[1] + text_off[1]
        if leader:
            self.ax.annotate("", xy=xy, xytext=(x, y), zorder=6,
                             arrowprops=dict(arrowstyle="-|>", color=DIM, lw=0.9, mutation_scale=9,
                                             shrinkA=2, shrinkB=1))
        s = key if not note else f"{key}\n{note}"
        self.ax.text(x, y, s, ha=ha, va="center", fontsize=8.6, family="monospace",
                     color=DIM, fontweight="bold", zorder=7,
                     bbox=dict(boxstyle="round,pad=0.22", fc="white", ec=DIM, lw=0.7))

    def callout(self, p3, key, note=None, text_off=(10, 10), ha="left"):
        self.label(iso(p3), key, note, text_off, ha, leader=True)
        self.pts.append(p3)

    def text(self, p3, s, off=(0, 0), **kw):
        x, y = iso(p3)
        kw.setdefault("fontsize", 7.6)
        kw.setdefault("color", NOTE)
        kw.setdefault("ha", "center")
        kw.setdefault("va", "center")
        self.ax.text(x + off[0], y + off[1], s, zorder=7, style="italic", **kw)

    def fit(self, pad=12):
        xs = [iso(p)[0] for p in self.pts]
        ys = [iso(p)[1] for p in self.pts]
        self.ax.set_xlim(min(xs) - pad, max(xs) + pad)
        self.ax.set_ylim(min(ys) - pad, max(ys) + pad)
        self.ax.set_aspect("equal")
        self.ax.axis("off")


# ---- 2D side-view helpers (for the panel parts, where a section says more) --

def dim2(ax, a, b, key, off=(0, 0), ha="center", va="center", note=None):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="<|-|>", mutation_scale=9, color=DIM, lw=1.1,
                                 shrinkA=0, shrinkB=0, zorder=6))
    m = ((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1])
    s = key if not note else f"{key}\n{note}"
    ax.text(*m, s, ha=ha, va=va, fontsize=8.6, family="monospace", color=DIM, fontweight="bold",
            zorder=7, bbox=dict(boxstyle="round,pad=0.22", fc="white", ec=DIM, lw=0.7))


def ext2(ax, a, b):
    ax.plot(*zip(a, b), color=DIM, lw=0.8, zorder=5)


def rect2(ax, x, y, w, h, fc, ec=INK, lw=0.8, z=2, hatch=None):
    ax.add_patch(Polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], closed=True, fc=fc,
                         ec=ec, lw=lw, zorder=z, hatch=hatch))


# ---- figure plumbing -------------------------------------------------------

def figure(title, section, notes, panels=1, size=(7.2, 5.0), ratios=None, rows=1):
    """A figure with `panels` drawing areas (in `rows` rows) and a notes strip under them."""
    import textwrap
    wrap = int(size[0] * 15)
    wrapped = [textwrap.wrap(t, wrap) for t in notes]
    n_lines = sum(len(w) for w in wrapped)
    h_notes = 0.2 * n_lines + 0.12 * len(notes) + 0.2
    cols = math.ceil(panels / rows)
    fig = plt.figure(figsize=(size[0], size[1] + h_notes), dpi=150)
    gs = fig.add_gridspec(rows + 1, cols, height_ratios=[size[1] / rows] * rows + [h_notes],
                          width_ratios=ratios, hspace=0.12, wspace=0.05)
    axes = [fig.add_subplot(gs[i // cols, i % cols]) for i in range(panels)]
    na = fig.add_subplot(gs[rows, :])
    na.axis("off")
    na.set_xlim(0, 1)
    na.set_ylim(-h_notes, 0)
    fig.suptitle(title, fontsize=13, fontweight="bold", color=INK, x=0.02, ha="left", y=0.995)
    fig.text(0.02, 1 - 0.42 / (size[1] + h_notes), f"ordered_parts.toml  →  {section}",
             fontsize=9, family="monospace", color=DIM, ha="left", va="top")
    y = -0.05
    for lines in wrapped:
        for i, ln in enumerate(lines):
            na.text(0.015 if i else 0.0, y, ("" if i else "• ") + ln, fontsize=8.2, color=INK,
                    va="top", ha="left")
            y -= 0.2
        y -= 0.12
    return fig, axes


def save(fig, name, builds=("with_uwb", "without_uwb")):
    for b in builds:
        out = os.path.join(DOCS, b, "images", "measure")
        os.makedirs(out, exist_ok=True)
        fig.savefig(os.path.join(out, name), bbox_inches="tight", facecolor="white", pad_inches=0.15)
    plt.close(fig)
    print("wrote", name, "→", ", ".join(builds))


# ============================================================================
#  1. Arducam PTZ base
# ============================================================================

def ptz():
    p = P["ptz"]
    hs, vs, D, sh, sd, ta = p["horizontal_bolt_spacing"], p["vertical_bolt_spacing"], p["base_d"], p["standoff_h"], p["servo_drop"], p["tilt_axis_h"]
    fig, (ax, ax2, ax3) = figure(
        "1 · Arducam pan-tilt base", "[ptz]",
        ["Look down on the base with the lens pointing straight ahead at mid-pan. The four standoffs make a "
         "rectangle. horizontal_bolt_spacing — side to side, between the two standoffs left and right of each other. "
         "vertical_bolt_spacing — front to back, between the two standoffs one behind the other.",
         "Both are centre to centre: measure over the outsides of the two standoffs and subtract one standoff's "
         "width. A square base has the two equal.",
         "base_d — across the bottom disc.   standoff_h — the brass standoffs, disc to foot.   servo_drop — from the "
         "underside of the bottom disc to the lowest point of the pan servo.   tilt_axis_h — from the underside of "
         "the bottom disc up to the centre of the tilt pivot.",
         "bolt_l / head_d / head_h — the M3 screws that go up through the lid into the standoffs: length under the "
         "head, and the head's width and height. Try one in a standoff first: it must be an M3 thread.",
         "ribbon_w / ribbon_l — the camera ribbon's width, and its length end to end.   lead_bundle_d — bunch the "
         "I2C/5 V lead (and the two servo leads, if the Pi will drive them) and measure across the bunch."],
        panels=3, size=(12.6, 5.0), ratios=[1.25, 1, 0.8])
    for a_ in (ax, ax2, ax3):
        a_.set_aspect("equal")
        a_.axis("off")

    # ---- side view ---------------------------------------------------------
    r = vs / 2                                              # from the side (lens to the right): the front-to-back pair
    ax.plot([-D / 2 - 14, D / 2 + 14], [0, 0], color=NOTE, lw=1.2)
    ax.text(-D / 2 - 14, -1.5, "lid", ha="left", va="top", fontsize=7.6, color=NOTE, style="italic")
    for x in (-r, r):
        rect2(ax, x - 2.75, 0, 5.5, sh, BRASS)
    rect2(ax, -D / 2, sh, D, 3, DARK)                       # bottom disc
    rect2(ax, -D / 2 + 2, sh + 3, D - 4, 11, METAL)         # bearing ring
    rect2(ax, -D / 2, sh + 14, D, 3, DARK)                  # top disc (turns)
    rect2(ax, -10, sh - sd, 40, sd, "#2a2d33")              # pan servo, hanging
    ax.text(10, sh - sd / 2, "pan servo", ha="center", va="center", fontsize=7.4, color="white", style="italic")
    # tilt bracket, servo and the camera head
    rect2(ax, -22, sh + 17, 44, 4, DARK)
    rect2(ax, -14, sh + 21, 28, ta - 21 + 14, "#3a3f4a")
    ax.add_patch(plt.Circle((0, sh + ta), 3.2, fc=METAL, ec=INK, lw=0.8, zorder=4))
    ax.plot([-9, 9], [sh + ta, sh + ta], color=DIM, lw=0.8, ls="-.", zorder=5)
    rect2(ax, -6, sh + ta + 14, 44, 30, "#cfd7e6")
    
    rect2(ax, 38, sh + ta + 18, 26, 22, "#1a2233")
    ax.text(16, sh + ta + 29, "camera\nhead", ha="center", va="center", fontsize=7.4, color=NOTE, style="italic")
    # cables: from the head, down the back, to the lid
    ax.add_patch(FancyArrowPatch((-6, sh + ta + 24), (-D / 2 - 8, 0), arrowstyle="-", color="#c98a1c", lw=2.2,
                                 connectionstyle="arc3,rad=0.35", zorder=3))
    ax.text(-D / 2 - 30, sh + ta + 10, "ribbon + leads\nleave the head here,\nrun down the back", ha="center",
            fontsize=7.4, color="#a06a10", style="italic")
    # dimensions
    xr = D / 2 + 9
    ext2(ax, (30, sh - sd), (xr + 2, sh - sd))
    ext2(ax, (D / 2, sh), (xr + 16, sh))
    dim2(ax, (xr, sh - sd), (xr, sh), "servo_drop", off=(18, 6), ha="left")
    ext2(ax, (r + 3, 0), (xr + 16, 0))
    dim2(ax, (xr + 14, 0), (xr + 14, sh), "standoff_h", off=(2, -13), ha="left")
    ext2(ax, (9, sh + ta), (xr + 2, sh + ta))
    dim2(ax, (xr, sh), (xr, sh + ta), "tilt_axis_h", off=(1.5, 4), ha="left")
    ax.set_xlim(-D / 2 - 58, xr + 100)
    ax.set_ylim(-14, sh + ta + 52)
    ax.set_title("from the side", fontsize=9, color=INK, pad=2)

    # ---- from above --------------------------------------------------------
    import numpy as np
    th = np.linspace(0, 2 * np.pi, 120)
    ax2.fill(D / 2 * np.cos(th), D / 2 * np.sin(th), fc="#4a4f57", ec=INK, lw=1)
    ax2.fill((D / 2 - 2) * np.cos(th), (D / 2 - 2) * np.sin(th), fc="#3a3f4a", ec="none")
    # lens forward is drawn pointing up: standoffs at (±h/2, ±v/2)
    pts = [(hs / 2, vs / 2), (-hs / 2, vs / 2), (-hs / 2, -vs / 2), (hs / 2, -vs / 2)]
    for x, y in pts:
        ax2.add_patch(Polygon([(x + 3.2 * math.cos(math.radians(60 * i)), y + 3.2 * math.sin(math.radians(60 * i)))
                               for i in range(6)], closed=True, fc=BRASS, ec=INK, lw=0.8, zorder=3))
    rect2(ax2, -10, -10, 20, 40, "#2a2d33", z=2)
    ax2.add_patch(FancyArrowPatch((0, 0), (0, D / 2 + 20), arrowstyle="-|>", mutation_scale=12, color=NOTE, lw=1.4,
                                  zorder=4))
    ax2.text(0, D / 2 + 22, "lens, at mid-pan", ha="center", va="bottom", fontsize=7.6, color=NOTE, style="italic")
    dim2(ax2, pts[1], pts[0], "horizontal_bolt_spacing", off=(0, -9))
    xv = D / 2 + 7                                          # front to back, down the outside of the disc
    ext2(ax2, (pts[0][0] + 4, pts[0][1]), (xv + 2, pts[0][1]))
    ext2(ax2, (pts[3][0] + 4, pts[3][1]), (xv + 2, pts[3][1]))
    ax2.add_patch(FancyArrowPatch((xv, pts[3][1]), (xv, pts[0][1]), arrowstyle="<|-|>", mutation_scale=9, color=DIM,
                                  lw=1.1, shrinkA=0, shrinkB=0, zorder=6))
    ax2.text(xv, 0, "vertical_bolt_spacing", rotation=90, ha="center", va="center", fontsize=8.6,
             family="monospace", color=DIM, fontweight="bold", zorder=7,
             bbox=dict(boxstyle="round,pad=0.22", fc="white", ec=DIM, lw=0.7))
    ext2(ax2, (-D / 2, 0), (-D / 2, -D / 2 - 12))
    ext2(ax2, (D / 2, 0), (D / 2, -D / 2 - 12))
    dim2(ax2, (-D / 2, -D / 2 - 9), (D / 2, -D / 2 - 9), "base_d", off=(0, -5))
    ax2.set_xlim(-D / 2 - 14, D / 2 + 16)
    ax2.set_ylim(-D / 2 - 22, D / 2 + 32)
    ax2.set_title("from above (standoffs under the disc)", fontsize=9, color=INK, pad=2)

    # ---- the screw, the ribbon and the leads -------------------------------
    L, hd, hh = p["bolt_l"], p["head_d"], p["head_h"]
    rect2(ax3, -hd / 2, -hh, hd, hh, METAL)
    rect2(ax3, -1.5, 0, 3, L, METAL)
    for i in range(int(L / 0.5)):
        ax3.plot([-1.5, 1.5], [i * 0.5, i * 0.5 + 0.25], color=DARK, lw=0.3, zorder=3)
    ext2(ax3, (1.6, L), (6.5, L))
    ext2(ax3, (hd / 2, 0), (6.5, 0))
    dim2(ax3, (5.5, 0), (5.5, L), "bolt_l", off=(1.2, 0), ha="left")
    ext2(ax3, (-hd / 2, -hh), (-hd / 2, -hh - 3.5))
    ext2(ax3, (hd / 2, -hh), (hd / 2, -hh - 3.5))
    dim2(ax3, (-hd / 2, -hh - 2.5), (hd / 2, -hh - 2.5), "head_d", off=(0, -2.2))
    ext2(ax3, (-hd / 2, 0), (-6, 0))
    ext2(ax3, (-hd / 2, -hh), (-6, -hh))
    dim2(ax3, (-5, -hh), (-5, 0), "head_h", off=(-1.0, 0), ha="right")
    ax3.text(0, L + 1.5, "M3 screw, up through\nthe lid into a standoff", ha="center", va="bottom", fontsize=7.6,
             color=NOTE, style="italic")
    # ribbon, lying flat with a fold drawn to show it is long
    y0, k = -30, 16 / p["ribbon_w"]
    w = p["ribbon_w"] * k * 0.5
    rect2(ax3, -12, y0, 24, w, "#e3c06a", ec="#a06a10")
    for i in range(1, 6):
        ax3.plot([-12, 12], [y0 + i * w / 6, y0 + i * w / 6], color="#a06a10", lw=0.4, zorder=3)
    rect2(ax3, -12, y0, 2.2, w, "#4b6ed6", ec=INK, lw=0.5, z=3)
    rect2(ax3, 9.8, y0, 2.2, w, "#4b6ed6", ec=INK, lw=0.5, z=3)
    ext2(ax3, (-12, y0), (-12, y0 - 4.5))
    ext2(ax3, (12, y0), (12, y0 - 4.5))
    dim2(ax3, (-12, y0 - 3.5), (12, y0 - 3.5), "ribbon_l", off=(0, -2.2))
    ext2(ax3, (12, y0), (15.5, y0))
    ext2(ax3, (12, y0 + w), (15.5, y0 + w))
    dim2(ax3, (14.5, y0), (14.5, y0 + w), "ribbon_w", off=(1.0, 0), ha="left")
    ax3.text(0, y0 + w + 1, "camera ribbon", ha="center", va="bottom", fontsize=7.6, color=NOTE, style="italic")
    # lead bundle, end on
    cy = -50
    for dx, dy, c in ((-1.6, 1.0, "#d64541"), (1.6, 1.0, "#f2a93b"), (0, -1.6, "#3a3f4a"), (-3.0, -1.4, "#eceff4"),
                      (3.0, -1.4, "#8b5a2b"), (0, 1.9, "#f2f2f2")):
        ax3.add_patch(plt.Circle((dx, cy + dy), 1.5, fc=c, ec=INK, lw=0.5, zorder=3))
    ext2(ax3, (-4.6, cy), (-4.6, cy - 7))
    ext2(ax3, (4.6, cy), (4.6, cy - 7))
    dim2(ax3, (-4.6, cy - 6), (4.6, cy - 6), "lead_bundle_d", off=(0, -2.2))
    ax3.text(0, cy + 4.6, "leads, bunched", ha="center", va="bottom", fontsize=7.6, color=NOTE, style="italic")
    ax3.set_xlim(-22, 30)
    ax3.set_ylim(cy - 12, L + 8)
    save(fig, "ptz.png")


# ============================================================================
#  2. Boards on the enclosure floor
# ============================================================================

def board_box(S, l, w, pcb_t=1.6, color=PCB):
    S.box(0, 0, 1.2, l, w, pcb_t, color)
    for x in (2.5, l - 2.5):     # pins under the board — it stands on them
        for y in (2.5, w - 2.5):
            S.box(x - 0.6, y - 0.6, 0, 1.2, 1.2, 1.2, METAL, lw=0.3)


def lwh(S, l, w, h, text_l=(0, 0), text_w=(0, 0), text_h=(0, 0)):
    S.dim((0, w, 0), (l, w, 0), (0, 9, 0), "l", text_off=text_l)
    S.dim((l, 0, 0), (l, w, 0), (9, 0, 0), "w", text_off=text_w)
    S.dim((l, 0, 0), (l, 0, h), (7, -7, 0), "h", text_off=(6 + text_h[0], text_h[1]), ha="left")


def boards():
    fig, axes = figure(
        "2 · Boards on the enclosure floor", "[buck]  [pd_trigger]  [latch]",
        ["l, w — the board's outline, or of anything that hangs over its edge (a terminal block, the USB-C socket), "
         "whichever is bigger.   l is the long side.",
         "h — stand the board on the table the way it will sit (on its pins or solder joints if they stick out "
         "underneath) and measure from the table to the top of the tallest part: inductor, heatsink, screw terminal, "
         "capacitor, or a lead bent over the top.",
         "buck: h from the bottom of its standoffs, which stay on.   hole_dx / hole_dy — standoff centre to centre, "
         "along l and along w (calipers: outside to outside, minus one standoff's width).   screw_d — their thread, 3 for M3.",
         "latch: the 3 × 7 cm perfboard on four M3 standoffs.   hole_dx / hole_dy — corner hole centre to centre "
         "(calipers: the holes' outside edges, minus one hole's width).   standoff_h — the standoffs' length.   "
         "h from the bottom of the standoffs.",
         "pd_trigger: it must have a USB-C SOCKET (a hole the cable plugs into), not a plug sticking out.   "
         "port_h — the socket's height above the board.   plug_w × plug_h — the bank cable's USB-C plug: the "
         "moulded body behind the metal, not the metal tip (the wall opening is cut to this)."],
        panels=3, size=(10.0, 7.6), rows=2)
    for ax, t in zip(axes, ("buck converter  [buck]", "PD trigger  [pd_trigger]", "power latch  [latch]")):
        ax.set_title(t, fontsize=9.5, color=INK, family="monospace", pad=2)

    # buck
    b = P["buck"]
    S = Scene(axes[0])
    so = min(10.0, b["h"] * 0.45)                                                   # standoff height, drawn
    x0, y0 = (b["l"] - b["hole_dx"]) / 2, (b["w"] - b["hole_dy"]) / 2
    for x in (x0, x0 + b["hole_dx"]):                                               # brass standoffs
        for y in (y0, y0 + b["hole_dy"]):
            S.cyl((x, y, 0), 2.5, so, "#c9a227", bias=1)
    S.box(0, 0, so, b["l"], b["w"], 1.6, "#2f5fb3")
    top = so + 1.6
    S.layer = 1
    for x in (x0, x0 + b["hole_dx"]):                                               # screw heads on top
        for y in (y0, y0 + b["hole_dy"]):
            S.disc((x, y, top), 2.3, METAL)
    S.layer = 2
    S.box(b["l"] * 0.30, b["w"] * 0.25, top, 26, 14, 2.5, "#1e3f7a", bias=3)         # display
    S.box(1.5, b["w"] / 2 - 4, top, 7, 8, b["h"] - top, "#3070d8", bias=3)          # screw terminals, IN
    S.box(b["l"] - 8.5, b["w"] / 2 - 4, top, 7, 8, b["h"] - top, "#3070d8", bias=3)   # and OUT
    lwh(S, b["l"], b["w"], b["h"])
    # hole spacing across the top, screw head to screw head: standoff centre to centre
    S.layer = 3
    yf, xr = y0 + b["hole_dy"], x0 + b["hole_dx"]
    S.dim((x0, yf, top), (xr, yf, top), (0, 0, 0), "hole_dx", text_off=(-6, -8))
    S.dim((xr, y0, top), (xr, yf, top), (0, 0, 0), "hole_dy", text_off=(10, 4), ha="left")
    S.draw()
    S.fit(pad=16)

    # PD trigger — laid out like the common black ones: USB-C socket at one end,
    # a blue screw terminal (12 V out) at the other, chip, button and LEDs between
    t = P["pd_trigger"]
    l, w, top = t["l"], t["w"], 2.8
    S = Scene(axes[1])
    board_box(S, l, w, color="#202226")
    sw, sl = 9.0, 7.5                                                               # USB-C socket
    S.box(l - sl + 0.6, w / 2 - sw / 2, top, sl, sw, t["port_h"], METAL, bias=3)
    S.poly([(l + 0.61, w / 2 - sw / 2 + 0.9, top + 0.7), (l + 0.61, w / 2 + sw / 2 - 0.9, top + 0.7),
            (l + 0.61, w / 2 + sw / 2 - 0.9, top + t["port_h"] - 0.7), (l + 0.61, w / 2 - sw / 2 + 0.9, top + t["port_h"] - 0.7)],
           "#1b1d22", bias=4, lw=0.4)                                               # its mouth
    S.box(0.4, 1.0, top, 7.5, w - 2.0, t["h"] - top, "#2f7fd6", bias=3)            # screw terminal
    for y in (w * 0.3, w * 0.7):
        S.disc((4.15, y, t["h"]), 2.1, "#7a828f", bias=4)
    S.box(l * 0.36, w * 0.2, top, l * 0.26, w * 0.32, 1.4, "#15161a", bias=2)      # chip
    S.box(l * 0.38, w * 0.62, top, 5, 5, 2.2, "#3a3d44", bias=2)                    # button
    S.cyl((l * 0.38 + 2.5, w * 0.62 + 2.5, top + 2.2), 1.5, 1.2, "#15161a", bias=3)
    for k in range(5):                                                              # voltage LEDs
        S.box(l * 0.30 + k * l * 0.07, 0.8, top, 1.2, 0.8, 0.6, "#f2f2f2", lw=0.3, bias=2)
    lwh(S, l, w, t["h"])
    S.dim((l + 0.6, w / 2 - sw / 2, top), (l + 0.6, w / 2 - sw / 2, top + t["port_h"]), (0, -5, 0),
          "port_h", text_off=(5, 6), ha="left")
    S.text((l + 0.6, w / 2, top + t["port_h"]), "USB-C socket\n(a hole, not a plug)", off=(-2, 20), ha="left")
    S.text((0.4, w / 2, t["h"]), "screw terminal\n12 V out", off=(-3, 4), ha="right")
    # the bank cable's plug, off to one side, pointing at the socket's end
    pw, ph = t["plug_w"], t["plug_h"]
    px, py, pz = l + 4, -40, top + 22
    S.box(px + 16, py - 4.2, pz + ph / 2 - 1.3, 6.5, 8.4, 2.6, METAL, bias=1)              # metal tip
    S.box(px, py - pw / 2, pz, 16, pw, ph, "#2a2d33", bias=2)                              # moulded body
    S.dim((px, py + pw / 2, pz + ph), (px, py - pw / 2, pz + ph), (0, 0, 5), "plug_w", text_off=(-3, 3), ha="right")
    S.dim((px + 16, py + pw / 2, pz), (px + 16, py + pw / 2, pz + ph), (3, 3, 0), "plug_h", text_off=(-3, 0), ha="right")
    S.text((px + 8, py - pw / 2, pz + ph), "bank cable's plug", off=(4, 6), ha="left")
    S.draw()
    S.fit(pad=16)

    # latch: the 3 × 7 cm perfboard on four M3 standoffs, like the buck
    la = P["latch"]
    S = Scene(axes[2])
    so = la["standoff_h"]
    x0, y0 = (la["l"] - la["hole_dx"]) / 2, (la["w"] - la["hole_dy"]) / 2
    for x in (x0, x0 + la["hole_dx"]):                                              # nylon standoffs
        for y in (y0, y0 + la["hole_dy"]):
            S.cyl((x, y, 0), 2.5, so, "#e8e4da", bias=1)
    S.box(0, 0, so, la["l"], la["w"], 1.6, "#3f9a4a")
    top = so + 1.6
    S.layer = 1
    for x in (x0, x0 + la["hole_dx"]):                                              # screw heads on top
        for y in (y0, y0 + la["hole_dy"]):
            S.disc((x, y, top), 2.3, METAL)
    S.layer = 2
    S.box(14, 8, top, 16, 10, la["h"] - top, DARK, bias=3)                            # MOSFET lying flat
    S.box(30, 10, top, 7, 6, 1.2, METAL, bias=4)                                       # its tab
    S.box(44, 18, top, 4, 3, 5, DARK, bias=3)                                          # 2N3904s
    S.box(44, 9, top, 4, 3, 5, DARK, bias=3)
    lwh(S, la["l"], la["w"], la["h"])
    S.layer = 3
    yf, xr = y0 + la["hole_dy"], x0 + la["hole_dx"]
    S.dim((x0, yf, top), (xr, yf, top), (0, 0, 0), "hole_dx", text_off=(-6, -8))
    S.dim((xr, y0, top), (xr, yf, top), (0, 0, 0), "hole_dy", text_off=(10, 4), ha="left")
    S.dim((x0, yf, 0), (x0, yf, so), (0, 8, 0), "standoff_h", text_off=(-4, 0), ha="right")
    S.draw()
    S.fit(pad=16)
    save(fig, "boards.png")


# ============================================================================
#  3. Rocker switch and barrel jack
# ============================================================================

def panel_parts():
    fig, (ax1, ax2, ax3) = figure(
        "3 · Round rocker switch and barrel jack", "[switch]  [jack]",
        ["switch: flange_d — across the round bezel on the front.   hole_d — across the threaded body behind it "
         "(the wall hole is cut 0.5 mm bigger).   hole_d_minus_flat — from the thread's key flat straight across to "
         "the far side; flat_side — where that flat is with ON at the top (top, bottom, left or right).   "
         "nut_d — the locking ring across its lugs.",
         "switch: nut_t — the ring's thickness.   thread_l — from the back of the bezel to the end of the thread.   "
         "depth — from the back of the bezel to the tips of the terminals.",
         "jack: hole_d — the threaded barrel's outside diameter.   body_d — the widest thing behind the panel: the nut "
         "across its corners, or the body, whichever is bigger.   depth — from the back of the front flange to the "
         "tips of the solder tags.   max_panel_t — the thread length left between the flange and the nut fully on."],
        panels=3, size=(13.0, 4.0), ratios=[1.45, 1.25, 1.25])
    sw, jk = P["switch"], P["jack"]

    # switch, front: round bezel, rocker, and the thread behind it dashed
    for a in (ax1, ax2, ax3):
        a.set_aspect("equal")
        a.axis("off")
    fd, hd_s, nd, nt, tl, d = sw["flange_d"], sw["hole_d"], sw["nut_d"], sw["nut_t"], sw["thread_l"], sw["depth"]
    from matplotlib.patches import Circle
    ax1.add_patch(Circle((0, 0), fd / 2, fc="#2a2d33", ec=INK, lw=0.8, zorder=2))
    ax1.add_patch(Circle((0, 0), fd * 0.34, fc="#1c1e22", ec=INK, lw=0.6, zorder=3))
    ax1.add_patch(Circle((0, 0), fd * 0.24, fc="#3a3d44", ec=INK, lw=0.6, zorder=4))
    ax1.text(0, fd * 0.08, "ON", ha="center", va="center", fontsize=6.5, color="#e8ecf2", zorder=5)
    ax1.text(0, -fd * 0.09, "OFF", ha="center", va="center", fontsize=6.5, color="#e8ecf2", zorder=5)
    fz = sw["hole_d_minus_flat"] - hd_s / 2                              # centre to the key flat
    fa = math.acos(max(-1.0, min(1.0, fz / (hd_s / 2))))
    prof = [(hd_s / 2 * math.sin(t), -hd_s / 2 * math.cos(t))
            for t in [fa + (2 * math.pi - 2 * fa) * i / 96 for i in range(97)]]
    ax1.add_patch(Polygon(prof, closed=True, fc="none", ec=BLUE, lw=1.4, ls="--", zorder=6))
    ax1.text(0, -fz + 1.4, "key flat", ha="center", va="bottom", fontsize=6.2, color="#9fc3ff", zorder=6)
    xd = fd / 2 + 3
    ext2(ax1, (0, hd_s / 2), (xd + 1, hd_s / 2))
    ext2(ax1, (0, -fz), (xd + 1, -fz))
    dim2(ax1, (xd, -fz), (xd, hd_s / 2), "hole_d_minus_flat", off=(1.0, 0), ha="left")
    dim2(ax1, (-fd / 2, fd / 2 + 3), (fd / 2, fd / 2 + 3), "flange_d", off=(0, 2.4))
    for x in (-fd / 2, fd / 2):
        ext2(ax1, (x, 0), (x, fd / 2 + 4))
    dim2(ax1, (-hd_s / 2, -fd / 2 - 3.5), (hd_s / 2, -fd / 2 - 3.5), "hole_d", off=(0, -2.6))
    for x in (-hd_s / 2, hd_s / 2):
        ext2(ax1, (x, 0), (x, -fd / 2 - 4.5))
    ax1.text(0, -fd / 2 - 11, "front — dashed: the thread behind the bezel, its flat drawn at the bottom",
             ha="center", fontsize=7.6, color=NOTE, style="italic")
    ax1.set_xlim(-fd / 2 - 8, fd / 2 + 32)
    ax1.set_ylim(-fd / 2 - 13, fd / 2 + 9)

    # switch, side: bezel outside (x < 0), thread, the ring screwed up against the wall, terminals
    ax = ax2
    pt = 3.0                                                              # a wall, for the picture
    rect2(ax, -3, -fd / 2, 3, fd, "#2a2d33")                              # bezel
    rect2(ax, -5, -fd * 0.24, 2, fd * 0.48, "#3a3d44")                    # rocker
    rect2(ax, 0, -hd_s / 2, tl, hd_s, "#2a2d33")                          # threaded body
    for k in range(int(tl / 1.2)):
        ax.plot([k * 1.2, k * 1.2 + 0.6], [hd_s / 2, -hd_s / 2], color="#55595f", lw=0.3, zorder=3)
    rect2(ax, tl, -hd_s / 2 + 2, d - tl - 6, hd_s - 4, "#2a2d33")           # body behind the thread
    for y in (-3, 1.5):
        rect2(ax, d - 6, y, 6, 1.4, METAL)                                # spade terminals
    rect2(ax, pt, -nd / 2, nt, nd, "#55595f")                             # ring, against the wall
    for y0, y1 in ((hd_s / 2 + 0.05, fd / 2 + 5), (-fd / 2 - 5, -hd_s / 2 - 0.05)):
        rect2(ax, 0, y0, pt, y1 - y0, "#c7cdd8", ec=NOTE, lw=0.6, z=1, hatch="////")
    ax.text(pt / 2, fd / 2 + 6.5, "wall", ha="center", fontsize=7.4, color=NOTE, style="italic")
    ax.text(pt + nt / 2, -nd / 2 - 1.2, "ring", ha="center", va="top", fontsize=7, color=NOTE, style="italic")
    ext2(ax, (0, -fd / 2 - 3), (0, -fd / 2 - 13))
    ext2(ax, (d, -3), (d, -fd / 2 - 13))
    dim2(ax, (0, -fd / 2 - 12), (d, -fd / 2 - 12), "depth", off=(0, -2.4))
    ext2(ax, (tl, -hd_s / 2), (tl, -fd / 2 - 8))
    dim2(ax, (0, -fd / 2 - 7), (tl, -fd / 2 - 7), "thread_l", off=(0, -2.4))
    ext2(ax, (pt, nd / 2), (pt, nd / 2 + 4))
    ext2(ax, (pt + nt, nd / 2), (pt + nt, nd / 2 + 4))
    dim2(ax, (pt, nd / 2 + 3), (pt + nt, nd / 2 + 3), "nut_t", off=(5.5, 2.2), ha="left")
    ext2(ax, (pt + nt, -nd / 2), (d + 6, -nd / 2))
    ext2(ax, (pt + nt, nd / 2), (d + 6, nd / 2))
    dim2(ax, (d + 5, -nd / 2), (d + 5, nd / 2), "nut_d", off=(1.2, 0), ha="left")
    ax.text(-3, -fd / 2 - 1.2, "outside", ha="center", va="top", fontsize=7.4, color=NOTE, style="italic")
    ax.text(d / 2, fd / 2 + 11, "switch, side, in the wall", ha="center", fontsize=7.6, color=NOTE, style="italic")
    ax.set_xlim(-9, d + 16)
    ax.set_ylim(-fd / 2 - 17, fd / 2 + 14)

    # jack, side
    ax = ax3
    hd, bd, jd, jp = jk["hole_d"], jk["body_d"], jk["depth"], jk["max_panel_t"]
    fl = hd + 3
    rect2(ax, -1.5, -fl / 2, 1.5, fl, METAL)                             # front flange
    thr = jp + 2.5
    rect2(ax, 0, -hd / 2, thr, hd, METAL)                                # threaded barrel
    for i in range(int(thr / 0.7)):
        ax.plot([i * 0.7, i * 0.7 + 0.35], [hd / 2, -hd / 2], color=DARK, lw=0.25, zorder=3)
    rect2(ax, jp, -bd / 2, 2.5, bd, "#9aa1ad")                           # nut, screwed fully on
    rect2(ax, thr, -hd / 2 + 1, jd - thr - 3, hd - 2, "#2a2d33")          # body
    rect2(ax, jd - 3.5, -0.6, 3.5, 1.2, BRASS)                           # solder tag
    rect2(ax, jd - 5.5, hd / 2 - 2.2, 5.5, 1.0, BRASS)
    for y0, y1 in ((hd / 2 + 0.05, bd / 2 + 6), (-bd / 2 - 6, -hd / 2 - 0.05)):
        rect2(ax, 0, y0, jp, y1 - y0, "#c7cdd8", ec=NOTE, lw=0.6, z=1, hatch="////")
    dim2(ax, (-4, -hd / 2), (-4, hd / 2), "hole_d", off=(-1, 0), ha="right")
    ext2(ax, (-1.5, -hd / 2), (-5, -hd / 2))
    ext2(ax, (-1.5, hd / 2), (-5, hd / 2))
    ext2(ax, (jp + 2.5, bd / 2), (jd + 6, bd / 2))
    ext2(ax, (jp + 2.5, -bd / 2), (jd + 6, -bd / 2))
    dim2(ax, (jd + 5, -bd / 2), (jd + 5, bd / 2), "body_d", off=(1.2, 0), ha="left")
    ext2(ax, (0, -bd / 2 - 0), (0, -bd / 2 - 9))
    ext2(ax, (jd, -0.6), (jd, -bd / 2 - 9))
    dim2(ax, (0, -bd / 2 - 8), (jd, -bd / 2 - 8), "depth", off=(0, -2.4))
    ext2(ax, (jp, bd / 2), (jp, bd / 2 + 4))
    dim2(ax, (0, bd / 2 + 3.2), (jp, bd / 2 + 3.2), "max_panel_t", off=(6.5, 2.4), ha="left")
    ax.text(jd / 2, bd / 2 + 10, "barrel jack, side, in the wall", ha="center", fontsize=7.6, color=NOTE,
            style="italic")
    ax.text(jp + 1.25, -bd / 2 - 1.2, "nut", ha="center", va="top", fontsize=7, color=NOTE, style="italic")
    ax.set_xlim(-14, jd + 20)
    ax.set_ylim(-bd / 2 - 13, bd / 2 + 12)
    save(fig, "switch_jack.png")


# ============================================================================
#  4. Pi heatsinks
# ============================================================================

def pi_heatsink():
    p = P["pi"]
    fig, (ax,) = figure(
        "4 · Pi heatsinks or fan case", "[pi] heatsink_h",
        ["heatsink_h — from the TOP surface of the Pi's circuit board (not the table, not the standoffs) to the top of "
         "the tallest heatsink. With a fan case, measure from the board's top surface to the top of the case, fan "
         "included. Easiest: lay a ruler across the top, measure down to the board at its edge."],
        size=(7.0, 4.4))
    S = Scene(ax)
    L, W, T = p["l"], p["w"], p["pcb_t"]
    hs = p["heatsink_h"]
    # turned so the heatsinks face you: USB/Ethernet at the back (x = 0), GPIO along the back-right edge (y = 0)
    S.box(0, 0, 0, L, W, T, PCB)
    pb, po = p["port_block_l"], p["port_overhang"]
    for y0, ww, hh in ((3, 15, p["port_h"]), (21, 15, p["port_h"]), (39, 14, p["port_h"] * 0.85)):
        S.box(-po, y0, T, pb + po, ww, hh, METAL, bias=-30)
    S.box(L - p["gpio_x1"], 1, T, p["gpio_x1"] - p["gpio_x0"], 5, 8.5, DARK, bias=-30)
    sinks = ((L - 37, 20, 15, 15, hs), (L - 52, 34, 9, 9, hs * 0.55), (L - 70, 30, 9, 8, hs * 0.5))
    for x, y, a_, b_, h in sinks:
        S.box(x, y, T, a_, b_, h * 0.25, "#9aa1ad", bias=10)
        for i in range(4):   # fins
            S.box(x + i * a_ / 4 + 0.6, y, T + h * 0.25, a_ / 4 - 1.2, b_, h * 0.75, "#9aa1ad", lw=0.4,
                  bias=10 + i * 0.1)
    x, y, a_, b_, h = sinks[0]
    S.dim((x + a_, y, T), (x + a_, y, T + hs), (L - x - a_ + 14, 0, 0), "heatsink_h",
          text_off=(5, 0), ha="left")
    S.callout((L, W * 0.8, T), "board top surface = zero", text_off=(6, -16))
    S.draw()
    S.fit(pad=18)
    save(fig, "pi_heatsink.png")


# ============================================================================
#  5. / 6. Power banks
# ============================================================================

def bank(section, title, name, d, far_input=False, builds=("with_uwb", "without_uwb")):
    l, w, h = d["l"], d["w"], d["h"]
    notes = [f"l × w × h — the body at its biggest: over buttons, the display, rubber feet and any bulge in the "
             f"middle. Not the cable or the plug — measure the bank alone. l is the long side, h its thickness lying flat."]
    if far_input:
        notes.append("input_on_far_end — true if the charging socket is on the end opposite the USB-A output "
                     "(the pod leaves that end open to charge through); false if both are on the same end.")
    fig, (ax,) = figure(title, section, notes, size=(7.2, 4.2))
    S = Scene(ax)
    S.box(0, 0, 0, l, w, h, DARK if not far_input else "#2a4d7a")
    if far_input:
        S.box(l - 0.01, w / 2 - 6.5, h / 2 - 2.6, 0.3, 13, 5.2, "#111", bias=1)
        S.text((l, w / 2, h / 2), "USB-A out", off=(28, -6))
        S.text((0, w / 2, h / 2), "charging in\n(far end)", off=(-24, 20))
        S.disc((0, w / 2, h / 2), 2.5, "#111", axis="x", bias=-5)
    else:
        S.box(l - 0.01, w * 0.2, h / 2 - 2.6, 0.3, 13, 5.2, "#111", bias=1)
        S.box(l - 0.01, w * 0.55, h / 2 - 1.6, 0.3, 9, 3.2, "#111", bias=1)
        for i in range(4):
            S.disc((l * 0.82 + i * 4, w * 0.5, h), 0.9, "#7fd4ff", bias=0.5, lw=0.3)
    S.dim((0, w, 0), (l, w, 0), (0, max(10, w * 0.2), 0), "l")
    S.dim((l, 0, 0), (l, w, 0), (max(10, l * 0.06), 0, 0), "w")
    S.dim((l, 0, 0), (l, 0, h), (6, -6, 0), "h", text_off=(6, 0), ha="left")
    S.text((l / 2, w / 2, h), name, fontsize=8.5, color="white")
    S.draw()
    S.fit(pad=16)
    fname = section.strip("[]") + ".png"
    save(fig, fname, builds)


# ============================================================================
#  7. ULA1
# ============================================================================

def ula1():
    u = P["ula1"]
    l, w, h = u["l"], u["w"], u["h"]
    fig, (ax,) = figure(
        "7 · Haorutech ULA1 UWB module", "[ula1]",
        ["l × w — the board outline, not counting the USB-A plug.   h — on the table, from the table to the top of the "
         "tallest part (or the plug, if that is taller).",
         "hole_dx / hole_dy — centre to centre of the corner holes, along the long side and the short side. "
         "Calipers: outside edges of two holes, minus one hole diameter.",
         "plug_overhang — from the board's end to the tip of the USB-A plug's metal.   antenna_from_end — from the "
         "far end of the board (away from the plug) to the centre of the antenna."],
        size=(7.8, 4.8))
    S = Scene(ax)
    S.box(0, 0, 0, l, w, 1.6, "#1f2f4a")
    dx, dy = u["hole_dx"], u["hole_dy"]
    x0, y0 = (l - dx) / 2, (w - dy) / 2
    ax_ = u["antenna_from_end"]
    S.layer = 1
    for x in (x0, x0 + dx):
        for y in (y0, y0 + dy):
            S.disc((x, y, 1.6), 1.35, "white")
    S.poly([(ax_ - 3, w * 0.2, 1.6), (ax_ + 3, w * 0.2, 1.6), (ax_ + 3, w * 0.8, 1.6), (ax_ - 3, w * 0.8, 1.6)],
           "#e3c06a", lw=0.5)
    S.layer = 2
    S.box(l * 0.45, w * 0.35, 1.6, 8, 8, h - 1.6, DARK)
    S.box(l - 3, w / 2 - 6, 1.6, 3, 12, 5, WHITE_PLASTIC, bias=1)
    S.box(l, w / 2 - 6, 1.6 + 0.25, u["plug_overhang"], 12, 4.5, METAL, bias=1)
    # dimensions
    S.dim((0, w, 0), (l, w, 0), (0, 12, 0), "l", text_off=(-4, -2))
    S.dim((x0, y0 + dy, 1.6), (x0 + dx, y0 + dy, 1.6), (0, w - y0 - dy + 5, 0), "hole_dx", text_off=(-3, -2))
    S.dim((x0, y0, 1.6), (x0, y0 + dy, 1.6), (-x0 - 5, 0, 0), "hole_dy", text_off=(-2, 7))
    S.dim((l, 0, 0), (l, w, 0), (u["plug_overhang"] + 6, 0, 0), "w", text_off=(3, -2), ha="left")
    S.dim((0, w, 0), (0, w, h), (-12, 0, 0), "h", text_off=(-3, 0), ha="right")
    S.dim((0, 0, 1.6), (ax_, 0, 1.6), (0, -6, 0), "antenna_from_end", text_off=(4, 6), ha="left")
    S.dim((l, w / 2 - 6, 1.6), (l + u["plug_overhang"], w / 2 - 6, 1.6), (0, -(w / 2 - 6) - 6, 0),
          "plug_overhang", text_off=(4, 4), ha="left")
    S.text((ax_, w * 0.8, 1.6), "antenna", off=(-10, -4))
    S.text((l + u["plug_overhang"], w / 2, 6), "USB-A", off=(14, 0))
    S.draw()
    S.fit(pad=10)
    save(fig, "ula1.png", ("with_uwb",))


# ============================================================================
#  8. USB extension
# ============================================================================

def usb_extension():
    e = P["usb_extension"]
    fig, ax = figure(
        "8 · USB-A extension cable ends", "[usb_extension]",
        ["female_l × female_w × female_h — the rigid socket end, from its open face to where the strain relief "
         "starts to bend.",
         "male_l — the plug end, from the shoulder where the metal stops (that sits at the Pi's port face) back to "
         "where the cable can turn: overmould plus strain relief.   male_w × male_h — that overmould's width and "
         "height; the cable slot in the wall is cut to pass it."],
        panels=2, size=(9.6, 3.8))
    ax1, ax2 = ax
    S = Scene(ax1)
    fl, fw, fh = e["female_l"], e["female_w"], e["female_h"]
    S.box(0, 0, 0, fl, fw, fh, "#2a2d33")
    S.layer = 1
    S.poly([(fl, fw / 2 - 6.2, fh / 2 - 2.3), (fl, fw / 2 + 6.2, fh / 2 - 2.3), (fl, fw / 2 + 6.2, fh / 2 + 2.3),
            (fl, fw / 2 - 6.2, fh / 2 + 2.3)], "#111")                               # socket opening
    S.layer = 0
    S.cyl((-14, fw / 2, fh / 2), 2.2, 14, "#2a2d33", axis="x", bias=-50)             # cable
    S.dim((0, fw, 0), (fl, fw, 0), (0, 8, 0), "female_l", text_off=(-3, -3))
    S.dim((fl, 0, 0), (fl, fw, 0), (8, 0, 0), "female_w", text_off=(4, -2), ha="left")
    S.dim((fl, 0, 0), (fl, 0, fh), (5, -5, 0), "female_h", text_off=(4, 0), ha="left")
    S.callout((fl, fw / 2, fh / 2), "open face", text_off=(10, 12))
    S.text((0, 0, fh), "socket end", off=(0, 12), fontsize=9, color=INK)
    S.draw()
    S.fit(pad=10)

    S = Scene(ax2)
    ml, mw, mh = e["male_l"], e["male_w"], e["male_h"]
    S.box(0, 0, 0, ml, mw, mh, "#2a2d33")
    S.box(ml, mw / 2 - 6, mh / 2 - 2.25, 12, 12, 4.5, METAL, bias=1)                 # metal plug
    S.cyl((-14, mw / 2, mh / 2), 2.2, 14, "#2a2d33", axis="x", bias=-50)
    S.dim((0, mw, 0), (ml, mw, 0), (0, 8, 0), "male_l", text_off=(-3, -3))
    S.dim((ml, 0, 0), (ml, mw, 0), (20, 0, 0), "male_w", text_off=(4, -2), ha="left")
    S.dim((0, mw, 0), (0, mw, mh), (-6, 0, 0), "male_h", text_off=(-4, 0), ha="right")
    S.callout((ml, mw / 2 + 6, mh / 2 - 2.25), "port face\n(metal starts)", text_off=(8, 22))
    S.text((0, 0, mh), "plug end", off=(0, 12), fontsize=9, color=INK)
    S.draw()
    S.fit(pad=10)
    save(fig, "usb_extension.png", ("with_uwb",))


# ============================================================================
#  9. Dowel, and the tripod nut
# ============================================================================

def dowel():
    d = P["dowel"]["d"]
    fig, (ax,) = figure(
        "9 · Mast dowel", "[dowel] d",
        ["d — the dowel's diameter with calipers. Measure near both ends and in the middle, turning it a quarter turn "
         "each time (dowels are rarely round), and enter the LARGEST reading: the sockets are bored to it, and "
         "slightly loose is fine — the pinch screws take it up — but too tight won't go in."],
        size=(6.4, 3.6))
    S = Scene(ax)
    S.cyl((0, 0, 0), d / 2, 70, WOOD, axis="x")
    S.disc((70, 0, 0), d / 2 * 0.55, "#c79c62", axis="x", bias=1, lw=0.3)
    S.dim((70, -d / 2, 0), (70, d / 2, 0), (8, 0, 0), "d", text_off=(10, 0), ha="left")
    S.draw()
    S.fit(pad=14)
    save(fig, "dowel.png", ("with_uwb",))


def tripod_nut():
    t = P["tripod_nut"]
    af, th = t["af"], t["t"]
    rc = af / math.sqrt(3)                     # centre to a corner
    fig, (ax,) = figure(
        "Tripod nut", "[tripod_nut]",
        ["af — across the flats: calipers on two opposite flat sides, not the corners. The floor's hex pocket "
         "is cut to it (a standard 3/8-16 nut is 14.29 mm, 9/16 in).",
         "t — its thickness, face to face. The pocket is 9 mm deep, so it must not be thicker than that."],
        size=(5.6, 3.8))
    S = Scene(ax)
    S.cyl((0, 0, 0), rc, th, METAL, n=6)
    S.disc((0, 0, th), 4.76, "#4a4f5a", bias=1)
    S.dim((0, -af / 2, 0), (0, af / 2, 0), (8, 0, 0), "af", text_off=(4, -4), ha="left")
    cx, cy = rc * math.cos(math.radians(-60)), rc * math.sin(math.radians(-60))
    S.dim((cx, cy, 0), (cx, cy, th), (5, -5, 0), "t", text_off=(3, 0), ha="left")
    S.text((-rc, 0, th / 2), "3/8-16 inside", off=(-10, 0), ha="right")
    S.draw()
    S.fit(pad=14)
    save(fig, "tripod_nut.png")


if __name__ == "__main__":
    ptz()
    boards()
    panel_parts()
    pi_heatsink()
    bank("[power_bank]", "5 · Camera power bank", "25 000 mAh bank", P["power_bank"])
    bank("[tag_bank]", "6 · Wearable power bank", "slim bank", P["tag_bank"], far_input=True, builds=("with_uwb",))
    ula1()
    usb_extension()
    dowel()
    tripod_nut()
