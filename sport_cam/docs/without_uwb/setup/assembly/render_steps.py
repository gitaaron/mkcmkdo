#!/usr/bin/env python3
"""Render the offline fallback illustrations for the assembly guide.

index.html normally renders the assembly live in WebGL (three.js from a CDN
+ the meshes packed in models.js). When there is no internet or no WebGL it
falls back to the turntable PNGs this script produces: each step rendered
from the *real* STLs in cad/stl/ at 8 azimuths, so the guide still works
fully offline (drag to spin between views).

    python3 docs/setup/assembly/render_steps.py            # all steps
    python3 docs/setup/assembly/render_steps.py battery    # one step (fast iteration)

Only printed parts appear here (boards, the Arducam base and the bank are
primitives in the live viewer); callouts mark where the hardware goes.

Requires: numpy-stl, matplotlib
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from stl import mesh as stlmesh

HERE = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(HERE, "..", "..", "..", "..", "without_uwb", "cad", "stl")
OUT = os.path.join(HERE, "renders")
os.makedirs(OUT, exist_ok=True)

ANGLES = [-150, -120, -90, -60, -30, 0, 30, 60]   # turntable azimuths; the page steps through these
DPI = 110
FIGSIZE = (6.4, 4.4)
LIGHT = np.array([0.42, -0.72, 0.55])
LIGHT = LIGHT / np.linalg.norm(LIGHT)

BODY = "#c3ccdb"       # already-assembled parts
NEW = "#2f6fed"        # the part going on in this step
ACCENT = "#1f9d55"

# Assembly coordinates (mm) — OpenSCAD space, from the layout cad/fit.py
# solved (../../../../without_uwb/cad/layout.json), the same numbers the live guide uses.
import json  # noqa: E402
LY = json.load(open(os.path.join(HERE, "..", "..", "..", "..", "without_uwb", "cad", "layout.json")))
LID_Z = LY["lid_z"]
LID_TOP = LY["lid_top"]
SHELF_Z = LY["shelf_z"]
BAND_Z = LY["window_z"] - LY["design"]["diffuser_lip"]


def rot_z(deg):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


def rot_x(deg):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)


# name -> (stl file, rotation, translation)
PARTS = {
    "shell":    ("base_housing.stl",      None,        (0, 0, 0)),
    "diffuser": ("led_diffuser_ring.stl", None,        (0, 0, BAND_Z)),
    "shelf":    ("shelf.stl",             None,        (0, 0, SHELF_Z)),
    "lid":      ("lid.stl",               None,        (0, 0, LID_Z)),
    "tray":     ("battery_tray.stl",      None,        (-77.4, -38.4, -20)),
}
_cache: dict[str, np.ndarray] = {}


def cylinder(cx: float, cy: float, r: float, z0: float, z1: float, n: int = 20) -> np.ndarray:
    """Side wall and caps of a vertical cylinder, as triangles."""
    a = np.linspace(0, 2 * math.pi, n + 1)
    ring = np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], axis=1)
    tris = []
    for (x0, y0), (x1, y1) in zip(ring[:-1], ring[1:]):
        tris += [[(x0, y0, z0), (x1, y1, z0), (x1, y1, z1)], [(x0, y0, z0), (x1, y1, z1), (x0, y0, z1)],
                 [(cx, cy, z1), (x0, y0, z1), (x1, y1, z1)], [(cx, cy, z0), (x1, y1, z0), (x0, y0, z0)]]
    return np.array(tris, dtype=float)


PRIMS: dict = {}   # bought parts drawn anyway (none in the camera-only build)


def load(name: str) -> np.ndarray:
    if name in _cache:
        return _cache[name]
    if name in PRIMS:
        _cache[name] = PRIMS[name]()
        return _cache[name]
    fname, rot, trans = PARTS[name]
    tris = stlmesh.Mesh.from_file(os.path.join(STL_DIR, fname)).vectors.astype(float)
    if rot is not None:
        tris = tris @ rot.T
    tris = tris + np.array(trans, dtype=float)
    _cache[name] = tris
    return tris


def shade(tris: np.ndarray, base_hex: str) -> np.ndarray:
    base = np.array(matplotlib.colors.to_rgb(base_hex))
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    norms = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, norms, out=np.zeros_like(n), where=norms > 1e-9)
    lam = np.abs(n @ LIGHT)
    intensity = (0.42 + 0.58 * lam)[:, None]
    rgb = np.clip(base[None, :] * intensity, 0, 1)
    return np.concatenate([rgb, np.ones((len(rgb), 1))], axis=1)


# ---------------------------------------------------------------------------
# Scenes. `add` entries are (part, explode-offset). ids match the `render:`
# field of the steps in index.html.
# ---------------------------------------------------------------------------
UP = (0, 0, 0)
ALL = ["tray", "shell", "shelf", "diffuser", "lid"]
SCENES = [
    dict(id="prep", title="Printed parts overview", show=[],
         add=[("shell", UP), ("shelf", (0, 0, 60)), ("diffuser", (0, 0, 95)), ("lid", (0, 0, 150)),
              ("tray", (0, 0, -90))],
         arrows=False),
    dict(id="tripod-insert", title="Enclosure", show=[], add=[("shell", UP)], elev=38,
         marks=[((0, 0, 8), "3/8-16 insert (1/4-20 via bushing)")]),
    dict(id="power", title="Power boards on the floor", show=[], add=[("shell", UP)], elev=44,
         marks=[((LY["boxes"]["trigger"]["cx"], LY["boxes"]["trigger"]["cy"], 8), "PD trigger at the USB-C inlet"),
                ((LY["boxes"]["buck"]["cx"], LY["boxes"]["buck"]["cy"], 20), "buck"),
                ((LY["boxes"]["gauge"]["cx"], LY["boxes"]["gauge"]["cy"], 14), "gauge"),
                ((LY["boxes"]["latch"]["cx"], LY["boxes"]["latch"]["cy"], 14), "power latch")]),
    dict(id="led", title="LED ring under the shelf, diffuser band", show=["shell"],
         add=[("shelf", (0, 0, 60)), ("diffuser", (0, 0, 80))],
         marks=[((0, 0, SHELF_Z - 2), "ring under the shelf"), ((0, -LY["base_d"] / 2, BAND_Z + 8), "band over the window")]),
    dict(id="pi", title="Pi on the shelf, shelf on the posts", show=["shell", "diffuser"],
         add=[("shelf", (0, 0, 70))],
         marks=[((LY["pi"]["x"], LY["pi"]["y"], LY["pi"]["z"]), "Raspberry Pi 4"),
                ((LY["post_r"] * math.cos(math.radians(LY["post_angs"][0])), LY["post_r"] * math.sin(math.radians(LY["post_angs"][0])), SHELF_Z), "post")]),
    dict(id="lid-ptz", title="Arducam base onto the lid", show=[], add=[("lid", UP)], elev=34,
         marks=[((0, 0, LID_TOP), "slots take 30-72 mm bolt spacing")]),
    dict(id="lid-on", title="Lid onto the enclosure", show=["shell", "diffuser", "shelf"],
         add=[("lid", (0, 0, 95))]),
    dict(id="battery", title="Battery tray", show=["shell", "shelf", "diffuser", "lid"],
         add=[("tray", (0, 0, -70))],
         marks=[((0, 0, -14), "92 Wh bank, slung low")]),
    dict(id="complete", title="Completed assembly", show=ALL, add=[]),
]


def scene_bounds(scene):
    pts = [load(n).reshape(-1, 3) for n in scene["show"]]
    pts += [load(n).reshape(-1, 3) + np.array(off, dtype=float) for n, off in scene["add"]]
    pts += [np.array([p], dtype=float) for p, _ in scene.get("marks", [])]
    allpts = np.vstack(pts)
    centre = (allpts.min(0) + allpts.max(0)) / 2
    extent = np.maximum(allpts.max(0) - allpts.min(0), 1.0) * 0.52
    return centre, extent


def render(scene, azim: float, path: str) -> None:
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_proj_type("ortho")

    for name in scene["show"]:
        tris = load(name)
        ax.add_collection3d(Poly3DCollection(tris, facecolors=shade(tris, BODY), edgecolor="none", shade=False))
    for name, off in scene["add"]:
        offset = np.array(off, dtype=float)
        tris = load(name) + offset
        ax.add_collection3d(Poly3DCollection(tris, facecolors=shade(tris, NEW), edgecolor="none", shade=False))
        if offset.any() and scene.get("arrows", True):
            seat = load(name).reshape(-1, 3).mean(0)
            start = seat + offset * 0.8
            ax.quiver(*start, *(-offset * 0.6), color=ACCENT, linewidth=2.6, arrow_length_ratio=0.3, zorder=20)

    centre, extent = scene_bounds(scene)
    for pos, label in scene.get("marks", []):
        p3 = np.array(pos, dtype=float)
        out = p3[:2] - centre[:2]
        out = np.array([1.0, -1.0]) if np.linalg.norm(out) < 1e-6 else out / np.linalg.norm(out)
        lab = p3 + np.array([out[0] * 90, out[1] * 90, 55.0])
        ax.plot(*zip(p3, lab), color=ACCENT, linewidth=1.1, zorder=19)
        ax.scatter(*p3, color=ACCENT, s=30, depthshade=False, zorder=20)
        ax.text(lab[0], lab[1], lab[2] + 6, label, fontsize=7.5, zorder=21, color="#15502e", ha="center",
                bbox=dict(fc="white", ec=ACCENT, lw=0.6, pad=1.4, boxstyle="round,pad=0.25"))

    ax.set_xlim(centre[0] - extent[0], centre[0] + extent[0])
    ax.set_ylim(centre[1] - extent[1], centre[1] + extent[1])
    ax.set_zlim(centre[2] - extent[2], centre[2] + extent[2])
    try:
        ax.set_box_aspect(tuple(extent))
    except (AttributeError, TypeError):
        pass
    ax.view_init(elev=scene.get("elev", 26), azim=azim)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(path, facecolor="#f3f5f9", transparent=False)
    plt.close(fig)


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for scene in SCENES:
        if only and scene["id"] != only:
            continue
        for i, az in enumerate(ANGLES):
            render(scene, az, os.path.join(OUT, f"{scene['id']}_{i}.png"))
        print(f"wrote {scene['id']}_[0-{len(ANGLES) - 1}].png  ({scene['title']})", flush=True)


if __name__ == "__main__":
    main()
