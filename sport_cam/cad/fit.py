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
    <build>/docs/setup/assembly/layout.js   for the 3D assembly guide
    <build>/cad/stl/*.stl           via render_all.sh
    src/<build>/device/sportcam/config.py  geometry constants kept in step
    cad/FIT_REPORT.md               the audit, both builds

The layout ("option B"): bottom to top, the power boards stuck to the
enclosure floor; the LED ring under a printed shelf, shining out through the
LED window; the Raspberry Pi on the shelf; the lid with the camera. The
battery tray is outside, under the enclosure or on a tripod leg.

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

# Printed parts and how many separate bodies each STL should contain
# (the wearable is printed as body + lid side by side).
EXPECTED_BODIES = {"wearable_case.stl": 2}
# Boards taped to the enclosure floor, placed in this order after the PD trigger.
DECK_BOARDS = (("buck", "buck converter"), ("gauge", "battery gauge"), ("latch", "power latch"))
MAX_DECK_TRIES = 40        # floor arrangements tried per enclosure size before going wider


class NoFit(Exception):
    """No layout satisfies the constraints at this size."""


# ======================================================================
#  inputs
# ======================================================================

def load_parts(build: str) -> dict:
    with open(PARTS_FILE, "rb") as f:
        raw = tomllib.load(f)
    return {k: v for k, v in raw.items() if build in v.get("builds", BUILDS)}


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
        # flat on the floor first; then on printed risers over the tripod boss,
        # which frees the middle of the floor for a board too big to go round it
        for raised in (False, True):
            try:
                L = solve_at(build, P, C, d, raised)
                L["attempts"] = attempts
                return L
            except NoFit as e:
                attempts.append(f"Ø{d:g}{' on risers' if raised else ''}: {e}")
        d += 2
    raise NoFit("no layout fits up to the widest enclosure the A1 Mini can print "
                f"(Ø{max_base_d(build, C)}):\n    " + "\n    ".join(attempts[-4:]))


def solve_at(build, P, C, base_d, raised=False):
    uwb = build == "with_uwb"
    R_out = base_d / 2
    R_in = R_out - C["base_wall"]
    FZ = C["base_wall"]
    gap, wgap = C["part_gap"], C["wall_gap"]
    r_shelf = R_in - C["clr"] - 0.5
    pi = P["pi"]

    # ---- wall features: heights and footprints --------------------------
    tr, sw, jk = P["pd_trigger"], P["switch"], P["jack"]
    deck_z = FZ + C["tape_t"]
    # buck, gauge and power latch: on the floor, or on risers just clear of the tripod boss
    riser_h = C["tripod_boss_h"] + 1 - FZ if raised else 0.0
    board_z = deck_z + riser_h
    usbc_zc = deck_z + tr["h"] - tr["port_h"] / 2
    usbc_w, usbc_h = tr["plug_w"] + 1, tr["plug_h"] + 1
    sw_zc = FZ + sw["body_h"] / 2 + 1
    jk_zc = FZ + jk["body_d"] / 2 + 1
    feat_half = {   # half-width at the wall, mm
        "usbc": max(tr["w"], usbc_w) / 2,
        "switch": sw["body_w"] / 2,
        "jack": jk["body_d"] / 2,
    }
    low_top = max(usbc_zc + usbc_h / 2, sw_zc + sw["body_h"] / 2, jk_zc + jk["body_d"] / 2)

    blocked = []    # (angle, half-angle) where low wall features can't go
    if uwb:
        hb = math.degrees((C["arm_w"] / 2 + 2 + 3) / R_out)
        blocked = [(90, hb), (270, hb), (180, hb)]

    def ang_ok(a, half_mm, extra=()):
        h = math.degrees((half_mm + 3) / R_out)
        if any(angdiff(a, b) < h + hw for b, hw in blocked):
            return False
        return all(angdiff(a, b) >= h + hw for b, hw in extra)

    cand = [a for a in range(0, 360, 15)]
    pref = lambda a: -math.cos(math.radians(a))          # back of the head (−X) first
    combos = []
    for u in sorted(cand, key=pref, reverse=True):
        if not ang_ok(u, feat_half["usbc"]):
            continue
        hu = (u, math.degrees((feat_half["usbc"] + 3) / R_out))
        for j in sorted(cand, key=pref, reverse=True):
            if not ang_ok(j, feat_half["jack"], [hu]):
                continue
            hj = (j, math.degrees((feat_half["jack"] + 3) / R_out))
            for s in sorted(cand, key=pref, reverse=True):
                if not ang_ok(s, feat_half["switch"], [hu, hj]):
                    continue
                combos.append((u, j, s))
    combos.sort(key=lambda c: -(pref(c[0]) + pref(c[1]) + 0.5 * pref(c[2])))
    if not combos:
        raise NoFit("no room on the wall for the USB-C inlet, the jack and the switch")

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

    ptz = P["ptz"]
    tail = ptz["bolt_l"] - ptz["plate_t"] - C["lid_t"]
    nut_recess = 0.0 if tail >= ptz["nut_h"] else ptz["nut_h"] - tail + 0.3
    below_lid = max(tail, 0.0)
    r_bolt = ptz["bolt_spacing"] / 2
    # the lid's slots cover the configured range, stretched to your base if needed
    slot_min = min(C["ptz_bolt_min"], ptz["bolt_spacing"] - 6)
    slot_max = max(C["ptz_bolt_max"], ptz["bolt_spacing"] + 6)
    if slot_max / 2 + ptz["nut_af"] / math.sqrt(3) + 1 > R_in - C["clr"] - C["spigot_w"] - 1:
        raise NoFit(f"the Arducam base's bolts ({ptz['bolt_spacing']} mm apart) land on the lid's locating ring")
    if r_bolt - ptz["nut_af"] / math.sqrt(3) < C["ptz_cable_d"] / 2 + 0.5:
        raise NoFit(f"the Arducam base's bolts ({ptz['bolt_spacing']} mm apart) land in the lid's cable opening")
    nut_r = ptz["nut_af"] / math.sqrt(3) + 0.5
    lid_screw_angs = [45, 135, 225, 315]

    def ceiling_need(objs, base_h_guess=0.0):
        """How far above each object the lid underside must be (relative)."""
        need = 0.0
        spig_r = R_in - C["clr"] - C["spigot_w"] - 0.5
        pads = [place("pad", (R_in - C["clr"] - C["lid_screw_pad"] - 0.5, R_in, -5.5, 5.5, 0, 1), (0, 0, 0, a))
                for a in lid_screw_angs]
        nuts = [Cyl("nut", *polar(r_bolt, a), nut_r, 0, 1) for a in (0, 90, 180, 270)]
        slack = Cyl("slack", 0, 0, C["ptz_cable_d"] / 2 + 10, 0, 1)
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

    boss = Cyl("tripod boss", 0, 0, C["tripod_boss_d"] / 2, 0, C["tripod_boss_h"])
    post_r = R_in - C["post_d"] / 2 + 1
    last_err = "no arrangement found"

    def deck_spots(part, label, obstacles, first=False):
        """Every grid position/angle where a floor board fits, best first."""
        found = []
        for ang in range(0, 180, 15):
            for x in range(-int(R_in), int(R_in) + 1, 2):
                for y in range(-int(R_in), int(R_in) + 1, 2):
                    b = place(label, (-part["l"] / 2, part["l"] / 2, -part["w"] / 2, part["w"] / 2, 0, part["h"]),
                              (x, y, board_z, ang))
                    if b.rmax() > R_in - wgap or any(collide(b, o, gap) for o in obstacles):
                        continue
                    if raised and any(collide(pad, o, 1) for pad in riser_pads(b) for o in obstacles):
                        continue
                    if first:
                        return [b]
                    found.append(b)
        return found

    def riser_pads(b):
        pads = []
        for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            x, y = rot((sx * (b.l / 2 - 4), sy * (b.w / 2 - 4)), b.ang)
            pads.append(Box("riser", b.cx + x, b.cy + y, 6, 6, b.ang, FZ, FZ + riser_h))
        return pads

    def place_deck(obstacles, trig):
        deck = {"trigger": trig}
        for key, label in DECK_BOARDS:
            spots = deck_spots(P[key], label, obstacles)
            if not spots:
                return None, f"the {label} ({P[key]['l']}×{P[key]['w']} mm) has no room on the floor"
            # near the inlet, out towards the wall
            b = max(spots, key=lambda b: math.hypot(b.cx, b.cy) - 0.4 * math.hypot(b.cx - trig.cx, b.cy - trig.cy))
            deck[key] = b
            obstacles = obstacles + [b]
        return deck, ""

    # quick no: a board that doesn't fit on an empty floor won't fit anywhere
    for key, label in DECK_BOARDS:
        if not deck_spots(P[key], label, [boss], first=True):
            raise NoFit(f"the {label} ({P[key]['l']}×{P[key]['w']} mm) doesn't fit on a Ø{2 * R_in:.0f} floor at all")
    deck_cache = {}
    attempts = 0

    for pose_i, (px, py, pang, gap_d, gap_ang, pi_boxes) in enumerate(poses[:40]):
        u = (math.cos(math.radians(gap_ang)), math.sin(math.radians(gap_ang)))
        holes_w = [(px + hx, py + hy) for hx, hy in (rot(h, pang) for h in holes_l)]
        for (ua, ja, sa) in combos[:60]:
            feats = {"usbc": ua, "jack": ja, "switch": sa}
            # bodies of the wall-mounted parts, inside the wall
            tr_len = tr["l"]
            tr_r = math.sqrt(R_in ** 2 - (tr["w"] / 2) ** 2) - 0.2 - tr_len / 2
            trig = place("PD trigger", (-tr_len / 2, tr_len / 2, -tr["w"] / 2, tr["w"] / 2, 0, tr["h"]),
                         (*polar(tr_r, ua), deck_z, ua))
            swb = place("rocker switch", (R_in - sw["depth"], R_in + C["base_wall"], -sw["body_w"] / 2, sw["body_w"] / 2,
                                          -sw["body_h"] / 2, sw["body_h"] / 2), (0, 0, sw_zc, sa))
            jkb = place("barrel jack", (R_in - jk["depth"], R_in + C["base_wall"], -jk["body_d"] / 2, jk["body_d"] / 2,
                                        -jk["body_d"] / 2, jk["body_d"] / 2), (0, 0, jk_zc, ja))
            wall_parts = [trig, swb, jkb]
            if any(collide(a, b, gap) for a, b in itertools.combinations(wall_parts, 2)):
                last_err = "the wall-mounted parts collide"
                continue

            # ---- shelf posts -------------------------------------------
            post_ok = []
            for a in range(0, 360, 5):
                cx, cy = polar(post_r, a)
                if cx * u[0] + cy * u[1] > gap_d - 5:
                    continue
                post = Cyl("post", cx, cy, C["post_d"] / 2, FZ, 999)
                if any(overlap2d(post, w, gap) for w in wall_parts):
                    continue
                # opening in the wall right behind a post is no good either
                if any(angdiff(a, f) < math.degrees((feat_half[k] + C["post_d"] / 2 + 3) / R_out) for k, f in feats.items()):
                    continue
                head = Cyl("head", cx, cy, 3.2, 0, 1)
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
                last_err = "nowhere to put three shelf posts clear of the cable gap and the wall parts"
                continue
            post_angs = list(best[1])
            posts = [Cyl(f"shelf post {i + 1}", *polar(post_r, a), C["post_d"] / 2, FZ, 999) for i, a in enumerate(post_angs)]

            # ---- the power deck ----------------------------------------
            key = (ua, ja, sa, tuple(post_angs))
            if key not in deck_cache:
                attempts += 1
                if attempts > MAX_DECK_TRIES:
                    raise NoFit(last_err)
                deck_cache[key] = place_deck([boss, *posts, *wall_parts], trig)
            deck, err = deck_cache[key]
            if deck is None:
                last_err = err
                continue
            obstacles = [boss, *posts, *wall_parts, *(deck[k] for k, _ in DECK_BOARDS)]

            # ---- shifter: on the shelf beside the Pi, else on the floor --
            sh = P["shifter"]
            shifter = None
            standoffs = [Cyl("Pi standoff", hx, hy, 3, 0, 1) for hx, hy in holes_w]
            heads = [Cyl("post screw head", *polar(post_r, a), 3.2, 0, 1) for a in post_angs]
            for ang in range(0, 180, 15):
                for x in range(-60, 61, 2):
                    for y in range(-60, 61, 2):
                        b = place("level shifter", (-sh["l"] / 2, sh["l"] / 2, -sh["w"] / 2, sh["w"] / 2, 0, sh["h"]),
                                  (x, y, 0, ang))
                        if b.rmax() > r_shelf - 1:
                            continue
                        if max(cx * u[0] + cy * u[1] for cx, cy in b.corners()) > gap_d - 1:
                            continue
                        flat = [Box(o.name, o.cx, o.cy, o.l, o.w, o.ang, 0, 1) for o in pi_boxes]
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
                                      (x, y, deck_z, ang))
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
            deck_objs = list(deck.values()) + [swb, jkb] + ([shifter[1]] if shifter[0] == "deck" else [])
            power_top = max(o.z1 for o in deck_objs)
            win_h, lip = C["led_window_h"], C["diffuser_lip"]
            ledge_h = C["ledge_h"]
            window_z = power_top + 1
            if uwb:
                window_z = max(window_z, C["arm_boss_z"] + C["arm_root_h"] + 0.5 + lip)
            # the wall openings must stay below the band's ledge
            window_z = max(window_z, low_top + 1 + ledge_h + C["diffuser_t"] + lip)
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
                shifter = ("shelf", Box(b.name, b.cx, b.cy, b.l, b.w, b.ang, shelf_top + C["tape_t"], shelf_top + C["tape_t"] + sh["h"]))
                shelf_objs.append(shifter[1])
            base_h = max(C["base_h_min"], ceiling_need(shelf_objs),
                         shelf_top + C["vent_h"] + 4 + C["spigot_h"])
            base_h = math.ceil(base_h)

            # ---- vents and diffuser ------------------------------------
            ledge_bot = window_z - lip - ledge_h - C["diffuser_t"]
            low_vz = FZ + C["vent_h"] / 2 + 2
            if low_vz + C["vent_h"] / 2 > ledge_bot - 1:
                low_vz = None
            high_vz = (shelf_top + base_h - C["spigot_h"]) / 2
            vent_half = math.degrees((C["vent_w"] / 2 + 3) / R_out)

            def vent_angles(z, lowrow):
                out = []
                for a in range(5, 360, 20):
                    if lowrow:
                        if any(angdiff(a, b) < hw + vent_half for b, hw in blocked):
                            continue
                        if any(angdiff(a, f) < math.degrees((feat_half[k] + 3) / R_out) + vent_half for k, f in feats.items()):
                            continue
                        if any(angdiff(a, p) < math.degrees((C["post_d"] / 2 + 2) / R_out) + vent_half for p in post_angs):
                            continue
                    else:
                        if any(angdiff(a, s) < math.degrees(8 / R_out) + vent_half for s in lid_screw_angs):
                            continue
                        if uwb and z < C["arm_boss_z"] + C["mast_foot_h"] and angdiff(a, 180) < hb_foot + vent_half:
                            continue
                    out.append(a)
                return out

            hb_foot = math.degrees((C["arm_w"] / 2 + 3) / R_out) if uwb else 0
            # window ribs: no unsupported span longer than window_bridge
            n_ribs = math.ceil(2 * math.pi * R_out / (C["window_bridge"] + C["window_rib_w"]))
            window_ribs = [round(post_angs[0] + 360 * i / n_ribs, 2) % 360 for i in range(n_ribs)]
            vents_low = vent_angles(low_vz, True) if low_vz else []
            vents_high = vent_angles(high_vz, False)

            # ---- UWB anchors and wearable ------------------------------
            extra = {}
            if uwb:
                extra = solve_uwb(P, C, base_d)
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

            risers = []
            if raised:
                for k, _ in DECK_BOARDS:
                    for pad in riser_pads(deck[k]):
                        risers.append([round(pad.cx, 3), round(pad.cy, 3), pad.ang, round(riser_h, 3)])
            L = {
                "build": build, "base_d": base_d, "base_h": base_h, "R_in": R_in, "floor_z": FZ,
                "raised": raised, "risers": risers,
                "ptz_slot_min": slot_min, "ptz_slot_max": slot_max,
                "deck_z": deck_z, "power_top": power_top,
                "window_z": window_z, "shelf_z": shelf_z, "shelf_top": shelf_top, "shelf_r": r_shelf,
                "gap_ang": gap_ang, "gap_d": gap_d,
                "post_r": post_r, "post_angs": post_angs, "window_ribs": window_ribs,
                "ring_z0": ring_z0, "ring_z1": ring_z1,
                "pi": {"x": px, "y": py, "z": pi_z, "ang": pang}, "pi_holes": holes_w,
                "usbc": {"ang": ua, "z": usbc_zc, "w": usbc_w, "h": usbc_h},
                "jack": {"ang": ja, "z": jk_zc, "d": jk["hole_d"]},
                "switch": {"ang": sa, "z": sw_zc, "cut_w": sw["cut_w"], "cut_h": sw["cut_h"],
                           "panel_t": min(C["base_wall"], sw["max_panel_t"])},
                "vents_low": vents_low, "vent_low_z": low_vz or 0, "vents_high": vents_high, "vent_high_z": high_vz,
                "lid_screw_angs": lid_screw_angs, "lid_screw_z": base_h - C["spigot_h"] / 2,
                "nut_recess": nut_recess, "below_lid": below_lid,
                "shifter_on": shifter[0],
                "boxes": {
                    "trigger": box_d(deck["trigger"]), "buck": box_d(deck["buck"]), "gauge": box_d(deck["gauge"]),
                    "latch": box_d(deck["latch"]),
                    "switch": box_d(swb), "jack": box_d(jkb), "shifter": box_d(shifter[1]),
                },
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


def solve_uwb(P, C, base_d):
    """Anchor-board orientation, the mast geometry and the wearable pod."""
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
    v = {
        "base_d": L["base_d"], "base_h": L["base_h"],
        "window_z": L["window_z"], "shelf_z": L["shelf_z"], "shelf_r": L["shelf_r"],
        "gap_ang": L["gap_ang"], "gap_d": L["gap_d"],
        "post_r": L["post_r"], "post_angs": L["post_angs"], "window_ribs": L["window_ribs"],
        "pi_holes": [list(h) for h in L["pi_holes"]], "pi_hole_d": P["pi"]["hole_d"] + 0.2,
        "usbc_ang": L["usbc"]["ang"], "usbc_z": L["usbc"]["z"], "usbc_w": L["usbc"]["w"], "usbc_h": L["usbc"]["h"],
        "jack_ang": L["jack"]["ang"], "jack_z": L["jack"]["z"], "jack_d": L["jack"]["d"],
        "switch_ang": L["switch"]["ang"], "switch_z": L["switch"]["z"],
        "switch_cut_w": L["switch"]["cut_w"], "switch_cut_h": L["switch"]["cut_h"],
        "switch_panel_t": L["switch"]["panel_t"],
        "vents_low": L["vents_low"], "vent_low_z": L["vent_low_z"],
        "vents_high": L["vents_high"], "vent_high_z": L["vent_high_z"],
        "lid_screw_angs": L["lid_screw_angs"], "lid_screw_z": L["lid_screw_z"],
        "lid_nut_recess": L["nut_recess"], "ptz_nut_af": P["ptz"]["nut_af"],
        "ptz_slot_min": L["ptz_slot_min"], "ptz_slot_max": L["ptz_slot_max"],
        "risers": L["risers"],
        "insert_od": P["tripod_insert"]["od"], "insert_l": P["tripod_insert"]["l"],
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
    # the battery tray, strapped to the centre column a little below the head (guide only)
    keep["tray_z"] = -(C["tray_wall"] + P["power_bank"]["h"]) - 20
    keep["lid_z"] = L["base_h"]
    keep["lid_top"] = L["base_h"] + C["lid_t"]
    keep["tilt_z"] = L["base_h"] + C["lid_t"] + 49     # Arducam base: tilt axis 49 mm above the lid top
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
        os.path.join(ROOT, build, "docs", "setup", "assembly", "layout.js"):
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
    h.update(open(PARTS_FILE, "rb").read())
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


def scene(build, P, C, L):
    """Every bought part and every printed obstacle inside the enclosure."""
    R_in, FZ = L["R_in"], L["floor_z"]
    objs = [box_from(L["boxes"][k]) for k in ("trigger", "buck", "gauge", "latch", "switch", "jack", "shifter")]
    objs += [box_from(b) for b in L["pi_boxes"]]
    ring = P["led_ring"]
    objs.append(Cyl("LED ring", 0, 0, ring["od"] / 2, L["ring_z0"], L["ring_z1"]))
    printed = [Cyl("tripod boss", 0, 0, C["tripod_boss_d"] / 2, 0, C["tripod_boss_h"])]
    printed += [Cyl(f"shelf post {i + 1}", *polar(L["post_r"], a), C["post_d"] / 2, FZ, L["shelf_z"])
                for i, a in enumerate(L["post_angs"])]
    printed.append(Cyl("shelf", 0, 0, L["shelf_r"], L["shelf_z"], L["shelf_top"]))
    printed += [Box("riser", x, y, 6, 6, a, FZ, FZ + h) for x, y, a, h in L.get("risers", [])]
    base_h = L["base_h"]
    printed += [Box("lid spigot pad", *polar(R_in - C["clr"] - C["lid_screw_pad"] / 2, a), C["lid_screw_pad"], 10, a,
                    base_h - C["spigot_h"], base_h) for a in L["lid_screw_angs"]]
    r_b = P["ptz"]["bolt_spacing"] / 2
    nut_r = P["ptz"]["nut_af"] / math.sqrt(3) + 0.5
    printed += [Cyl("PTZ nut", *polar(r_b, a), nut_r, base_h - L["below_lid"], base_h) for a in (0, 90, 180, 270)]
    printed.append(Cyl("ribbon slack", 0, 0, C["ptz_cable_d"] / 2 + 10, base_h - C["ribbon_slack_h"] + 1, base_h))
    standoffs = [Cyl("Pi standoff", x, y, 2.9, L["shelf_top"], L["pi"]["z"]) for x, y in L["pi_holes"]]
    heads = [Cyl("shelf screw head", *polar(L["post_r"], a), 3.2, L["shelf_top"], L["shelf_top"] + 3) for a in L["post_angs"]]
    return objs, printed, standoffs, heads


def audit(build, P, C, L, stl_dir=None) -> Audit:
    A = Audit(build)
    uwb = build == "with_uwb"
    R_in, R_out, FZ = L["R_in"], L["base_d"] / 2, L["floor_z"]
    objs, printed, standoffs, heads = scene(build, P, C, L)
    through_wall = {"PD trigger", "rocker switch", "barrel jack"}

    # 1. inside the enclosure
    bad = [f"{o.name} reaches r={o.rmax():.1f}" for o in objs
           if o.name not in through_wall and o.name != "Pi USB-C plug" and o.rmax() > R_in - 0.01]
    bad += [f"{o.name} reaches r={o.rmax():.1f}" for o in objs if o.name == "Pi USB-C plug" and o.rmax() > R_in - 0.5]
    A.check(not bad, "Every bought part is inside the enclosure wall",
            "; ".join(bad) or f"inner radius {R_in:.1f} mm; furthest part at r = "
            f"{max(o.rmax() for o in objs if o.name not in through_wall):.1f} mm")
    tall = [o for o in objs + standoffs]
    over = [f"{o.name} top at z={o.z1:.1f}" for o in tall if o.z1 > L["base_h"] - 0.01]
    A.check(not over, "Everything is below the lid", "; ".join(over) or f"lid underside at z = {L['base_h']} mm")

    # 2. no two parts overlap, and none hits a printed feature
    allp = objs + printed + standoffs + heads
    clashes = []
    for a, b in itertools.combinations(allp, 2):
        names = {a.name, b.name}
        if names <= {"shelf", "LED ring"} or ("shelf" in names and ("post" in a.name + b.name)):
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
    A.check(not clashes, "No two parts overlap, and none hits a post, the boss, the shelf or the lid",
            "; ".join(sorted(set(clashes))) or f"{len(allp)} envelopes checked pairwise")

    # 3. light path
    deck_names = ["PD trigger", "buck converter", "battery gauge", "power latch", "rocker switch", "barrel jack"]
    deck_top = max(o.z1 for o in objs if o.name in deck_names or (o.name == "level shifter" and L["shifter_on"] == "deck"))
    A.check(deck_top <= L["window_z"] + EPS, "The power boards sit below the LED window",
            f"tallest at z = {deck_top:.1f}; window {L['window_z']:.1f}–{L['window_z'] + C['led_window_h']:.1f}")
    A.check(L["ring_z0"] >= L["window_z"] - EPS and L["ring_z1"] <= L["shelf_z"] + EPS,
            "The LED ring hangs under the shelf, inside the window band",
            f"ring z = {L['ring_z0']:.1f}–{L['ring_z1']:.1f}", ["led_ring"])

    # 4. wall openings
    feats = [("USB-C inlet", L["usbc"]["ang"], L["usbc"]["z"] + L["usbc"]["h"] / 2, max(L["usbc"]["w"], P["pd_trigger"]["w"]) / 2),
             ("rocker switch", L["switch"]["ang"], L["switch"]["z"] + P["switch"]["body_h"] / 2, P["switch"]["body_w"] / 2),
             ("barrel jack", L["jack"]["ang"], L["jack"]["z"] + P["jack"]["body_d"] / 2, P["jack"]["body_d"] / 2)]
    ledge_bot = L["window_z"] - C["diffuser_lip"] - C["ledge_h"] - C["diffuser_t"]
    probs = []
    for name, a, ztop, half in feats:
        if ztop > ledge_bot - 0.5:
            probs.append(f"{name} would be covered by the diffuser band")
        if uwb:
            for b in (90, 270, 180):
                if angdiff(a, b) < math.degrees((C["arm_w"] / 2 + 2 + half) / R_out):
                    probs.append(f"{name} at {a}° is behind the {'mast foot' if b == 180 else 'anchor arm'} at {b}°")
    for (n1, a1, _, h1), (n2, a2, _, h2) in itertools.combinations(feats, 2):
        if angdiff(a1, a2) < math.degrees((h1 + h2 + 2) / R_out):
            probs.append(f"{n1} and {n2} overlap on the wall")
    A.check(not probs, "Wall openings are reachable and clear of each other",
            "; ".join(probs) or ", ".join(f"{n} at {a}°" for n, a, _, _ in feats), ["pd_trigger", "switch", "jack"])
    sw = P["switch"]
    A.check(L["switch"]["panel_t"] <= sw["max_panel_t"] + EPS, "The rocker switch's clips can grip the wall",
            f"wall {C['base_wall']} mm, thinned to {L['switch']['panel_t']} mm round the cut-out (clips take ≤ {sw['max_panel_t']})", ["switch"])
    A.check(C["base_wall"] <= P["jack"]["max_panel_t"] + EPS, "The barrel jack's nut reaches through the wall",
            f"wall {C['base_wall']} mm, jack takes ≤ {P['jack']['max_panel_t']}", ["jack"])
    A.check(L["usbc"]["w"] >= P["pd_trigger"]["plug_w"] and L["usbc"]["h"] >= P["pd_trigger"]["plug_h"],
            "The bank's USB-C plug fits through its wall opening",
            f"opening {L['usbc']['w']}×{L['usbc']['h']} mm for a {P['pd_trigger']['plug_w']}×{P['pd_trigger']['plug_h']} plug", ["pd_trigger"])

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

    # 6. tripod
    ins = P["tripod_insert"]
    A.check(ins["l"] <= C["tripod_boss_h"] + EPS, "The tripod insert fits the floor boss",
            f"insert {ins['l']} mm long, boss {C['tripod_boss_h']} mm; bore cut to {ins['od']} mm", ["tripod_insert"])

    # 7. camera mount
    ptz = P["ptz"]
    A.check(L["ptz_slot_min"] <= ptz["bolt_spacing"] <= L["ptz_slot_max"], "The Arducam base's bolts land in the lid slots",
            f"bolt spacing {ptz['bolt_spacing']} mm; slots take {L['ptz_slot_min']:g}–{L['ptz_slot_max']:g}"
            + ("" if (L["ptz_slot_min"], L["ptz_slot_max"]) == (C["ptz_bolt_min"], C["ptz_bolt_max"]) else " (stretched to fit your base)"), ["ptz"])
    A.check(L["nut_recess"] <= C["lid_t"] - 2, "The PTZ bolts are long enough to take a nut",
            f"M3 × {ptz['bolt_l']} through {ptz['plate_t']} mm plate + {C['lid_t']} mm lid"
            + (f"; lid relieved {L['nut_recess']:.1f} mm under each slot so the nut engages" if L["nut_recess"] else ""), ["ptz"])
    A.check(ptz["plate_l"] * math.sqrt(2) / 2 <= R_out, "The Arducam base plate sits on the lid",
            f"plate diagonal {ptz['plate_l'] * math.sqrt(2):.0f} mm on a Ø{L['base_d']} lid", ["ptz"])
    A.check(C["ptz_cable_d"] >= ptz["cable_bundle_d"] + 4, "The ribbon and servo leads fit through the lid",
            f"opening Ø{C['ptz_cable_d']}, bundle Ø{ptz['cable_bundle_d']}", ["ptz"])

    # 8. battery tray
    bk = P["power_bank"]
    tray = (bk["l"] + 2 * C["tray_wall"], bk["w"] + 2 * C["tray_wall"])
    A.check(max(tray) <= PRINT_LIMIT, "The battery tray (sized to the bank) prints in one piece",
            f"tray {tray[0]:.0f} × {tray[1]:.0f} mm", ["power_bank"])

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
        e_ok &= not (angdiff(e["ang"], 180) < math.degrees((C["arm_w"] / 2 + 2 + e["w"] / 2) / R_out)
                     and e["z"] - e["h"] / 2 < C["arm_boss_z"] + C["mast_foot_h"])
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

    assumed = [f"{v.get('name', k)} (item {v.get('bom', '?')})" for k, v in P.items() if not v.get("measured")]
    if assumed:
        A.note("Sizes still assumed, not measured", ", ".join(assumed))
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
    for script in (os.path.join(ROOT, build, "docs", "setup", "assembly", "build_models.py"),
                   os.path.join(ROOT, build, "cad", "render_previews.py"),
                   os.path.join(ROOT, build, "docs", "setup", "assembly", "render_steps.py")):
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
    # through-wall parts legitimately pass through their openings
    envelopes = [o for o in objs if o.name not in ("rocker switch", "barrel jack", "PD trigger", "Pi USB-C plug")]
    parts = {
        "base_housing": f'import("{cad}/stl/base_housing.stl");',
        "shelf": f'translate([0,0,{L["shelf_z"]}]) import("{cad}/stl/shelf.stl");',
        "lid": f'translate([0,0,{L["base_h"]}]) import("{cad}/stl/lid.stl");',
        "led_diffuser_ring": f'translate([0,0,{L["window_z"] - C["diffuser_lip"]}]) import("{cad}/stl/led_diffuser_ring.stl");',
    }
    hits = []
    with tempfile.TemporaryDirectory() as td:
        for name, body in parts.items():
            src = os.path.join(td, f"{name}.scad")
            with open(src, "w") as f:
                f.write("intersection(){ union(){ " + body + " }\n union(){\n" + "\n".join(solid(o) for o in envelopes) + "\n} }\n")
            out = os.path.join(td, f"{name}.stl")
            r = subprocess.run(["openscad", "-o", out, src], capture_output=True, text=True)
            if "Current top level object is empty" in r.stderr or not os.path.exists(out) or os.path.getsize(out) < 200:
                continue
            # find which envelope(s)
            for o in envelopes:
                with open(src, "w") as f:
                    f.write("intersection(){ union(){ " + body + " }\n" + solid(o) + " }\n")
                r = subprocess.run(["openscad", "-o", out, src], capture_output=True, text=True)
                if "empty" not in r.stderr and os.path.exists(out) and os.path.getsize(out) > 200:
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
            lines += [f"Enclosure Ø{L['base_d']} × {L['base_h']} mm (floor to lid). "
                      f"Power boards on the floor up to z = {L['power_top']:.0f}; LED window "
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
                  f"inlet {L['usbc']['ang']}°, jack {L['jack']['ang']}°, switch {L['switch']['ang']}°"
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
