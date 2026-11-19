#!/usr/bin/env python3
"""SportCam fit: solve the enclosure layout, audit that every part fits,
regenerate the CAD.

    python3 cad/fit.py              solve, write the generated files, render
                                    the STLs, audit — the normal command
    python3 cad/fit.py --check      change nothing; fail if the generated
                                    files or STLs are out of date or the
                                    audit fails (the git hook and CI run this)
    python3 cad/fit.py --watch      re-run on every change to the inputs
    python3 cad/fit.py --no-render  solve, write and audit; skip OpenSCAD
    python3 cad/fit.py --deep       also intersect the real meshes with
                                    OpenSCAD (slow; CI runs it)
    --build with_uwb|without_uwb    one build only

Inputs:
    cad/ordered_parts.toml          sizes of the parts you buy
    <build>/cad/config.scad         design choices (walls, clearances, …)

Outputs, per build (all generated — don't edit by hand):
    <build>/cad/layout.scad         the solved layout, included by config.scad
    <build>/cad/layout.json         the same, plus every part's envelope
    docs/<build>/setup/assembly/layout.js for the 3D assembly guide
    <build>/cad/stl/*.stl           via render_all.sh
    src/<build>/device/sportcam/config.py  geometry constants kept in step
    cad/FIT_REPORT.md               the audit, both builds

The layout, bottom to top: the power drum, a round open-topped box the same
diameter as the enclosure, screwed under its floor. In it, the power bank in a
pocket across the middle, the buck and the power latch standing on edge
against the pocket's side walls, the PD trigger and the rocker switch on the
drum wall; the tripod screws into its floor. Then the enclosure: the LED ring
under a printed shelf, shining out through the LED window; the Raspberry Pi on
the shelf; the lid with the camera.

Only the standard library is needed for --check; rendering needs openscad,
and refreshing the guide's meshes and previews needs numpy-stl + matplotlib.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))          # sport_cam/cad
ROOT = os.path.dirname(HERE)                               # sport_cam
PARTS_FILE = os.path.join(HERE, "ordered_parts.toml")
REPORT_FILE = os.path.join(HERE, "FIT_REPORT.md")
BUILDS = ("with_uwb", "without_uwb")

PRINTER = "Bambu Lab A1 Mini"
PRINT_LIMIT = 170.0        # its 180 mm cube, less 5 mm a side for a brim
EPS = 1e-6
# the switch hole's key flat, by where it is seen from outside with ON at the top: degrees about the hole axis from the bottom
FLAT_ROT = {"bottom": 0, "right": 90, "top": 180, "left": 270}
PTZ_ENGAGE = 4.0        # M3 thread each PTZ screw needs in its standoff
SCREW_LENGTHS = (6, 8, 10, 12, 16, 20, 25, 30)   # stock screw lengths, mm
PTZ_HEAD_ARM = 45       # camera board's ribbon socket, out from the tilt axis
SERVO_CLEAR = 2.0       # air kept under the pan servo, above the lid
PTZ_WASHER_T = 0.5      # an M3 washer (DIN 125, from the screw kit) — stacked under a standoff to lift the base
PTZ_WASHERS_MAX = 6
PI_CSI = (45.0, 11.5)   # Pi 4 camera socket, from the microSD end / power edge

# Printed parts and how many separate bodies each STL should contain
# (the wearable is printed as body + lid side by side).
EXPECTED_BODIES = {"wearable_case.stl": 2}
# Boards standing on edge in the power drum, against the bank pocket's side walls, on
# M3 standoffs, screwed through the wall from inside the pocket.
EDGE_BOARDS = (("buck", "buck converter"), ("latch", "power latch"))
LABELS = dict(EDGE_BOARDS)
TRIGGER_PLUG_L = 20        # room kept in front of the PD trigger's socket for the cable's plug and its bend
DEBUG = []
# Every board on standoffs: the two on edge above; the PD trigger (two holes at its socket
# end, a printed rest under the other), screwed up through the drum floor; and the level
# shifter (on the shelf, or on the enclosure floor when the shelf has no room).
STANDOFF_BOARDS = (("buck", "buck", "buck converter"), ("latch", "latch", "power latch"),
                   ("pd_trigger", "trigger", "PD trigger"), ("shifter", "shifter", "level shifter"))


def local_holes(part):
    """A board's standoff positions, from its centre, x along l. Four corner holes
    from hole_dx × hole_dy; or, with hole_x, two holes hole_dy apart, hole_x in from
    the +x end (the PD trigger's socket end)."""
    if "hole_x" in part:
        return [(part["l"] / 2 - part["hole_x"], s * part["hole_dy"] / 2) for s in (1, -1)]
    return [(sx * part["hole_dx"] / 2, sy * part["hole_dy"] / 2) for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1))]


def screw_for(part, through):
    """The countersunk screw up through `through` mm of plastic into a standoff."""
    d = part["screw_d"]
    need = through + PTZ_ENGAGE
    return {"d": d, "hole_d": d + 0.4, "head_d": 2 * d + 0.4, "through": round(through, 3),
            "l": next((x for x in SCREW_LENGTHS if x >= need), SCREW_LENGTHS[-1])}


class NoFit(Exception):
    """No layout satisfies the constraints at this size."""


# ======================================================================
#  inputs
# ======================================================================

def load_parts(build: str) -> dict:
    with open(PARTS_FILE, "rb") as f:
        raw = tomllib.load(f)
    return {k: v for k, v in raw.items() if build in v.get("builds", BUILDS)}


def measure_todos(path: str = PARTS_FILE) -> dict:
    """{part: [keys]} still marked MEASURE_TODO in ordered_parts.toml (a comment, so read the raw text)."""
    todo: dict = {}
    section = None
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*\[(\w+)\]", line)
        if m:
            section = m.group(1)
            continue
        key = re.match(r"\s*(\w+)\s*=", line)
        if section and key and "MEASURE_TODO" in line.partition("#")[2]:
            todo.setdefault(section, []).append(key.group(1))
    return todo


_ASSIGN = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*([^;]+);")


def load_config(build: str) -> dict:
    """Numbers from config.scad above the `include <layout.scad>` line.

    They must be plain numbers or arithmetic on earlier names; anything
    derived from the layout belongs below the include."""
    path = os.path.join(ROOT, build, "cad", "config.scad")
    vals: dict = {}
    allowed = {"max": max, "min": min, "sqrt": math.sqrt, "true": True, "false": False}
    for line in open(path, encoding="utf-8"):
        line = line.split("//")[0]
        if "include" in line and "layout.scad" in line:
            break
        for stmt in line.split(";"):
            m = _ASSIGN.match(stmt + ";")
            if not m or m.group(1).startswith("$"):
                continue
            name, expr = m.group(1), m.group(2).strip()
            if not re.fullmatch(r"[\w\s\.\+\-\*/\(\),]+", expr):
                continue
            try:
                vals[name] = eval(expr, {"__builtins__": {}}, {**allowed, **vals})   # noqa: S307 — numbers only
            except Exception as e:  # pragma: no cover
                raise SystemExit(f"{path}: can't read `{name} = {expr}` ({e}); keep design constants numeric")
    return vals


# ======================================================================
#  geometry: oriented boxes and cylinders, footprint × height
# ======================================================================

@dataclass
class Box:
    name: str
    cx: float
    cy: float
    l: float
    w: float
    ang: float          # degrees, direction of l
    z0: float
    z1: float
    kind: str = "box"

    def axes(self):
        a = math.radians(self.ang)
        return (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))

    def corners(self):
        (ux, uy), (vx, vy) = self.axes()
        hl, hw = self.l / 2, self.w / 2
        return [(self.cx + sx * hl * ux + sy * hw * vx, self.cy + sx * hl * uy + sy * hw * vy)
                for sx, sy in ((1, 1), (1, -1), (-1, -1), (-1, 1))]

    def rmax(self):
        return max(math.hypot(x, y) for x, y in self.corners())


@dataclass
class Cyl:
    name: str
    cx: float
    cy: float
    r: float
    z0: float
    z1: float
    kind: str = "cyl"

    def rmax(self):
        return math.hypot(self.cx, self.cy) + self.r


def _proj(pts, ax):
    v = [p[0] * ax[0] + p[1] * ax[1] for p in pts]
    return min(v), max(v)


def overlap2d(a, b, g=0.0) -> bool:
    if a.kind == "box" and b.kind == "box":
        pa, pb = a.corners(), b.corners()
        for ax in (*a.axes(), *b.axes()):
            a0, a1 = _proj(pa, ax)
            b0, b1 = _proj(pb, ax)
            if a1 + g <= b0 + EPS or b1 + g <= a0 + EPS:
                return False
        return True
    if a.kind == "cyl" and b.kind == "cyl":
        return math.hypot(a.cx - b.cx, a.cy - b.cy) < a.r + b.r + g - EPS
    box, cyl = (a, b) if a.kind == "box" else (b, a)
    (ux, uy), (vx, vy) = box.axes()
    dx, dy = cyl.cx - box.cx, cyl.cy - box.cy
    lx, ly = dx * ux + dy * uy, dx * vx + dy * vy
    qx = max(-box.l / 2, min(box.l / 2, lx))
    qy = max(-box.w / 2, min(box.w / 2, ly))
    return math.hypot(lx - qx, ly - qy) < cyl.r + g - EPS


def collide(a, b, g=0.0) -> bool:
    if not (a.z0 < b.z1 + g - EPS and b.z0 < a.z1 + g - EPS):
        return False
    return overlap2d(a, b, g)


def place(name, local, pose):
    """local (x0, x1, y0, y1, z0, z1) in the part's frame → world Box at pose (x, y, z, deg)."""
    x0, x1, y0, y1, z0, z1 = local
    X, Y, Z, A = pose
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    a = math.radians(A)
    return Box(name, X + cx * math.cos(a) - cy * math.sin(a), Y + cx * math.sin(a) + cy * math.cos(a),
               x1 - x0, y1 - y0, A, Z + z0, Z + z1)


def polar(r, deg):
    a = math.radians(deg)
    return r * math.cos(a), r * math.sin(a)


def drum_geom(C, P):
    """The bank pocket's fixed sizes: inside length and width, the drop-in floor plate
    under the bank (it holds the tripod nut), and the top of the bank above the drum's bottom."""
    bank, nut = P["power_bank"], P["tripod_nut"]
    il, iw = bank["l"] + 2 * C["pocket_clr"], bank["w"] + 2 * C["pocket_clr"]
    plate_t = math.ceil((nut["t"] + 0.5) * 2) / 2          # the nut sits on the drum floor, in a hex hole through the plate
    ih = bank["h"] + C["pocket_head"]
    return {"il": il, "iw": iw, "ih": ih, "plate_t": plate_t, "pw": C["pocket_wall"],
            "bank_z": C["drum_floor"] + plate_t, "bank_top": C["drum_floor"] + plate_t + ih}


def edge_holes(part, b, up):
    """A board standing on edge against a pocket wall: its standoffs' (x, y, z) in the box's own
    frame, the screw axis across the wall. `up` is +1 if the components face the box's +y."""
    zc = (b.z0 + b.z1) / 2
    return [(hx, -up * b.w / 2, zc + hy) for hx, hy in local_holes(part)]


