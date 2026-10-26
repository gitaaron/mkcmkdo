#!/usr/bin/env python3
"""Render a preview PNG for every STL in cad/stl/ → docs/without_uwb/images/parts/.

Usage:  python3 cad/render_previews.py     (run cad/render_all.sh first)
Requires: pip install numpy-stl matplotlib
"""
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from stl import mesh

HERE = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(HERE, "stl")
OUT = os.path.join(HERE, "..", "..", "docs", "without_uwb", "images", "parts")
os.makedirs(OUT, exist_ok=True)

for f in sorted(os.listdir(STL_DIR)):
    if not f.endswith(".stl"):
        continue
    name = f[:-4]
    m = mesh.Mesh.from_file(os.path.join(STL_DIR, f))
    tris = m.vectors
    if len(tris) > 15000:  # decimate for speed; preview only
        idx = np.random.default_rng(1).choice(len(tris), 15000, replace=False)
        tris = tris[idx]

    fig = plt.figure(figsize=(3.2, 2.6), dpi=100)
    ax = fig.add_subplot(111, projection="3d")
    ax.add_collection3d(
        Poly3DCollection(tris, facecolor="#8fa8d8", edgecolor="#33425e", linewidth=0.08)
    )
    pts = m.vectors.reshape(-1, 3)
    c = (pts.min(0) + pts.max(0)) / 2
    r = (pts.max(0) - pts.min(0)).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(c[2] - r, c[2] + r)
    ax.axis("off")
    ax.view_init(elev=35, azim=-60)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(os.path.join(OUT, f"{name}.png"), facecolor="white")
    plt.close(fig)
    print("wrote", f"{name}.png")