def solve_drum(build, P, C, base_d):
    """The power drum under the enclosure: where the bank pocket, the two boards on edge,
    the PD trigger, the switch and the four fixing posts go. Worked out in the pocket's frame
    (bank along +x, its open end at +x, the tripod axis at the origin), then turned so the
    open end faces bank_ang."""
    uwb = build == "with_uwb"
    R_out = base_d / 2
    R_in = R_out - C["drum_wall"]
    DF = C["drum_floor"]
    gap, wgap = C["part_gap"], C["wall_gap"]
    G = drum_geom(C, P)
    il, iw, pw = G["il"], G["iw"], G["pw"]
    tr, sw = P["pd_trigger"], P["switch"]
    zb = DF + C["board_clear"]
    DH = max(G["bank_top"], *(zb + P[k]["w"] + 0.5 for k, _ in EDGE_BOARDS))
    if uwb:
        DH = max(DH, C["arm_boss_z"] + C["arm_root_h"])
    DH = math.ceil(DH * 2) / 2
    head_r = 3.2                       # an M3 countersunk head, in the pocket wall

    # round switch: bezel outside, locking ring inside on a flat boss
    sw_r = max(sw["flange_d"], sw["nut_d"] + 4) / 2
    sw_seat_r = math.sqrt(R_out ** 2 - (sw["flange_d"] / 2 + 0.5) ** 2)
    sw_panel_t = min(C["base_wall"], sw["thread_l"] - sw["nut_t"] - 1)
    sw_zs = [z for z in (max(DF + sw["nut_d"] / 2 + 1, sw_r + 0.5), DH - sw_r - 0.5) if z + sw_r <= DH + EPS]
    half = {"switch": sw_r}
    blocked = []
    if uwb:
        hb = math.degrees((C["arm_w"] / 2 + 2 + 3) / R_out)
        blocked = [(90, hb), (270, hb), (180, hb)]

    def wall_ok(a, half_mm, extra=()):
        h = math.degrees((half_mm + 3) / R_out)
        return all(angdiff(a, b) >= h + hw for b, hw in [*blocked, *extra])

    post_r = R_in - C["drum_post_d"] / 2 + 1
    bank_angs = sorted(range(0, 360, 15), key=lambda a: (-(-math.cos(math.radians(a))), a))   # the back (180°) first
    why = {}

    def fail(stage, msg):
        why.setdefault(stage, msg)
    for dy in sorted(range(-45, 46), key=abs):
        y0 = -iw / 2 + dy
        y1 = y0 + iw
        if not (y0 + 14 < 0 < y1 - 14):
            continue
        ym = max(abs(y0), abs(y1))
        if ym >= R_out:
            continue
        x1 = math.sqrt(R_out ** 2 - ym ** 2)         # the bank's front corner reaches the outside of the wall
        x0 = x1 - il
        if not (x0 + 14 < 0 < x1 - 14):
            fail(0, "the tripod axis isn't under the bank")
            continue
        if math.hypot(x0 - pw, max(abs(y0 - pw), abs(y1 + pw))) > R_in:
            fail(1, "the bank pocket's closed end doesn't fit inside the drum")
            continue
        yc = (y0 + y1) / 2
        if x1 + C["catch_l"] > math.sqrt(R_out ** 2 - (abs(yc) + C["catch_w"] / 2) ** 2):
            continue
        BIG = R_out + 6
        pocket = Box("bank pocket", (x0 - pw + BIG) / 2, yc, BIG - (x0 - pw), iw + 2 * pw, 0, 0, DH)
        fx0 = x1 - C["finger_l"]
        fz = G["bank_z"] + C["finger_z"]          # the windows' bottom: under them the wall is whole
        fingers = [Box("finger window", (fx0 + BIG) / 2, s * (iw / 2 + pw + C["finger_d"] / 2) + yc,
                       BIG - fx0, C["finger_d"], 0, fz, DH) for s in (1, -1)]
        # each board on edge against one of the pocket's three walls: +y, -y, or the closed end
        def wall_spots(key):
            bk = P[key]
            out = []
            for wall in ("+y", "-y", "back"):
                if wall == "back":
                    xin = x0 - pw
                    c = (xin - bk["h"] / 2)
                    lo = y0 + bk["hole_dx"] / 2 + head_r + 0.5
                    hi = y1 - bk["hole_dx"] / 2 - head_r - 0.5
                    found = []
                    yy = lo
                    while yy <= hi + EPS:
                        bx = Box(LABELS[key], c, yy, bk["l"], bk["h"], 90, zb, zb + bk["w"])
                        if bx.rmax() <= R_in - wgap:
                            found.append((wall, bx, 1))
                        yy += 2
                else:
                    side = 1 if wall == "+y" else -1
                    yin = y1 + pw if side > 0 else y0 - pw
                    lo = max(x0 + bk["hole_dx"] / 2 + head_r + 0.5, x0 - pw + bk["l"] / 2)
                    hi = fx0 - 2 - bk["l"] / 2
                    found = []
                    xc = lo
                    while xc <= hi + EPS:
                        bx = Box(LABELS[key], xc, yin + side * bk["h"] / 2, bk["l"], bk["h"], 0, zb, zb + bk["w"])
                        if bx.rmax() <= R_in - wgap:
                            found.append((wall, bx, side))
                        xc += 2
                if found:          # the two ends and the middle of where it fits on this wall
                    out += sorted({id(f): f for f in (found[0], found[len(found) // 2], found[-1])}.values(),
                                  key=lambda f: found.index(f))
            return out

        spots = {k: wall_spots(k) for k, _ in EDGE_BOARDS}
        for key, label in EDGE_BOARDS:
            if not spots[key]:
                fail(2, f"the {label} ({P[key]['l']} mm long, {P[key]['h']} mm deep on edge) has no room against the bank pocket")
        combos = [(bs, ls) for bs in spots["buck"] for ls in spots["latch"]
                  if bs[0] != ls[0] or not collide(bs[1], ls[1], gap)]
        combos = [c for c in combos if not collide(c[0][1], c[1][1], gap)]
        trig_cache = {}
        for bs, ls in combos:
            id_boards = (bs[0], round(bs[1].cx, 1), round(bs[1].cy, 1), ls[0], round(ls[1].cx, 1), round(ls[1].cy, 1))
            boards = {"buck": (bs[1], bs[2]), "latch": (ls[1], ls[2])}
            walls = {"buck": bs[0], "latch": ls[0]}
            obst = [pocket, *fingers, *(b for b, _ in boards.values())]
            for bank_ang in bank_angs:
                # the opening, with the finger windows either side, must miss the anchor-arm bosses
                ys = (y0 - pw - C["finger_d"], y1 + pw + C["finger_d"])
                opening = [math.degrees(math.atan2(y, math.sqrt(max(R_out ** 2 - y ** 2, 0)))) for y in ys]
                mid, span = (opening[0] + opening[1]) / 2 + bank_ang, (opening[1] - opening[0]) / 2
                if any(angdiff(mid, b) < span + hw + 3 for b, hw in blocked):
                    fail(3, "the bank's opening would be behind an anchor arm")
                    continue
                # the PD trigger lies on the drum floor, screwed up through it, as near a finger window as it
                # fits: the bank's cable (a right-angle plug in the bank's face) comes back in through the window
                if trig_cache.get(id_boards) is None:
                    best_t = None
                    plug = TRIGGER_PLUG_L
                    win = [(fx0 + 4, s_ * (iw / 2 + pw + C["finger_d"] / 2) + yc) for s_ in (1, -1)]
                    tl = tr["l"] + plug
                    pts = [(x, y) for x in range(-int(R_in), int(R_in) + 1, 3) for y in range(-int(R_in), int(R_in) + 1, 3)
                           if math.hypot(x, y) <= R_in - wgap - tr["w"] / 2
                           and not overlap2d(Cyl("", x, y, tr["w"] / 2, 0, 1), pocket)
                           and min(math.hypot(x - wx, y - wy) for wx, wy in win) < 45]
                    for ang in range(0, 360, 15):
                        for x, y in pts:
                            if True:
                                pw_ = max(tr["w"], tr.get("plug_w", 0)) / 2      # the cable's plug, in front of the socket
                                t_ = place("PD trigger", (-tr["l"] / 2, tr["l"] / 2 + plug, -pw_, pw_, 0, tr["h"]),
                                           (x, y, DF, ang))
                                if t_.rmax() > R_in - wgap or any(collide(t_, o, gap) for o in obst):
                                    continue
                                sx, sy = x + (tr["l"] / 2 + plug) * math.cos(math.radians(ang)), y + (tr["l"] / 2 + plug) * math.sin(math.radians(ang))
                                d_ = min(math.hypot(sx - wx, sy - wy) for wx, wy in win)
                                if best_t is None or d_ < best_t[0]:
                                    best_t = (d_, t_, ang, x, y)
                    trig_cache[id_boards] = best_t or False
                bt = trig_cache[id_boards]
                if not bt:
                    fail(4, "no room on the drum floor for the PD trigger")
                    continue
                _, tplug, t_ang, tx, ty = bt
                t = place("PD trigger", (-tr["l"] / 2, tr["l"] / 2, -tr["w"] / 2, tr["w"] / 2, 0, tr["h"]), (tx, ty, DF, t_ang))
                obst_t = obst + [tplug]
                sw_cands = []
                for sa in sorted(range(0, 360, 5), key=lambda a: (angdiff(a, bank_ang), a)):
                    if not wall_ok(sa, half["switch"]):
                        continue
                    if any(angdiff(sa, c[0]) < 10 for c in sw_cands):
                        continue          # a spread of places to try, not neighbours
                    for zc in sw_zs:
                        # the locking ring on its boss, just inside the wall, then the narrower body and terminals
                        ring_in = sw_seat_r - sw_panel_t - sw["nut_t"] - 1
                        b = place("rocker switch ring", (ring_in, R_in + C["drum_wall"], -sw_r, sw_r, -sw_r, sw_r),
                                  (0, 0, zc, sa - bank_ang))
                        hb_ = sw["hole_d"] / 2 + 1
                        bb = place("rocker switch", (sw_seat_r - sw["depth"], ring_in + 0.01, -hb_, hb_, -hb_, hb_),
                                   (0, 0, zc, sa - bank_ang))
                        if any(collide(x_, o, gap) for o in obst_t for x_ in (b, bb)):
                            continue
                        sw_cands.append((sa, zc, b, bb))
                        break
                if not sw_cands:
                    if os.environ.get("DRUM_DEBUG"):
                        DEBUG.append((R_in, R_out, obst_t, t))
                    fail(5, "no room on the drum wall for the rocker switch")
                    continue
                for swb in sw_cands:
                    sa, sw_zc, swbox, swbody = swb
                    # fixing posts, an M3 insert in each top: merged into the drum wall, or into the
                    # pocket's walls from outside; three or four, spread round the axis
                    pr = C["drum_post_d"] / 2
                    interior = Box("bank", (x0 + BIG) / 2, yc, BIG - x0, iw, 0, 0, DH)
                    cands = [polar(post_r, a - bank_ang) for a in range(0, 360, 5)]
                    cands += [(x, s_ * (iw / 2 + pw + pr - 1) + yc) for s_ in (1, -1) for x in range(int(x0) - 2, int(fx0), 3)]
                    cands += [(x0 - pw - pr + 1, y) for y in range(int(y0) - 2, int(y1) + 3, 3)]
                    cands += [(x0 - pw / 2, y0 - pw / 2), (x0 - pw / 2, y1 + pw / 2)]
                    by_ang = {}
                    for x, y in cands:
                        c = Cyl("drum post", x, y, pr, 0, DH)
                        if c.rmax() > R_in + 1 + EPS or overlap2d(c, interior, 0.5):
                            continue
                        if any(overlap2d(c, o, 0.5) for o in [*fingers, *(b_ for b_, _ in boards.values()), tplug, swbox, swbody]):
                            continue
                        k = int(math.degrees(math.atan2(y, x)) % 360 // 10)
                        if k not in by_ang or math.hypot(x, y) > math.hypot(*by_ang[k]):
                            by_ang[k] = (x, y)
                    pts = list(by_ang.values())
                    best = None
                    for n in (4, 3):
                        for combo in itertools.combinations(pts, n):
                            angs = sorted(math.degrees(math.atan2(y, x)) % 360 for x, y in combo)
                            gaps = [angs[i + 1] - angs[i] for i in range(n - 1)] + [360 - angs[-1] + angs[0]]
                            if max(gaps) > (140 if n == 4 else 150):
                                continue
                            if min(math.hypot(x, y) for x, y in combo) < 35:
                                continue
                            if best is None or min(gaps) > best[0]:
                                best = (min(gaps), combo)
                        if best:
                            break
                    if not best:
                        fail(6, "nowhere to put the posts that screw the drum to the enclosure")
                        continue      # the next place for the switch
                    post_pts = [rot(p_, bank_ang) for p_ in best[1]]
                    post_angs = [round(math.degrees(math.atan2(y, x)) % 360, 1) for x, y in post_pts]
                    # vents round the buck, half way up the wall
                    buck_box, _ = boards["buck"]
                    buck_ang = math.degrees(math.atan2(buck_box.cy, buck_box.cx)) + bank_ang
                    vents = []
                    for a in range(0, 360, 10):
                        if angdiff(a, buck_ang) > 50:
                            continue
                        v = place("vent", (R_in - 1, R_out + 1, -C["vent_w"] / 2 - 2, C["vent_w"] / 2 + 2, 0, DH), (0, 0, 0, a - bank_ang))
                        if any(overlap2d(v, o) for o in [pocket, *fingers, tplug, swbox, swbody]):
                            continue
                        if any(overlap2d(v, Cyl("", *rot(p_, -bank_ang), pr, 0, 1), 1) for p_ in post_pts):
                            continue
                        if not wall_ok(a, C["vent_w"] / 2):
                            continue
                        if angdiff(a, sa) < math.degrees((half["switch"] + C["vent_w"] / 2 + 3) / R_out):
                            continue
                        vents.append(a % 360)

                    def world(b):
                        cx, cy = rot((b.cx, b.cy), bank_ang)
                        return Box(b.name, cx, cy, b.l, b.w, (b.ang + bank_ang) % 360, b.z0 - DH, b.z1 - DH)

                    # the plate under the bank: two M3 screws up through the drum floor into inserts in it
                    plate_screws = []
                    for x in (x0 + 14, x1 - C["finger_l"] - 4):
                        if math.hypot(x, yc) < 16:
                            x += 16 if x > 0 else -16
                        plate_screws.append([round(x, 3), round(yc, 3)])
                    mounts, edge = {}, {}
                    for key, _ in EDGE_BOARDS:
                        b, side = boards[key]
                        # each screw goes from the pocket face of the wall out into the standoff: point on that face, axis angle
                        axis = (b.ang + (90 if side > 0 else -90)) % 360
                        hs = []
                        for hx, hy, z in edge_holes(P[key], b, side):
                            x, y = rot((hx, hy), b.ang)
                            ax, ay = polar(pw, axis)
                            hs.append((b.cx + x - ax, b.cy + y - ay, z))
                        edge[key] = {"wall": walls[key], "holes_local": [[round(x, 3), round(y, 3), round(z, 3), axis] for x, y, z in hs]}
                        mounts[key] = {"on": "wall",
                                       "holes": [[round(v, 3) for v in (*rot((x, y), bank_ang), z - DH)] for x, y, z in hs],
                                       **screw_for(P[key], pw)}
                    tw = world(t)
                    mounts["pd_trigger"] = {"on": "drum", "holes": [[round(x, 3), round(y, 3)] for x, y in
                                                                   ((tw.cx + hx, tw.cy + hy) for hx, hy in (rot(h, tw.ang) for h in local_holes(tr)))],
                                            **screw_for(tr, DF)}
                    rx, ry = rot((-tr["l"] / 2 + 4, 0), tw.ang)
                    wire = (buck_box.cx, buck_box.cy)
                    return {
                        "h": DH, "R_in": R_in, "R_out": R_out, "floor": DF, "wall": C["drum_wall"], "ang": bank_ang,
                        "x0": round(x0, 3), "x1": round(x1, 3), "y0": round(y0, 3), "y1": round(y1, 3),
                        "il": il, "iw": iw, "pw": pw, "plate_t": G["plate_t"], "bank_z": G["bank_z"],
                        "plate_screws": plate_screws, "edge": edge, "mounts": mounts,
                        "rests": [[round(tw.cx + rx, 3), round(tw.cy + ry, 3), tw.ang, 6, max(4, tr["w"] - 4), tr["standoff_h"]]],
                        "switch": {"ang": sa, "z": sw_zc, "r": sw_r, "hole_d": sw["hole_d"] + 0.5,
                                   "flat_d": sw["hole_d_minus_flat"] + 0.5, "flat_rot": FLAT_ROT.get(sw["flat_side"], 0),
                                   "flange_d": sw["flange_d"], "boss_d": sw["nut_d"] + 4,
                                   "seat_r": round(sw_seat_r, 3), "panel_t": sw_panel_t},
                        "post_d": C["drum_post_d"], "post_angs": post_angs,
                        "screws": [[round(x, 3), round(y, 3)] for x, y in post_pts],
                        "screw_l": next(s for s in SCREW_LENGTHS if s >= C["base_wall"] + C["drum_insert_h"] - 1),
                        "vents": vents, "vent_z": round(DH / 2, 2),
                        "wire_hole": [round(v, 3) for v in rot(wire, bank_ang)] + [C["wire_hole_d"]],
                        "boxes": {"buck": world(boards["buck"][0]), "latch": world(boards["latch"][0]),
                                  "trigger": tw, "switch": world(swbox), "switch_body": world(swbody)},
                        "edge_up": {k: boards[k][1] for k, _ in EDGE_BOARDS},
                    }
    raise NoFit(f"the power drum (Ø{base_d:g}): {why[max(why)] if why else 'no arrangement found'}")


def ptz_bolts(ptz):
    """The Arducam base's standoffs from its two spacings: (corner-to-corner spacing, angles).

    They make a rectangle lined up with the lens: 0° is straight ahead at mid-pan,
    horizontal is side to side, vertical front to back."""
    h, v = ptz["horizontal_bolt_spacing"], ptz["vertical_bolt_spacing"]
    a = math.degrees(math.atan2(h, v))
    return round(math.hypot(h, v), 2), [round(x % 360, 2) for x in (a, 180 - a, 180 + a, -a)]


def angdiff(a, b):
    return abs((a - b + 180) % 360 - 180)


# ======================================================================
#  bought-part envelopes
# ======================================================================

def pi_local(p, ext=None):
    """The Pi as a set of boxes, centre-origin, z = 0 at the underside of the board.
    With UWB, `ext` adds the anchors' USB plugs sticking out of its USB ports."""
    L, W, T = p["l"], p["w"], p["pcb_t"]
    hl, hw = L / 2, W / 2
    extra = []
    if ext:
        x0 = hl + p["port_overhang"]
        extra = [("Pi USB plugs (anchors)", (x0, x0 + ext["male_l"], -hw + 1, 4, T, T + p["port_h"]))]
    return [
        ("Pi board", (-hl, hl, -hw, hw, 0, T)),
        ("Pi underside", (-hl, hl, -hw, hw, -p["under_h"], 0)),
        ("Pi heatsinks", (-hl, hl, -hw, hw, T, T + p["heatsink_h"])),
        ("Pi USB/Ethernet", (hl - p["port_block_l"], hl + p["port_overhang"], -hw + 1, hw - 1, T, T + p["port_h"])),
        ("Pi GPIO leads", (p["gpio_x0"] - hl, p["gpio_x1"] - hl, hw - p["gpio_w"], hw, T, T + p["gpio_lead_h"])),
        ("Pi USB-C plug", (p["usbc_x"] - hl - p["plug_w"] / 2, p["usbc_x"] - hl + p["plug_w"] / 2,
                           -hw - p["plug_l"], -hw, 0, T + p["plug_h"])),
    ] + extra


def pi_holes_local(p):
    return [(x - p["l"] / 2, y - p["w"] / 2) for x, y in p["holes"]]


def rot(pt, deg):
    a = math.radians(deg)
    return pt[0] * math.cos(a) - pt[1] * math.sin(a), pt[0] * math.sin(a) + pt[1] * math.cos(a)


# ======================================================================
#  the solver
# ======================================================================

def max_base_d(build, C):
    """Widest enclosure the A1 Mini can print: the with-UWB wall bosses add
    8 mm across Y; the diffuser band adds its own thickness."""
    lim = PRINT_LIMIT - 2 * (C["clr"] + C["diffuser_t"])
    if build == "with_uwb":
        lim = min(lim, PRINT_LIMIT - 8)
    return math.floor(lim / 2) * 2


def solve(build, P, C):
    attempts = []
    d = C["base_d_min"]
    while d <= max_base_d(build, C) + EPS:
        try:
            L = solve_at(build, P, C, d)
            L["attempts"] = attempts
            return L
        except NoFit as e:
            attempts.append(f"Ø{d:g}: {e}")
        d += 2
    raise NoFit("no layout fits up to the widest enclosure the A1 Mini can print "
                f"(Ø{max_base_d(build, C)}):\n    " + "\n    ".join(attempts[-4:]))


def solve_at(build, P, C, base_d):
    uwb = build == "with_uwb"
    R_out = base_d / 2
    R_in = R_out - C["base_wall"]
    FZ = C["base_wall"]
    gap, wgap = C["part_gap"], C["wall_gap"]
    r_shelf = R_in - C["clr"] - 0.5
    pi = P["pi"]

    # ---- the power drum underneath --------------------------------------
    D = solve_drum(build, P, C, base_d)
    # its four posts' screws come down through the floor from inside, so each keeps a
    # screwdriver's way clear; the leads from the drum come up through the wire hole
    cols = [Cyl("drum screw", x, y, 4.0, FZ, 999) for x, y in D["screws"]]
    wh = D["wire_hole"]
    wire = Cyl("wire hole", wh[0], wh[1], wh[2] / 2 + 1, FZ, 999)

    # ---- Pi poses on the shelf, best (lowest ceiling) first --------------
    pi_local_boxes = pi_local(pi, P["usb_extension"] if uwb else None)
    holes_l = pi_holes_local(pi)
    poses = []
    for ang in range(0, 360, 15):
        for x in range(-24, 25, 3):
            for y in range(-24, 25, 3):
                boxes = [place(n, lb, (x, y, 0, ang)) for n, lb in pi_local_boxes]
                ok = all(b.rmax() <= (R_in - 1 if "plug" in b.name else r_shelf) for b in boxes)
                if uwb and ok:
                    # the anchor cables come in through a slot in the wall behind the USB end
                    ub = boxes[-1]
                    ok = ub.rmax() <= R_in - 1
                if not ok:
                    continue
                # cable gap: the shelf is cut away beyond the Pi's power edge
                u = rot((0, -1), ang)
                pcb = boxes[0]
                gap_d = max(px * u[0] + py * u[1] for px, py in pcb.corners()) + 1.5
                if r_shelf - gap_d < 8:
                    continue          # the plug and pigtail need somewhere to drop through
                poses.append((x, y, ang, gap_d, math.degrees(math.atan2(u[1], u[0])) % 360, boxes))
    if not poses:
        raise NoFit(f"the Pi ({pi['l']}×{pi['w']} plus its plug) doesn't fit on a Ø{2 * r_shelf:.0f} shelf")

    # The Arducam base stands on its four standoffs on the lid; M3 screws come up
    # through radial slots into them. Short screws: counterbore the lid underneath.
    ptz = P["ptz"]
    # the pan servo must clear the lid: if the standoffs are too short, stack M3 washers under them
    short = ptz["servo_drop"] + SERVO_CLEAR - ptz["standoff_h"]
    washers = max(0, math.ceil(round(short / PTZ_WASHER_T, 6)))
    if washers > PTZ_WASHERS_MAX:
        washers = 0           # more than a few washers is the wrong fix — the audit says so
    lift = washers * PTZ_WASHER_T
    grip = ptz["bolt_l"] - C["lid_t"] - lift
    screw_recess = 0.0 if grip >= PTZ_ENGAGE else PTZ_ENGAGE - grip
    below_lid = max(ptz["head_h"] - screw_recess, 0.0)
    diag, bolt_angs = ptz_bolts(ptz)
    r_bolt = diag / 2
    # the lid's slots cover the configured range, stretched to your base if needed
    slot_min = min(C["ptz_bolt_min"], diag - 6)
    slot_max = max(C["ptz_bolt_max"], diag + 6)
    head_r = ptz["head_d"] / 2 + 0.5
    spig_in = R_in - C["clr"] - C["spigot_w"]
    if slot_max / 2 + head_r + 1 > spig_in - 1:
        raise NoFit(f"the Arducam base's standoffs ({diag:g} mm apart corner to corner) land on the lid's locating ring")
    lid_screw_angs = [45, 135, 225, 315]
    # Cable slot: the ribbon and leads come off the camera head, over the turntable,
    # and in through the lid at the back — as near straight behind the lens (180°)
    # as the bolt slots and the lid-screw pads allow.
    cs_w = ptz["ribbon_w"] + ptz["lead_bundle_d"] + 4
    cs_d = max(ptz["lead_bundle_d"], 6) + 1
    cs_r = spig_in - 1.5 - cs_d / 2
    if cs_r - cs_d / 2 < 20:
        raise NoFit("no room in the lid for the camera cable slot")
    radial_clear = slot_max / 2 + C["ptz_slot_w"] / 2 + 2 <= cs_r - cs_d / 2
    need_bolt = 0.0 if radial_clear else math.degrees((cs_w / 2 + head_r + 2) / cs_r)
    need_pad = math.degrees((cs_w / 2 + 5 + 2) / cs_r)
    cs_ang = next((a % 360 for d in (0, 7.5, 15, 22.5, 30, 37.5, 45) for a in (180 - d, 180 + d)
                   if all(angdiff(a, b) >= need_bolt for b in bolt_angs)
                   and all(angdiff(a, p) >= need_pad for p in lid_screw_angs)), None)
    if cs_ang is None:
        raise NoFit("no place at the back of the lid for the camera cable slot between the bolt slots and the lid screws")

    def ceiling_need(objs, base_h_guess=0.0):
        """How far above each object the lid underside must be (relative)."""
        need = 0.0
        spig_r = R_in - C["clr"] - C["spigot_w"] - 0.5
        pads = [place("pad", (R_in - C["clr"] - C["lid_screw_pad"] - 0.5, R_in, -5.5, 5.5, 0, 1), (0, 0, 0, a))
                for a in lid_screw_angs]
        nuts = [Cyl("screw head", *polar(r_bolt, a), head_r, 0, 1) for a in bolt_angs]
        slack = Cyl("slack", *polar(cs_r, cs_ang), cs_w / 2 + 4, 0, 1)
        for o in objs:
            n = o.z1 + 1
            if o.rmax() > spig_r or any(overlap2d(o, p) for p in pads):
                n = max(n, o.z1 + C["spigot_h"] + 1)
            if any(overlap2d(o, q) for q in nuts):
                n = max(n, o.z1 + below_lid + 1)
            if overlap2d(o, slack):
                n = max(n, o.z1 + C["ribbon_slack_h"])
            need = max(need, n)
        return need

    poses.sort(key=lambda p: (round(ceiling_need(p[5]), 1), r_shelf - p[3] < 20, abs(p[0]) + abs(p[1])))

    post_r = R_in - C["post_d"] / 2 + 1
    last_err = "no arrangement found"
    sh = P["shifter"]

    for pose_i, (px, py, pang, gap_d, gap_ang, pi_boxes) in enumerate(poses[:40]):
        u = (math.cos(math.radians(gap_ang)), math.sin(math.radians(gap_ang)))
        holes_w = [(px + hx, py + hy) for hx, hy in (rot(h, pang) for h in holes_l)]

        # ---- shelf posts -------------------------------------------
        post_ok = []
        for a in range(0, 360, 5):
            cx, cy = polar(post_r, a)
            if cx * u[0] + cy * u[1] > gap_d - 5:
                continue
            post = Cyl("post", cx, cy, C["post_d"] / 2, FZ, 999)
            if any(overlap2d(post, w, gap) for w in cols + [wire]):
                continue
            if any(math.hypot(cx - hx, cy - hy) < 3.2 + 3 + 1 for hx, hy in holes_w):
                continue
            post_ok.append(a)
        best = None
        for tri in itertools.combinations(post_ok, 3):
            gaps = sorted([(tri[1] - tri[0]), (tri[2] - tri[1]), (360 - tri[2] + tri[0])])
            if gaps[-1] >= 165:
                continue
            score = gaps[0]
            if best is None or score > best[0]:
                best = (score, tri)
        if not best or best[0] < 50:
            last_err = "nowhere to put three shelf posts clear of the cable gap and the drum's screws"
            continue
        post_angs = list(best[1])
        posts = [Cyl(f"shelf post {i + 1}", *polar(post_r, a), C["post_d"] / 2, FZ, 999) for i, a in enumerate(post_angs)]
        obstacles = [*cols, wire, *posts]

        # ---- shifter: on the shelf beside the Pi, else on the floor --
        shifter = None
        standoffs = [Cyl("Pi standoff", hx, hy, 3, 0, 1) for hx, hy in holes_w]
        heads = [Cyl("post screw head", *polar(post_r, a), 3.2, 0, 1) for a in post_angs]
        flat = [Box(o.name, o.cx, o.cy, o.l, o.w, o.ang, 0, 1) for o in pi_boxes]
        for ang in range(0, 180, 15):
            for x in range(-60, 61, 2):
                for y in range(-60, 61, 2):
                    b = place("level shifter", (-sh["l"] / 2, sh["l"] / 2, -sh["w"] / 2, sh["w"] / 2, 0, sh["h"]),
                              (x, y, 0, ang))
                    if b.rmax() > r_shelf - 1:
                        continue
                    if max(cx * u[0] + cy * u[1] for cx, cy in b.corners()) > gap_d - 1:
                        continue
                    if any(overlap2d(b, o, gap) for o in flat + standoffs + heads):
                        continue
                    shifter = ("shelf", b)
                    break
                if shifter:
                    break
            if shifter:
                break
        if not shifter:
            for ang in range(0, 180, 15):
                for x in range(-int(R_in), int(R_in) + 1, 2):
                    for y in range(-int(R_in), int(R_in) + 1, 2):
                        b = place("level shifter", (-sh["l"] / 2, sh["l"] / 2, -sh["w"] / 2, sh["w"] / 2, 0, sh["h"]),
                                  (x, y, FZ, ang))
                        if b.rmax() <= R_in - wgap and not any(collide(b, o, gap) for o in obstacles):
                            shifter = ("deck", b)
                            break
                    if shifter:
                        break
                if shifter:
                    break
        if not shifter:
            last_err = "no room for the level shifter"
            continue

        # ---- heights -----------------------------------------------
        # nothing stands on the floor now but the shifter, if the shelf had no room for it
        power_top = shifter[1].z1 if shifter[0] == "deck" else FZ
        win_h, lip = C["led_window_h"], C["diffuser_lip"]
        ledge_h = C["ledge_h"]
        # the diffuser band's ledge, under the window, has to stay above the floor's underside
        window_z = max(power_top + 1, FZ + 1 + ledge_h + C["diffuser_t"] + lip)
        shelf_z = window_z + win_h
        ring = P["led_ring"]
        ring_z1 = shelf_z - C["tape_t"]
        ring_z0 = ring_z1 - ring["h"]
        if ring_z0 < window_z:
            raise NoFit("the LED ring is taller than the LED window")
        shelf_top = shelf_z + C["shelf_t"]
        if pi["standoff_h"] < pi["under_h"] + 0.5:
            raise NoFit("the Pi's standoffs are shorter than the parts under the board")
        pi_z = shelf_top + pi["standoff_h"]
        pi_world = [Box(b.name, b.cx, b.cy, b.l, b.w, b.ang, b.z0 + pi_z, b.z1 + pi_z) for b in pi_boxes]
        shelf_objs = list(pi_world)
        if shifter[0] == "shelf":
            b = shifter[1]
            shifter = ("shelf", Box(b.name, b.cx, b.cy, b.l, b.w, b.ang, shelf_top, shelf_top + sh["h"]))
            shelf_objs.append(shifter[1])
        base_h = max(C["base_h_min"], ceiling_need(shelf_objs),
                     shelf_top + C["vent_h"] + 4 + C["spigot_h"])
        base_h = math.ceil(base_h)

        # ---- vents and diffuser ------------------------------------
        high_vz = (shelf_top + base_h - C["spigot_h"]) / 2
        vent_half = math.degrees((C["vent_w"] / 2 + 3) / R_out)
        vents_high = [a for a in range(5, 360, 20)
                      if all(angdiff(a, s) >= math.degrees(8 / R_out) + vent_half for s in lid_screw_angs)]
        # window ribs: no unsupported span longer than window_bridge
        n_ribs = math.ceil(2 * math.pi * R_out / (C["window_bridge"] + C["window_rib_w"]))
        window_ribs = [round(post_angs[0] + 360 * i / n_ribs, 2) % 360 for i in range(n_ribs)]

        # ---- UWB anchors and wearable ------------------------------
        extra = {}
        if uwb:
            extra = solve_uwb(P, C, base_d, D["h"])
            ub = pi_world[-1]
            ext = P["usb_extension"]
            ent_ang = round(math.degrees(math.atan2(ub.cy, ub.cx)) % 360)
            ent_h = ext["male_h"] + 2
            ent_z = base_h - C["spigot_h"] - 2 - ent_h / 2
            if ent_z - ent_h / 2 < shelf_top + 2:
                raise NoFit("no wall height above the shelf for the anchor-cable slot")
            ent_w = ext["male_w"] + 2
            extra["usb_entry"] = {"ang": ent_ang, "z": ent_z, "w": ent_w, "h": ent_h}
            ent_half = math.degrees((ent_w / 2 + 3) / R_out)
            vents_high = [a for a in vents_high if angdiff(a, ent_ang) >= ent_half + vent_half]

        mounts = dict(D["mounts"])
        on_shelf = shifter[0] == "shelf"
        through = C["shelf_t"] if on_shelf else FZ
        b = shifter[1]
        mounts["shifter"] = {"on": "shelf" if on_shelf else "floor",
                             "holes": [[round(b.cx + x, 3), round(b.cy + y, 3)] for x, y in (rot(h, b.ang) for h in local_holes(sh))],
                             **screw_for(sh, through)}
        boxes = {k: box_d(v) for k, v in D["boxes"].items()}
        for k in ("buck", "latch"):
            boxes[k]["edge"] = D["edge_up"][k]       # standing on edge: its components face the box's +y (1) or -y (-1)
        boxes["shifter"] = box_d(shifter[1])
        drum = {k: v for k, v in D.items() if k not in ("boxes", "mounts", "edge_up")}
        L = {
            "build": build, "base_d": base_d, "base_h": base_h, "R_in": R_in, "floor_z": FZ, "lid_t": C["lid_t"],
            "mounts": mounts, "drum": drum,
            "ptz_slot_min": slot_min, "ptz_slot_max": slot_max,
            "power_top": power_top,
            "window_z": window_z, "shelf_z": shelf_z, "shelf_top": shelf_top, "shelf_r": r_shelf,
            "gap_ang": gap_ang, "gap_d": gap_d,
            "post_r": post_r, "post_angs": post_angs, "window_ribs": window_ribs,
            "ring_z0": ring_z0, "ring_z1": ring_z1,
            "pi": {"x": px, "y": py, "z": pi_z, "ang": pang}, "pi_holes": holes_w,
            "vents_high": vents_high, "vent_high_z": high_vz,
            "lid_screw_angs": lid_screw_angs, "lid_screw_z": base_h - C["spigot_h"] / 2,
            "screw_recess": screw_recess, "below_lid": below_lid,
            "bolt_angs": bolt_angs, "ptz_washers": washers, "ptz_lift": lift,
            "cable_slot": {"ang": cs_ang, "r": cs_r, "w": cs_w, "d": cs_d},
            "shifter_on": shifter[0],
            "boxes": boxes,
            "pi_boxes": [box_d(b) for b in pi_world],
            "pose_rank": pose_i,
            **extra,
        }
        return L
    raise NoFit(last_err)


def box_d(b):
    return {"name": b.name, "cx": round(b.cx, 3), "cy": round(b.cy, 3), "l": b.l, "w": b.w,
            "ang": b.ang, "z0": round(b.z0, 3), "z1": round(b.z1, 3)}


def box_from(d):
    return Box(d["name"], d["cx"], d["cy"], d["l"], d["w"], d["ang"], d["z0"], d["z1"])


def solve_uwb(P, C, base_d, drum_h):
    """Anchor-board orientation, the mast geometry and the wearable pod. The arms and the
    mast foot bolt to bosses on the power drum's wall, whose bottom is drum_h below the
    enclosure floor."""
    u, ext = P["ula1"], P["usb_extension"]
    arm_boss_r = base_d / 2 + 4
    bracket_face = arm_boss_r + 6
    # Radial: USB plug pointing at the enclosure. The extension's rigid
    # female end has to fit between the plug and the arm's root bracket.
    tip = C["uwb_half_base"] - u["l"] / 2 - u["plug_overhang"]
    radial_room = tip - bracket_face
    tangential = radial_room < ext["female_l"] + 3
    ant_x = (u["l"] / 2 - u["antenna_from_end"]) if tangential else 0.0
    ant_r_extra = 0.0 if tangential else (u["l"] / 2 - u["antenna_from_end"])
    mast_bore = P["dowel"]["d"] + 2 * C["clr"]
    mast_sock_r = mast_bore / 2 + C["mast_wall"]
    mast_axis_r = arm_boss_r + 6 + mast_sock_r - 2
    cradle_rise = C["mast_floor"] + C["arm_t"] + 4
    dowel_l = C["anchor_board_z"] + C["uwb_v_base"] - cradle_rise - (C["arm_boss_z"] + C["mast_floor"])
    tb = P["tag_bank"]
    inline_l = tb["l"] + u["l"] + 3
    pod = {"layout": "inline", "inner_l": inline_l, "inner_w": max(tb["w"], u["w"]) + 2,
           "inner_h": max(tb["h"], u["h"] + 3) + 2, "ula1_x0": tb["l"] + 3,
           "charge_slot": bool(tb.get("input_on_far_end", True))}
    return {
        "ula1_tangential": tangential, "ula1_radial_room": radial_room,
        "antenna_x": ant_x, "baseline": 2 * (C["uwb_half_base"] + ant_r_extra),
        "arm_boss_r": arm_boss_r, "mast_axis_r": mast_axis_r, "mast_bore": mast_bore,
        "dowel_l": dowel_l, "pod": pod,
        # A3 is placed relative to the A1–A2 midpoint. Turning the boards
        # shifts all three antennas the same way along X, so it cancels.
        "a3_back": mast_axis_r, "a3_up": C["uwb_v_base"],
        "anchor_z": C["anchor_board_z"] - drum_h, "lid_t": C["lid_t"],      # A1/A2 boards, from the enclosure floor
    }


# ======================================================================
#  generated files
# ======================================================================

def fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return f"{v:.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(fmt(x) for x in v) + "]"
    raise TypeError(v)


def gen_scad(build, P, C, L) -> str:
    Dr = L["drum"]
    v = {
        "base_d": L["base_d"], "base_h": L["base_h"],
        "window_z": L["window_z"], "shelf_z": L["shelf_z"], "shelf_r": L["shelf_r"],
        "gap_ang": L["gap_ang"], "gap_d": L["gap_d"],
        "post_r": L["post_r"], "post_angs": L["post_angs"], "window_ribs": L["window_ribs"],
        "pi_holes": [list(h) for h in L["pi_holes"]], "pi_hole_d": P["pi"]["hole_d"] + 0.2,
        "vents_low": [], "vent_low_z": 0,
        "vents_high": L["vents_high"], "vent_high_z": L["vent_high_z"],
        "lid_screw_angs": L["lid_screw_angs"], "lid_screw_z": L["lid_screw_z"],
        "lid_screw_recess": L["screw_recess"], "ptz_head_d": P["ptz"]["head_d"],
        "ptz_slot_min": L["ptz_slot_min"], "ptz_slot_max": L["ptz_slot_max"], "ptz_bolt_angs": L["bolt_angs"],
        "cable_slot_ang": L["cable_slot"]["ang"], "cable_slot_r": L["cable_slot"]["r"],
        "cable_slot_w": L["cable_slot"]["w"], "cable_slot_d": L["cable_slot"]["d"],
        # [x, y, hole Ø, countersink Ø, depth through]: screws up into each board's standoffs
        "floor_holes": [[x, y, m["hole_d"], m["head_d"], m["through"]]
                        for m in L["mounts"].values() if m["on"] == "floor" for x, y in m["holes"]],
        "shelf_holes": [[x, y, m["hole_d"], m["head_d"]]
                        for m in L["mounts"].values() if m["on"] == "shelf" for x, y in m["holes"]],
        "rests": [],
        # the power drum: drawn in the enclosure's x, y, its bottom at z = 0; the pocket in its own frame
        "drum_h": Dr["h"], "drum_ang": Dr["ang"], "drum_screws": Dr["screws"], "drum_screw_l": Dr["screw_l"],
        "wire_hole": Dr["wire_hole"],
        "pocket_x0": Dr["x0"], "pocket_x1": Dr["x1"], "pocket_y0": Dr["y0"], "pocket_y1": Dr["y1"],
        "plate_t": Dr["plate_t"], "plate_screws": Dr["plate_screws"],
        # the boards' screws through the pocket walls: from a point on the wall's pocket face, out along axis°
        "wall_holes": [h for k in ("buck", "latch") for h in Dr["edge"][k]["holes_local"]],     # [x, y, z, axis°], pocket frame
        "wall_hole_d": 3.4,
        "drum_floor_holes": [[x, y, m["hole_d"], m["head_d"], m["through"]]
                             for m in L["mounts"].values() if m["on"] == "drum" for x, y in m["holes"]],
        "drum_rests": Dr["rests"],
        "switch_ang": Dr["switch"]["ang"], "switch_z": Dr["switch"]["z"],
        "switch_hole_d": Dr["switch"]["hole_d"], "switch_flange_d": Dr["switch"]["flange_d"],
        "switch_boss_d": Dr["switch"]["boss_d"], "switch_seat_r": Dr["switch"]["seat_r"],
        "switch_panel_t": Dr["switch"]["panel_t"],
        "switch_flat_d": Dr["switch"]["flat_d"], "switch_flat_rot": Dr["switch"]["flat_rot"],
        "drum_vents": Dr["vents"], "drum_vent_z": Dr["vent_z"],
        "drum_arms": build == "with_uwb",
        "nut_af": P["tripod_nut"]["af"], "nut_t": P["tripod_nut"]["t"],
        "bank_l": P["power_bank"]["l"], "bank_w": P["power_bank"]["w"], "bank_h": P["power_bank"]["h"],
    }
    if build == "with_uwb":
        u = P["ula1"]
        v.update({
            "uwb_l": u["l"], "uwb_w": u["w"], "uwb_hole_dx": u["hole_dx"], "uwb_hole_dy": u["hole_dy"],
            "ula1_tangential": L["ula1_tangential"], "mast_d": P["dowel"]["d"],
            "pod_inner_l": L["pod"]["inner_l"], "pod_inner_w": L["pod"]["inner_w"], "pod_inner_h": L["pod"]["inner_h"],
            "pod_ula1_x0": L["pod"]["ula1_x0"], "pod_charge_slot": L["pod"]["charge_slot"],
            "usb_entry_ang": L["usb_entry"]["ang"], "usb_entry_z": L["usb_entry"]["z"],
            "usb_entry_w": L["usb_entry"]["w"], "usb_entry_h": L["usb_entry"]["h"],
        })
    out = ["// GENERATED by cad/fit.py from cad/ordered_parts.toml and config.scad.",
           "// Do not edit: change those and run  python3 cad/fit.py  (from sport_cam/).", ""]
    out += [f"{k} = {fmt(x)};" for k, x in v.items()]
    return "\n".join(out) + "\n"


def gen_json(build, P, C, L) -> dict:
    keep = {k: v for k, v in L.items() if k != "attempts"}
    keep["design"] = {k: C[k] for k in ("base_wall", "lid_t", "spigot_h", "shelf_t", "led_window_h",
                                        "diffuser_t", "diffuser_lip", "tape_t", "clr") if k in C}
    keep["parts"] = {k: {kk: vv for kk, vv in v.items() if kk not in ("name",)} for k, v in P.items()}
    if build == "with_uwb":
        keep["uwb"] = {k: C[k] for k in ("uwb_half_base", "anchor_board_z", "uwb_v_base", "arm_boss_z", "mast_floor")}
    # the power drum hangs under the floor: its bottom (the tripod plate) is at -h
    keep["drum_z"] = -L["drum"]["h"]
    keep["nut_seat"] = -L["drum"]["h"] + C["drum_floor"]                # the tripod nut sits on the drum floor
    keep["lid_z"] = L["base_h"]
    keep["lid_top"] = L["base_h"] + C["lid_t"]
    # Arducam base: on its standoffs on the lid; the tilt axis is above the bottom disc
    keep["ptz_washers"] = L["ptz_washers"]
    keep["ptz_z"] = keep["lid_top"] + L["ptz_lift"] + P["ptz"]["standoff_h"]
    keep["tilt_z"] = keep["ptz_z"] + P["ptz"]["tilt_axis_h"]
    return keep


def write_if_changed(path, text):
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old != text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    return False


def generated(build, P, C, L) -> dict:
    data = gen_json(build, P, C, L)
    js = json.dumps(data, indent=1, sort_keys=True)
    return {
        os.path.join(ROOT, build, "cad", "layout.scad"): gen_scad(build, P, C, L),
        os.path.join(ROOT, build, "cad", "layout.json"): js + "\n",
        os.path.join(ROOT, "docs", build, "setup", "assembly", "layout.js"):
            "// GENERATED by cad/fit.py — the solved layout for the 3D guide. Do not edit.\n"
            f"window.SPORTCAM_LAYOUT = {js};\n",
    }


# device constants that follow from the geometry
def device_updates(build, P, L) -> dict:
    out = {"LED_COUNT": str(P["led_ring"]["count"])}
    if build == "with_uwb":
        out.update({
            "UWB_BASELINE_M": f"{L['baseline'] / 1000:.3f}".rstrip("0").rstrip("."),
            "UWB_A3_BACK_M": f"{L['a3_back'] / 1000:.3f}".rstrip("0").rstrip("."),
            "UWB_A3_UP_M": f"{L['a3_up'] / 1000:.3f}",
            # tilt axis above the A1/A2 boards: lid top + the base's standoffs + its tilt-axis height
            "LENS_ABOVE_ANCHORS_M": f"{(L['base_h'] + L['lid_t'] + L['ptz_lift'] + P['ptz']['standoff_h'] + P['ptz']['tilt_axis_h'] - L['anchor_z']) / 1000:.3f}",
        })
    return out


def device_config_text(build, P, L):
    path = os.path.join(ROOT, "src", build, "device", "sportcam", "config.py")
    text = open(path, encoding="utf-8").read()
    new = text
    for k, v in device_updates(build, P, L).items():
        # rewrite only a value that actually differs, keeping the line's layout
        new = re.sub(rf"^({k}\s*=\s*)([0-9.]+)",
                     lambda m: m.group(0) if abs(float(m.group(2)) - float(v)) < 1e-9 else m.group(1) + v,
                     new, count=1, flags=re.M)
    return path, text, new


# ======================================================================
#  STL checks
# ======================================================================

def stl_vertices(path):
    data = open(path, "rb").read()
    if data[:5] == b"solid" and b"facet" in data[:400]:
        return [tuple(float(x) for x in m.groups())
                for m in re.finditer(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", data)]
    import struct
    (n,) = struct.unpack("<I", data[80:84])
    out = []
    for i in range(n):
        off = 84 + i * 50 + 12
        for k in range(3):
            out.append(struct.unpack("<3f", data[off + 12 * k: off + 12 * k + 12]))
    return out


def stl_info(path):
    v = stl_vertices(path)
    size = [max(p[i] for p in v) - min(p[i] for p in v) for i in range(3)]
    idx, par, ids = {}, [], []

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for t in v:
        key = (round(t[0], 4), round(t[1], 4), round(t[2], 4))
        if key not in idx:
            idx[key] = len(par)
            par.append(len(par))
        ids.append(idx[key])
    for i in range(0, len(ids), 3):
        a = find(ids[i])
        par[find(ids[i + 1])] = a
        par[find(ids[i + 2])] = a
    bodies = len({find(i) for i in range(len(par))})
    return size, bodies


def inputs_hash(build):
    h = hashlib.sha256()
    with open(PARTS_FILE, "rb") as f:           # the values, not the text: MEASURE_TODO → MEASURE_DONE re-renders nothing
        h.update(json.dumps(tomllib.load(f), sort_keys=True).encode())
    cad = os.path.join(ROOT, build, "cad")
    for f in sorted(os.listdir(cad)):
        if f.endswith(".scad") or f == "render_all.sh":
            h.update(f.encode())
            h.update(open(os.path.join(cad, f), "rb").read())
    return h.hexdigest()


STAMP = ".fit-inputs"


# ======================================================================
#  the audit
# ======================================================================

class Audit:
    def __init__(self, build):
        self.build = build
        self.rows = []

    def check(self, ok, title, detail="", parts=()):
        self.rows.append(("PASS" if ok else "FAIL", title, detail, tuple(parts)))
        return ok

    def note(self, title, detail=""):
        self.rows.append(("NOTE", title, detail, ()))

    @property
    def failed(self):
        return [r for r in self.rows if r[0] == "FAIL"]


def drum_scene(P, C, L):
    """The power drum's bought parts and printed features, in the enclosure's frame (its bottom at -h)."""
    D = L["drum"]
    H, ang, DF, pw = D["h"], D["ang"], D["floor"], D["pw"]
    x0, x1, y0, y1 = D["x0"], D["x1"], D["y0"], D["y1"]
    yc = (y0 + y1) / 2
    xo = D["R_out"]

    def w(name, cx, cy, l, wd, a, z0, z1):            # a box in the pocket's frame → the enclosure's
        X, Y = rot((cx, cy), ang)
        return Box(name, X, Y, l, wd, (a + ang) % 360, z0 - H, z1 - H)
    bk = P["power_bank"]
    objs = [box_from(L["boxes"][k]) for k in ("buck", "latch", "trigger", "switch", "switch_body")]
    objs.append(w("power bank", (x0 + x1) / 2, yc, bk["l"], bk["w"], 0, D["bank_z"], D["bank_z"] + bk["h"]))
    t_ = pw - 0.1           # the boards stand flush against the walls: keep rounding from reading as a clash
    printed = [w("pocket wall +y", (x0 - pw + xo) / 2, y1 + pw / 2, xo - x0 + pw, t_, 0, 0, H),
               w("pocket wall -y", (x0 - pw + xo) / 2, y0 - pw / 2, xo - x0 + pw, t_, 0, 0, H),
               w("pocket closed end", x0 - pw / 2, yc, t_, y1 - y0 + 2 * pw, 0, 0, H),
               w("bank plate", (x0 + x1) / 2, yc, x1 - x0, y1 - y0 - 2 * C["plate_clr"], 0, DF, DF + D["plate_t"])]
    printed += [Cyl(f"drum post {i + 1}", x, y, D["post_d"] / 2, -H, 0) for i, (x, y) in enumerate(D["screws"])]
    printed += [Box("trigger rest", r[0], r[1], r[3], r[4], r[2], DF - H, DF - H + r[5]) for r in D["rests"]]
    return objs, printed


def scene(build, P, C, L):
    """Every bought part and every printed obstacle: in the enclosure, and in the drum under it."""
    R_in, FZ = L["R_in"], L["floor_z"]
    objs = [box_from(L["boxes"]["shifter"])]
    objs += [box_from(b) for b in L["pi_boxes"]]
    ring = P["led_ring"]
    objs.append(Cyl("LED ring", 0, 0, ring["od"] / 2, L["ring_z0"], L["ring_z1"]))
    # the drum's screws, and the screwdriver's way down to each (they go in before the shelf)
    printed = [Cyl("drum screw", x, y, 4.0, FZ, L["shelf_z"]) for x, y in L["drum"]["screws"]]
    printed += [Cyl(f"shelf post {i + 1}", *polar(L["post_r"], a), C["post_d"] / 2, FZ, L["shelf_z"])
                for i, a in enumerate(L["post_angs"])]
    printed.append(Cyl("shelf", 0, 0, L["shelf_r"], L["shelf_z"], L["shelf_top"]))
    base_h = L["base_h"]
    printed += [Box("lid spigot pad", *polar(R_in - C["clr"] - C["lid_screw_pad"] / 2, a), C["lid_screw_pad"], 10, a,
                    base_h - C["spigot_h"], base_h) for a in L["lid_screw_angs"]]
    r_b = ptz_bolts(P["ptz"])[0] / 2
    head_r = P["ptz"]["head_d"] / 2 + 0.5
    printed += [Cyl("PTZ screw head", *polar(r_b, a), head_r, base_h - L["below_lid"], base_h) for a in L["bolt_angs"]]
    cs = L["cable_slot"]
    printed.append(Cyl("ribbon slack", *polar(cs["r"], cs["ang"]), cs["w"] / 2 + 4,
                       base_h - C["ribbon_slack_h"] + 1, base_h))
    d_objs, d_printed = drum_scene(P, C, L)
    objs += d_objs
    printed += d_printed
    standoffs = [Cyl("Pi standoff", x, y, 2.9, L["shelf_top"], L["pi"]["z"]) for x, y in L["pi_holes"]]
    heads = [Cyl("shelf screw head", *polar(L["post_r"], a), 3.2, L["shelf_top"], L["shelf_top"] + 3) for a in L["post_angs"]]
    return objs, printed, standoffs, heads


def audit(build, P, C, L, stl_dir=None) -> Audit:
    A = Audit(build)
    uwb = build == "with_uwb"
    R_in, R_out, FZ = L["R_in"], L["base_d"] / 2, L["floor_z"]
    objs, printed, standoffs, heads = scene(build, P, C, L)
    D = L["drum"]
    H = D["h"]
    in_drum = lambda o: o.z1 <= EPS
    through_wall = {"rocker switch", "rocker switch ring"}

    # 1. inside the enclosure and the drum
    bad = [f"{o.name} reaches r={o.rmax():.1f}" for o in objs
           if not in_drum(o) and o.name != "Pi USB-C plug" and o.rmax() > R_in - 0.01]
    bad += [f"{o.name} reaches r={o.rmax():.1f}" for o in objs if o.name == "Pi USB-C plug" and o.rmax() > R_in - 0.5]
    A.check(not bad, "Every bought part in the enclosure is inside its wall",
            "; ".join(bad) or f"inner radius {R_in:.1f} mm; furthest part at r = "
            f"{max(o.rmax() for o in objs if not in_drum(o)):.1f} mm")
    tall = [o for o in objs + standoffs]
    over = [f"{o.name} top at z={o.z1:.1f}" for o in tall if o.z1 > L["base_h"] - 0.01]
    A.check(not over, "Everything is below the lid", "; ".join(over) or f"lid underside at z = {L['base_h']} mm")
    bad = [f"{o.name} reaches r={o.rmax():.1f}" for o in objs
           if in_drum(o) and o.name not in through_wall | {"power bank"} and o.rmax() > D["R_in"] - 0.01]
    A.check(not bad, "Every power part is inside the drum, under the enclosure floor",
            "; ".join(bad) or f"drum Ø{L['base_d']} × {H:g} mm; buck and latch on edge against the bank pocket's walls, "
            f"PD trigger on its floor, rocker switch in its wall", ["buck", "latch", "pd_trigger", "switch"])

    # 2. no two parts overlap, and none hits a printed feature
    allp = objs + printed + standoffs + heads
    clashes = []
    for a, b in itertools.combinations(allp, 2):
        names = {a.name, b.name}
        if names <= {"shelf", "LED ring"} or ("shelf" in names and ("post" in a.name + b.name)):
            continue
        if names == {"PD trigger", "trigger rest"}:     # the rest is under the board, holding it up
            continue
        if names == {"power bank", "bank plate"}:      # the bank lies on it
            continue
        if names == {"rocker switch", "rocker switch ring"}:
            continue
        if "Pi standoff" in names and ("Pi board" in names or "Pi underside" in names or "shelf" in names):
            continue
        if "shelf screw head" in names and ("shelf" in names or "post" in (a.name + b.name)):
            continue
        if a in printed and b in printed:
            continue
        if a.name.startswith("Pi ") and b.name.startswith("Pi ") and "standoff" not in a.name + b.name:
            continue          # pieces of the same board
        if collide(a, b):
            clashes.append(f"{a.name} × {b.name}")
    A.check(not clashes, "No two parts overlap, and none hits a post, a pocket wall, a drum screw, the shelf or the lid",
            "; ".join(sorted(set(clashes))) or f"{len(allp)} envelopes checked pairwise")

    # 3. light path
    A.check(L["power_top"] <= L["window_z"] + EPS, "Nothing on the enclosure floor stands in front of the LED window",
            ("the level shifter on the floor, top at z = " + f"{L['power_top']:.1f}" if L["shifter_on"] == "deck" else
             "the floor is clear: the power parts are in the drum")
            + f"; window {L['window_z']:.1f}–{L['window_z'] + C['led_window_h']:.1f}")
    A.check(L["ring_z0"] >= L["window_z"] - EPS and L["ring_z1"] <= L["shelf_z"] + EPS,
            "The LED ring hangs under the shelf, inside the window band",
            f"ring z = {L['ring_z0']:.1f}–{L['ring_z1']:.1f}", ["led_ring"])

    # 4. the drum: the switch in its wall, the boards on its pocket walls and floor
    S_ = D["switch"]
    probs = []
    if uwb:
        for b in (90, 270, 180):
            if angdiff(S_["ang"], b) < math.degrees((C["arm_w"] / 2 + 2 + S_["r"]) / R_out):
                probs.append(f"the switch at {S_['ang']}° is behind the {'mast foot' if b == 180 else 'anchor arm'} at {b}°")
    if S_["z"] + S_["r"] > H + EPS or S_["z"] - S_["r"] < -EPS:
        probs.append("the switch's seat runs off the drum wall")
    A.check(not probs, "The rocker switch is in the drum wall, clear of the bank's opening"
            + (" and the anchor bosses" if uwb else ""),
            "; ".join(probs) or f"at {S_['ang']}°, {S_['z']:g} mm up the {H:g} mm wall (the bank's opening faces {D['ang']}°)", ["switch"])
    sw = P["switch"]
    pt = S_["panel_t"]
    A.check(pt >= 2.0 - EPS and pt + sw["nut_t"] <= sw["thread_l"] + EPS,
            "The rocker switch's ring clamps it to the wall",
            f"{pt} mm of wall between the bezel's flat seat and the ring's boss; {sw['nut_t']} mm ring on a "
            f"{sw['thread_l']} mm thread", ["switch"])
    A.check(sw["hole_d"] / 2 < sw["hole_d_minus_flat"] < sw["hole_d"] and sw["flat_side"] in FLAT_ROT,
            "The rocker switch's key flat is keyed into its hole",
            f"thread Ø{sw['hole_d']}, {sw['hole_d_minus_flat']} across the flat, flat at the {sw['flat_side']}"
            f" (must be one of {', '.join(FLAT_ROT)})", ["switch"])
    fx0 = D["x1"] - C["finger_l"]
    bank_bot = D["bank_z"]
    for k, _, label in STANDOFF_BOARDS:
        bk, m = P[k], L["mounts"][k]
        if "hole_x" in bk:
            b_ok = 0 < bk["hole_x"] < bk["l"] and 0 < bk["hole_dy"] < bk["w"]
            pattern = f"2 holes {bk['hole_dy']} mm apart, {bk['hole_x']} mm in from the socket end, and a printed rest under the other"
        else:
            b_ok = 0 < bk["hole_dx"] < bk["l"] and 0 < bk["hole_dy"] < bk["w"]
            pattern = f"standoffs {bk['hole_dx']}×{bk['hole_dy']} mm"
        if m["on"] == "wall":
            e = D["edge"][k]
            hl = e["holes_local"]
            r_ = m["head_d"] / 2
            b_ok &= all(D["floor"] + r_ <= z <= H - r_ for _, _, z, _ in hl)
            b_ok &= all(D["y0"] + r_ <= y <= D["y1"] - r_ if e["wall"] == "back" else
                        D["x0"] + r_ <= x <= fx0 - r_ for x, y, _, _ in hl)
            wall = {"back": "the pocket's closed end", "+y": "a side wall of the pocket", "-y": "a side wall of the pocket"}[e["wall"]]
            where = f"{wall}, standing on edge"
            through = (f"the {D['pw']:g} mm wall from inside the pocket (countersunk flush, under the bank's sides"
                       f" from {bank_bot:g} mm up; driven before the bank plate goes in"
                       + (", with a stubby screwdriver across the pocket" if e["wall"] != "back" else ", through the open end") + ")")
        elif m["on"] == "drum":
            b_ok &= all(math.hypot(x, y) < D["R_in"] - m["head_d"] / 2 for x, y in m["holes"])
            where = "the drum floor"
            through = f"the {m['through']:g} mm drum floor"
        elif m["on"] == "floor":
            b_ok &= all(math.hypot(x, y) < R_in - m["head_d"] / 2 and
                        all(math.dist((x, y), q) > m["head_d"] / 2 + 4 for q in D["screws"]) for x, y in m["holes"])
            where = "the enclosure floor, clear of the drum's screws and the wall"
            through = f"the {m['through']:g} mm floor"
        else:
            b_ok &= all(math.hypot(x, y) < L["shelf_r"] - m["head_d"] / 2 for x, y in m["holes"])
            where = "the shelf"
            through = f"the {m['through']:g} mm shelf"
        A.check(b_ok, f"The {label}'s standoffs land on {where}",
                f"{pattern} on a {bk['l']}×{bk['w']} board; {len(m['holes'])} × M{bk['screw_d']:g} × {m['l']} "
                f"countersunk through {through}", [k])
    # the bank's cable: a right-angle plug in the bank's face, out through the nearer finger window, to the trigger
    yc = (D["y0"] + D["y1"]) / 2
    tb = L["boxes"]["trigger"]
    tx, ty = rot((tb["cx"], tb["cy"]), -D["ang"])
    sock = (tx + tb["l"] / 2 * math.cos(math.radians(tb["ang"] - D["ang"])), ty + tb["l"] / 2 * math.sin(math.radians(tb["ang"] - D["ang"])))
    wins = [(fx0 + C["finger_l"] / 2, s_ * (D["iw"] / 2 + D["pw"] + C["finger_d"] / 2) + yc) for s_ in (1, -1)]
    win = min(wins, key=lambda p_: math.dist(p_, sock))
    run = math.dist((D["x1"] + 8, yc), win) + math.dist(win, sock) + 2 * 25 + 40
    A.check(run <= 300, "The bank's cable reaches the PD trigger inside the drum",
            f"≈ {run:.0f} mm: right-angle plug in the bank's face, round through the nearer finger window to the trigger's socket, "
            f"with slack to unplug it; the cable in the bill of materials is 300 mm", ["pd_trigger"])

    ribs = sorted(L["window_ribs"])
    span = max(((ribs[(i + 1) % len(ribs)] - ribs[i]) % 360) for i in range(len(ribs))) * math.pi / 180 * R_out - C["window_rib_w"]
    A.check(span <= C["window_bridge"] + 0.5, "The wall above the LED window prints without support",
            f"{len(ribs)} ribs; longest bridge {span:.0f} mm (limit {C['window_bridge']})")

    # 5. shelf, posts and Pi mounting
    pa = sorted(L["post_angs"])
    gaps = [pa[1] - pa[0], pa[2] - pa[1], 360 - pa[2] + pa[0]]
    A.check(max(gaps) < 180, "Three posts hold the shelf level (its centre is inside them)",
            f"posts at {', '.join(f'{a}°' for a in pa)}; widest gap {max(gaps)}°")
    u = polar(1, L["gap_ang"])
    in_gap = [a for a in pa if (polar(L["post_r"], a)[0] * u[0] + polar(L["post_r"], a)[1] * u[1]) > L["gap_d"] - 5]
    A.check(not in_gap, "No post is under the shelf's cable gap", f"gap {L['shelf_r'] - L['gap_d']:.0f} mm deep at {L['gap_ang']:.0f}°")
    edge = min(L["shelf_r"] - math.hypot(x, y) for x, y in L["pi_holes"])
    gap_edge = min(L["gap_d"] - (x * u[0] + y * u[1]) for x, y in L["pi_holes"])
    A.check(min(edge, gap_edge) >= 3, "The Pi's holes have plastic round them on the shelf",
            f"nearest edge {min(edge, gap_edge):.1f} mm", ["pi"])
    A.check(P["pi"]["standoff_h"] >= P["pi"]["under_h"] + 0.5, "The Pi's standoffs clear the parts under the board",
            f"{P['pi']['standoff_h']} mm standoffs, {P['pi']['under_h']} mm underneath", ["pi"])
    wh = D["wire_hole"]
    w_ok = math.hypot(wh[0], wh[1]) + wh[2] / 2 < R_in - 1 and all(
        math.dist(wh[:2], polar(L["post_r"], a)) > wh[2] / 2 + C["post_d"] / 2 + 1 for a in L["post_angs"]) and all(
        math.dist(wh[:2], q) > wh[2] / 2 + 4 for q in D["screws"])
    A.check(w_ok, "The leads from the drum have a hole up through the enclosure floor",
            f"Ø{wh[2]:g} at ({wh[0]:.0f}, {wh[1]:.0f}), over the buck, clear of the posts and the drum's screws")

    # 6. tripod: the nut in the bank plate, on the drum floor
    nut = P["tripod_nut"]
    A.check(nut["t"] + 0.5 <= D["plate_t"] + EPS and D["floor"] >= 2.5 - EPS and C["tripod_clear_d"] < nut["af"] - 2,
            "The tripod nut fits its hex hole in the bank plate",
            f"nut {nut['af']} mm across the flats × {nut['t']} mm in the {D['plate_t']:g} mm plate, pulled down onto the "
            f"{D['floor']:g} mm drum floor by the tripod screw; the bank slides in over it", ["tripod_nut"])

    # 7. camera mount
    ptz = P["ptz"]
    cs = L["cable_slot"]
    diag = ptz_bolts(ptz)[0]
    A.check(L["ptz_slot_min"] <= diag <= L["ptz_slot_max"], "The Arducam base's standoffs land on the lid slots",
            f"standoffs {ptz['horizontal_bolt_spacing']:g} × {ptz['vertical_bolt_spacing']:g} mm, {diag:g} corner to corner, "
            f"at {', '.join(f'{a:g}°' for a in L['bolt_angs'])}; slots take {L['ptz_slot_min']:g}–{L['ptz_slot_max']:g}"
            + ("" if (L["ptz_slot_min"], L["ptz_slot_max"]) == (C["ptz_bolt_min"], C["ptz_bolt_max"]) else " (stretched to fit your base)"), ["ptz"])
    grip = ptz["bolt_l"] - C["lid_t"] - L["ptz_lift"] + L["screw_recess"]
    A.check(L["screw_recess"] <= C["lid_t"] - 2 and grip <= ptz["standoff_h"] - 2, "The PTZ screws reach into the standoffs",
            f"M3 × {ptz['bolt_l']} up through the {C['lid_t']} mm lid"
            + (f" and {L['ptz_washers']} washers" if L["ptz_washers"] else "") + f": {grip:g} mm of thread in each standoff"
            + (f"; lid counterbored {L['screw_recess']:.1f} mm under each slot" if L["screw_recess"] else ""), ["ptz"])
    clear = ptz["standoff_h"] + L["ptz_lift"] - ptz["servo_drop"]
    A.check(clear >= SERVO_CLEAR - EPS, "The pan servo under the base clears the lid",
            f"servo hangs {ptz['servo_drop']:g} mm below the base, on {ptz['standoff_h']:g} mm standoffs"
            + (f" lifted on {L['ptz_washers']} M3 washers each ({L['ptz_lift']:g} mm)" if L["ptz_washers"] else "")
            + f": {clear:.1f} mm above the lid"
            + ("" if clear >= SERVO_CLEAR - EPS else
               f"; needs {SERVO_CLEAR:g} — more than {PTZ_WASHERS_MAX} washers would take, so use longer standoffs"), ["ptz"])
    A.check(cs["w"] >= ptz["ribbon_w"] + 2 and cs["d"] >= ptz["lead_bundle_d"] + 1, "The ribbon and leads fit the lid's cable slot",
            f"slot {cs['w']:g}×{cs['d']:g} mm at {cs['ang']:g}° (180° = straight behind the lens); "
            f"ribbon {ptz['ribbon_w']} mm wide, leads Ø{ptz['lead_bundle_d']}", ["ptz"])
    # the ribbon's run: camera board → over the turntable → cable slot → the Pi's CSI socket
    sx, sy = polar(cs["r"], cs["ang"])
    pi_ = L["pi"]
    cx, cy = rot((PI_CSI[0] - P["pi"]["l"] / 2, PI_CSI[1] - P["pi"]["w"] / 2), pi_["ang"])
    inside = math.dist((sx, sy, L["base_h"]), (pi_["x"] + cx, pi_["y"] + cy, pi_["z"] + P["pi"]["pcb_t"])) + 15
    outside = math.hypot(ptz["standoff_h"] + L["ptz_lift"] + ptz["tilt_axis_h"], cs["r"]) + PTZ_HEAD_ARM + C["ptz_loop"]
    run = outside + C["lid_t"] + inside
    A.check(run <= ptz["ribbon_l"], "The camera ribbon reaches the Pi",
            f"≈ {run:.0f} mm needed ({outside:.0f} outside with a {C['ptz_loop']} mm loop for pan and tilt, "
            f"{inside:.0f} inside); ribbon {ptz['ribbon_l']} mm", ["ptz", "pi"])

    # 8. the bank in the drum (C4a): it slides in, the catch holds it, it pinches out
    bk = P["power_bank"]
    yc = (D["y0"] + D["y1"]) / 2
    front = [D["R_out"] - math.hypot(D["x1"], y) for y in (D["y0"], D["y1"])]
    rec = math.sqrt(D["R_out"] ** 2 - yc ** 2) - D["x1"]
    A.check(min(front) >= -0.01 and D["x0"] - D["pw"] < 0,
            "The bank's pocket runs across the drum, open at one side",
            f"its open end faces {D['ang']}°; the bank's front face is {rec:.0f} mm in from the outline at the middle, "
            f"{abs(min(front)):.0f} mm at its nearer corner", ["power_bank"])
    t, ln, h = C["bar_t"], C["bar_span"], C["catch_h"]
    strain = 6 * t * h / ln ** 2           # a bar held at both ends, pushed down h in the middle
    A.check(1.5 <= h <= 4 and strain <= 0.02 and D["plate_t"] - t >= h + 1 and C["finger_l"] >= 20
            and C["catch_w"] < ln - 10 and ln < D["iw"] - 2 * C["plate_clr"]
            and D["x1"] + C["catch_l"] <= math.sqrt(D["R_out"] ** 2 - (abs(yc) + C["catch_w"] / 2) ** 2),
            "The bank slides in, the catch snaps up behind it, and it pinches out at the open end",
            f"{h:g} mm catch on a {ln:g} mm crossbar along the bank plate's front edge, {t:g} mm thick, held at both ends "
            f"({100 * strain:.1f} % strain pressed flat; PETG takes about 2 %); {C['finger_l']:g} mm finger windows each side, "
            f"from {D['bank_z'] + C['finger_z']:g} mm up", ["power_bank"])
    angs = sorted(D["post_angs"])
    n = len(angs)
    gaps = [angs[(i + 1) % n] - angs[i] + (360 if i == n - 1 else 0) for i in range(n)]
    A.check(n >= 3 and max(gaps) < 150 and C["base_wall"] + 4 <= D["screw_l"] <= C["base_wall"] + C["drum_insert_h"],
            "The drum screws up under the enclosure on posts spread round it",
            f"{n} posts at {', '.join(f'{a:g}°' for a in angs)} (widest gap {max(gaps):.0f}°), each an M3 insert; "
            f"{n} × M3 × {D['screw_l']} countersunk down through the enclosure floor, before the shelf", ["power_bank"])

    # 9. UWB parts
    if uwb:
        ul, ext = P["ula1"], P["usb_extension"]
        A.check(L["ula1_tangential"] or L["ula1_radial_room"] >= ext["female_l"] + 3,
                "The anchor boards' USB plugs have room for the extension cables",
                (f"boards turned across the arms, plug towards −X: {L['ula1_radial_room']:.0f} mm between plug and arm root "
                 f"is too short for the {ext['female_l']} mm socket end, so it runs off to the side")
                if L["ula1_tangential"] else f"{L['ula1_radial_room']:.0f} mm between plug and arm root", ["ula1", "usb_extension"])
        e = L["usb_entry"]
        e_ok = all(angdiff(e["ang"], a) >= math.degrees((e["w"] / 2 + 6) / R_out) for a in L["lid_screw_angs"])
        A.check(e_ok and P["usb_extension"]["male_w"] <= e["w"] and P["usb_extension"]["male_h"] <= e["h"],
                "The anchor USB cables have a way into the enclosure, and room to plug into the Pi",
                f"slot {e['w']:.0f}×{e['h']:.0f} mm at {e['ang']}°, z = {e['z']:.0f}, behind the Pi's USB ports; "
                f"{P['usb_extension']['male_l']} mm kept clear beyond them for the plugs", ["usb_extension"])
        A.check(ul["hole_dx"] < ul["l"] and ul["hole_dy"] < ul["w"], "The ULA1 hole pattern is inside the board",
                f"{ul['hole_dx']}×{ul['hole_dy']} on {ul['l']}×{ul['w']}", ["ula1"])
        A.check(0 < L["dowel_l"] <= P["dowel"]["stock_l"], "The mast dowel can be cut from the stock length",
                f"cut to {L['dowel_l']:.0f} mm from {P['dowel']['stock_l']} mm", ["dowel"])
        pod = L["pod"]
        pod_l = pod["inner_l"] + 2 * C["pod_wall"]
        A.check(pod_l <= C["pod_max_l"] and pod_l <= PRINT_LIMIT,
                "The wearable pod holds the tag plugged straight into its bank",
                f"tag in line with the bank: pod {pod_l:.0f} × {pod['inner_w'] + 2 * C['pod_wall']:.0f} mm (limit {C['pod_max_l']})",
                ["tag_bank", "ula1"])

    # 10. device constants
    path, cur, new = device_config_text(build, P, L)
    A.check(cur == new, "Device config matches the geometry",
            ", ".join(f"{k} = {v}" for k, v in device_updates(build, P, L).items()))

    # 11. the printed parts themselves
    stl_dir = stl_dir or os.path.join(ROOT, build, "cad", "stl")
    stamp = os.path.join(stl_dir, STAMP)
    fresh = os.path.exists(stamp) and open(stamp).read().strip() == inputs_hash(build)
    A.check(fresh, "STLs are rendered from the current CAD and part sizes",
            "" if fresh else "run python3 cad/fit.py to re-render")
    for f in sorted(os.listdir(stl_dir)) if os.path.isdir(stl_dir) else []:
        if not f.endswith(".stl"):
            continue
        size, bodies = stl_info(os.path.join(stl_dir, f))
        want = EXPECTED_BODIES.get(f, 1)
        A.check(max(size) <= PRINT_LIMIT and bodies == want, f"{f} prints in one piece on the {PRINTER}",
                f"{' × '.join(f'{s:.0f}' for s in size)} mm" + ("" if bodies == want else f"; {bodies} separate bodies, expected {want}"))

    todo = measure_todos()
    assumed = [f"{v.get('name', k)} (item {v.get('bom', '?')}: {', '.join(todo[k])})" for k, v in P.items() if k in todo]
    if assumed:
        A.note("Still marked MEASURE_TODO in ordered_parts.toml", "; ".join(assumed))
    if L.get("attempts"):
        A.note("Narrower enclosures tried first", "; ".join(L["attempts"]))
    return A


# ======================================================================
#  OpenSCAD
# ======================================================================

def render(build):
    cad = os.path.join(ROOT, build, "cad")
    if not shutil.which("openscad"):
        print("  openscad not found — STLs not re-rendered")
        return False
    subprocess.run(["bash", os.path.join(cad, "render_all.sh")], check=True,
                   env={**os.environ, "SPORTCAM_FIT_RUNNING": "1"})
    with open(os.path.join(cad, "stl", STAMP), "w") as f:
        f.write(inputs_hash(build) + "\n")
    return True


def refresh_guide(build):
    try:
        import numpy  # noqa: F401
        import stl    # noqa: F401
        import matplotlib  # noqa: F401
    except ImportError:
        print("  numpy-stl / matplotlib not installed — guide meshes and previews not refreshed "
              "(pip install numpy-stl matplotlib)")
        return
    for script in (os.path.join(ROOT, "docs", build, "setup", "assembly", "build_models.py"),
                   os.path.join(ROOT, build, "cad", "render_previews.py"),
                   os.path.join(ROOT, "docs", build, "setup", "assembly", "render_steps.py")):
        subprocess.run([sys.executable, script], check=True, stdout=subprocess.DEVNULL)


def deep_check(build, L, P, C) -> list:
    """Intersect each printed part, in its assembled place, with the bought-part
    envelopes using OpenSCAD itself. Catches CAD that drifted from the model above."""
    if not shutil.which("openscad"):
        return ["openscad not found"]
    objs, printed, standoffs, heads = scene(build, P, C, L)
    cad = os.path.join(ROOT, build, "cad")

    def solid(o, shrink=0.15):
        if o.kind == "cyl":
            return (f"translate([{o.cx:.3f},{o.cy:.3f},{o.z0 + shrink:.3f}]) "
                    f"cylinder(r={max(o.r - shrink, 0.1):.3f}, h={max(o.z1 - o.z0 - 2 * shrink, 0.1):.3f}, $fn=32);")
        return (f"translate([{o.cx:.3f},{o.cy:.3f},{o.z0 + shrink:.3f}]) rotate([0,0,{o.ang:.3f}]) "
                f"cube([{max(o.l - 2 * shrink, 0.1):.3f},{max(o.w - 2 * shrink, 0.1):.3f},{max(o.z1 - o.z0 - 2 * shrink, 0.1):.3f}], center=false);"
                .replace("cube(", f"translate([{-(o.l / 2 - shrink):.3f},{-(o.w / 2 - shrink):.3f},0]) cube("))
    # through-wall parts legitimately pass through their openings, and the PD trigger stands on its printed rest
    envelopes = [o for o in objs if o.name not in ("rocker switch", "rocker switch ring", "Pi USB-C plug", "PD trigger")]
    D = L["drum"]
    parts = {
        "base_housing": f'import("{cad}/stl/base_housing.stl");',
        "shelf": f'translate([0,0,{L["shelf_z"]}]) import("{cad}/stl/shelf.stl");',
        "lid": f'translate([0,0,{L["base_h"]}]) import("{cad}/stl/lid.stl");',
        "led_diffuser_ring": f'translate([0,0,{L["window_z"] - C["diffuser_lip"]}]) import("{cad}/stl/led_diffuser_ring.stl");',
        "power_drum": f'translate([0,0,{-D["h"]}]) import("{cad}/stl/power_drum.stl");',
        "bank_plate": f'translate([0,0,{-D["h"] + D["floor"]}]) rotate([0,0,{D["ang"]}]) import("{cad}/stl/bank_plate.stl");',
    }
    def ask(td, name, head, body, solids):
        src, out = os.path.join(td, f"{name}.scad"), os.path.join(td, f"{name}.stl")
        with open(src, "w") as f:
            f.write(head + "intersection(){ union(){ " + body + " }\n union(){\n" + "\n".join(solids) + "\n} }\n")
        if os.path.exists(out):
            os.remove(out)
        r = subprocess.run(["openscad", "-o", out, src], capture_output=True, text=True)
        if "CGAL error" in r.stderr:
            return None       # the kernel gave up (and hands back its first operand): not an answer
        return not ("empty" in r.stderr or not os.path.exists(out) or os.path.getsize(out) < 200)

    def meets(td, name, solids):
        """Does the part intersect these solids? Asked of its STL; if CGAL chokes on the
        re-imported mesh (it can, on a sound one), asked again of the part's CAD source.
        None if OpenSCAD could not say either way."""
        hit = ask(td, name, "", parts[name], solids)
        if hit is None:
            hit = ask(td, name, f'use <{cad}/{name}.scad>\n', parts[name].replace(f'import("{cad}/stl/{name}.stl");', f"{name}();"), solids)
        return hit

    hits = []
    with tempfile.TemporaryDirectory() as td:
        for name in parts:
            if meets(td, name, [solid(o) for o in envelopes]) is False:
                continue
            # find which envelope(s)
            for o in envelopes:
                hit = meets(td, name, [solid(o)])
                if hit is None:
                    hits.append(f"{name} × {o.name} (OpenSCAD could not evaluate it)")
                elif hit:
                    hits.append(f"{name} × {o.name}")
    return hits


# ======================================================================
#  report
# ======================================================================

def report_md(results) -> str:
    lines = ["# Fit report", "",
             "Generated by `python3 cad/fit.py` — do not edit. It audits that every "
             "printed and bought part fits together in both builds, using the part "
             "sizes in [`ordered_parts.toml`](ordered_parts.toml).", ""]
    for build, (L, A) in results.items():
        status = "✅ everything fits" if not A.failed else f"❌ {len(A.failed)} problem(s)"
        lines += [f"## {build.replace('_', ' ')} — {status}", ""]
        if L:
            lines += [f"Enclosure Ø{L['base_d']} × {L['base_h']} mm (floor to lid), on a power drum "
                      f"Ø{L['base_d']} × {L['drum']['h']:g} mm: {L['drum']['h'] + L['base_h'] + L['lid_t']:g} mm "
                      f"from the tripod plate to the top of the lid. LED window "
                      f"{L['window_z']:.0f}–{L['window_z'] + 12:.0f}; shelf at {L['shelf_z']:.0f}; "
                      f"Pi on {len(L['pi_holes'])} standoffs at z = {L['pi']['z']:.0f}, turned {L['pi']['ang']}°.", ""]
        lines += ["| | Check | Detail |", "| --- | --- | --- |"]
        for st, title, detail, _ in A.rows:
            icon = {"PASS": "✅", "FAIL": "❌", "NOTE": "ℹ️"}[st]
            lines.append(f"| {icon} | {title} | {detail.replace('|', '/')} |")
        lines.append("")
    return "\n".join(lines)


def print_audit(A):
    for st, title, detail, _ in A.rows:
        if st == "PASS":
            print(f"  ok    {title}")
        elif st == "FAIL":
            print(f"  FAIL  {title}\n          {detail}")
        else:
            print(f"  note  {title}: {detail}")


# ======================================================================
#  main
# ======================================================================

def run(builds, check=False, do_render=True, deep=False, force_render=False) -> int:
    results = {}
    rc = 0
    for build in builds:
        print(f"\n== {build}")
        P, C = load_parts(build), load_config(build)
        try:
            L = solve(build, P, C)
        except NoFit as e:
            print(f"  FAIL  no layout fits: {e}")
            A = Audit(build)
            A.check(False, "A layout exists for these part sizes", str(e))
            results[build] = (None, A)
            rc = 1
            continue
        files = generated(build, P, C, L)
        path, cur, new = device_config_text(build, P, L)
        if check:
            stale = [os.path.relpath(p, ROOT) for p, t in files.items()
                     if not os.path.exists(p) or open(p, encoding="utf-8").read() != t]
            if stale:
                print("  FAIL  generated files are out of date: " + ", ".join(stale) +
                      "\n          run python3 cad/fit.py")
                rc = 1
        else:
            changed = [os.path.relpath(p, ROOT) for p, t in files.items() if write_if_changed(p, t)]
            if cur != new:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new)
                changed.append(os.path.relpath(path, ROOT))
            print(f"  layout: Ø{L['base_d']} × {L['base_h']} mm, Pi at {L['pi']['ang']}°, "
                  f"drum {L['drum']['h']:g} mm, bank opening {L['drum']['ang']}°, switch {L['drum']['switch']['ang']}°"
                  + (", anchor boards turned across the arms" if L.get("ula1_tangential") else ""))
            if changed:
                print("  wrote " + ", ".join(changed))
            stamp = os.path.join(ROOT, build, "cad", "stl", STAMP)
            stale_stl = not os.path.exists(stamp) or open(stamp).read().strip() != inputs_hash(build)
            if do_render and (stale_stl or force_render):
                print("  rendering STLs …")
                if render(build):
                    refresh_guide(build)
        A = audit(build, P, C, L)
        if deep:
            hits = deep_check(build, L, P, C)
            A.check(not hits, "Mesh check: no printed part intersects a bought part (OpenSCAD)", "; ".join(hits) or "clean")
        print_audit(A)
        results[build] = (L, A)
        if A.failed:
            rc = 1
    if not check and set(builds) == set(BUILDS):
        write_if_changed(REPORT_FILE, report_md(results))
    print("\n" + ("all checks passed" if rc == 0 else "FIT CHECK FAILED — see above (and cad/FIT_REPORT.md)"))
    return rc


def watch(builds, do_render):
    def snapshot():
        files = [PARTS_FILE] + [os.path.join(ROOT, b, "cad", f) for b in builds
                                for f in os.listdir(os.path.join(ROOT, b, "cad"))
                                if f.endswith(".scad") and f != "layout.scad"]
        return {f: hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files}
    last = None
    print("watching cad/ordered_parts.toml and <build>/cad/*.scad — Ctrl-C to stop")
    while True:
        snap = snapshot()
        if snap != last:
            run(builds, do_render=do_render)
            last = snapshot()
        time.sleep(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--render", action="store_true", help="render even if the STLs look current")
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--build", choices=BUILDS)
    a = ap.parse_args()
    builds = [a.build] if a.build else list(BUILDS)
    if a.watch:
        watch(builds, not a.no_render)
        return 0
    return run(builds, check=a.check, do_render=not a.no_render, deep=a.deep, force_render=a.render)


if __name__ == "__main__":
    sys.exit(main())
