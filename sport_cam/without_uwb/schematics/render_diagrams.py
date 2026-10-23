#!/usr/bin/env python3
"""Render system-design illustrations for SportCam to docs/images/*.png.

Usage:  python3 schematics/render_diagrams.py
"""
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle, Wedge, Polygon

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "images")
os.makedirs(OUT, exist_ok=True)

INK = "#1a2233"
BLUE = "#2f6fed"
GREEN = "#1f9d55"
RED = "#d64541"
GREY = "#8a93a6"
SLATE = "#4a5d85"   # sleep
BGBOX = "#f4f6fb"


def box(ax, x, y, w, h, title, lines=(), fc=BGBOX, ec=INK, title_fs=11, fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06",
                                fc=fc, ec=ec, lw=1.4))
    ax.text(x + w / 2, y + h - 0.32, title, ha="center", va="top",
            fontsize=title_fs, fontweight="bold", color=INK)
    for i, ln in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.75 - i * 0.34, ln, ha="center", va="top",
                fontsize=fs, color=INK)


def arrow(ax, p1, p2, label="", color=INK, style="-|>", ls="-", lw=1.6, lofs=(0, 0.14), fs=8.5):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=14,
                                 color=color, lw=lw, linestyle=ls, shrinkA=4, shrinkB=4))
    if label:
        mx, my = (p1[0] + p2[0]) / 2 + lofs[0], (p1[1] + p2[1]) / 2 + lofs[1]
        ax.text(mx, my, label, ha="center", va="bottom", fontsize=fs, color=color,
                bbox=dict(fc="white", ec="none", pad=1))


def new_fig(w, h, title):
    fig, ax = plt.subplots(figsize=(w, h), dpi=140)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    ax.set_title(title, fontsize=14, fontweight="bold", color=INK, pad=14)
    return fig, ax


def save(fig, name, dpi=None):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name), bbox_inches="tight", facecolor="white",
                dpi=dpi or fig.dpi)
    plt.close(fig)
    print("wrote", name)


# ----------------------------------------------------------------------------
# 0. Intro scene — camera sweeping for, then following, a climber
# ----------------------------------------------------------------------------
def intro_scene():
    fig, ax = new_fig(12, 8.2, "SportCam tracking a climber")

    # gym floor + mats
    ax.add_patch(Rectangle((0, 0), 12, 0.5, fc="#2a3850", ec="none"))
    ax.add_patch(Rectangle((0, 0.5), 4.4, 0.35, fc="#3d4f74", ec="none"))
    ax.text(2.1, 0.16, "mats", fontsize=8, color="#8fa0c0")

    # climbing wall (slight overhang)
    wall = Polygon([(0.4, 0.5), (1.5, 8.0), (0, 8.0), (0, 0.5)], fc="#e9edf5", ec=INK, lw=1.5)
    ax.add_patch(wall)
    rng = [(0.55, 1.3, "#d64541"), (0.95, 2.4, "#f2a93b"), (0.7, 3.4, "#1f9d55"),
           (1.15, 4.3, "#2f6fed"), (0.9, 5.5, "#d64541"), (1.35, 6.3, "#8e5bd6"),
           (1.05, 7.2, "#f2a93b"), (1.5, 7.6, "#1f9d55"), (0.55, 2.0, "#8e5bd6"),
           (1.3, 5.0, "#f2a93b")]
    for x, y, c in rng:
        ax.add_patch(Circle((x, y), 0.11, fc=c, ec="none"))

    # climber (mid-wall, reaching for a hold)
    hx, hy = 1.75, 5.9                     # hip position
    ax.plot([hx, hx + 0.28], [hy, hy + 0.85], color=INK, lw=3.5)              # torso (leaning into wall)
    ax.add_patch(Circle((hx + 0.42, hy + 1.1), 0.22, fc="#f5d0b5", ec=INK, lw=1.5))  # head
    ax.plot([hx + 0.2, 1.32, 1.35], [hy + 0.75, hy + 1.15, 6.28], color=INK, lw=3)   # reaching arm → purple hold
    ax.plot([hx + 0.25, 1.42, 1.32], [hy + 0.6, hy + 0.3, 5.02], color=INK, lw=3)    # lower arm → orange hold
    ax.plot([hx, 1.05, 0.92], [hy, hy - 0.7, 5.52], color=INK, lw=3)                 # leg → red hold
    ax.plot([hx, 1.55, 1.32], [hy - 0.05, hy - 1.0, 5.0], color=INK, lw=3)           # trailing leg
    # tripod + SportCam, floor right, aimed up-left at the climber
    tx, ty = 8.6, 0.5                      # tripod centre at floor
    for dx in (-1.1, 1.1):
        ax.plot([tx, tx + dx], [ty + 1.6, ty], color=INK, lw=3)
    ax.plot([tx, tx], [ty + 1.6, ty], color=GREY, lw=3)
    # base with LED ring (green = tracking)
    ax.add_patch(Rectangle((tx - 0.55, ty + 1.6), 1.1, 0.55, fc=BGBOX, ec=INK, lw=1.5))
    ax.add_patch(Rectangle((tx - 0.55, ty + 1.72), 1.1, 0.14, fc=GREEN, ec="none"))
    ax.annotate("LED ring: tracking", xy=(tx - 0.55, ty + 1.79), xytext=(5.4, 0.9),
                fontsize=9, color=GREEN, arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.2))
    # rotating head, tilted toward climber
    ang = math.degrees(math.atan2(hy - (ty + 2.5), hx - tx))   # ≈ toward climber
    ax.add_patch(Rectangle((tx - 0.45, ty + 2.15), 0.9, 0.28, fc=BGBOX, ec=INK, lw=1.5))
    # camera body + lens on the head
    import matplotlib.transforms as mtransforms
    cam_x, cam_y = tx, ty + 2.62
    tr = mtransforms.Affine2D().rotate_deg_around(cam_x, cam_y, ang - 180) + ax.transData
    ax.add_patch(Rectangle((cam_x - 0.42, cam_y - 0.2), 0.84, 0.4, fc="#dde3ef", ec=INK,
                           lw=1.5, transform=tr))
    ax.add_patch(Rectangle((cam_x - 0.72, cam_y - 0.13), 0.3, 0.26, fc=INK, ec=INK, transform=tr))
    ax.text(tx, ty + 3.35, "SportCam head:\npan · tilt · zoom", fontsize=9, color=INK, ha="center")

    # field-of-view cone from lens to climber
    fov = Polygon([(cam_x - 0.55, cam_y + 0.1), (hx + 0.9, hy + 1.7), (hx + 0.4, hy - 1.4)],
                  closed=True, fc="#2f6fed", ec="none", alpha=0.10)
    ax.add_patch(fov)
    ax.annotate("", xy=(hx + 0.75, hy + 0.35), xytext=(cam_x - 0.6, cam_y + 0.05),
                arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=1.6, ls="-"))
    ax.text(5.1, 4.35, "camera follows,\nzoom holds framing", fontsize=9, color=BLUE, rotation=24)

    # phone in the corner showing the app
    px, py = 10.6, 4.6
    ax.add_patch(FancyBboxPatch((px, py), 1.1, 2.1, boxstyle="round,pad=0.05",
                                fc="white", ec=INK, lw=1.5))
    ax.add_patch(Rectangle((px + 0.08, py + 0.5), 0.94, 1.45, fc="#0d1420", ec="none"))
    ax.add_patch(Circle((px + 0.83, py + 1.75), 0.08, fc=GREEN, ec="white", lw=1))
    ax.plot([px + 0.45, px + 0.55], [py + 1.0, py + 1.25], color="#cbd6ea", lw=1.5)
    ax.add_patch(Circle((px + 0.55, py + 1.33), 0.05, fc="none", ec="#cbd6ea", lw=1.2))
    for i, c in enumerate(["#eef1f7", GREEN]):
        ax.add_patch(Rectangle((px + 0.1 + i * 0.47, py + 0.12), 0.43, 0.3, fc=c, ec=INK, lw=0.6))
    ax.text(px + 0.55, py - 0.25, "live app", fontsize=8.5, color=INK, ha="center")

    save(fig, "intro-scene.png")


# ----------------------------------------------------------------------------
# 1. System architecture
# ----------------------------------------------------------------------------
def system_architecture():
    fig, ax = new_fig(12, 7.6, "SportCam — system architecture")

    box(ax, 4.5, 5.4, 3.2, 1.9, "Firebase (cloud)",
        ["api function  /api/call/*", "Firestore: state + preview",
         "Storage: recordings", "Hosting: Vue web app"])
    box(ax, 9.2, 5.4, 2.5, 1.9, "Phone / laptop app",
        ["Flutter (phone) · Vue (web)", "live video",
         "link badge + status ring"])
    box(ax, 0.4, 2.2, 3.6, 2.6, "Camera unit (one board)",
        ["Raspberry Pi 4 (HW H.264)", "Arducam PTZ ctrl (I2C 0x0C)",
         "pan + tilt + zoom + focus", "HOG person detector (vision)",
         "LED ring (SPI) · INA260 gauge"])
    box(ax, 4.6, 0.3, 3.2, 1.8, "Battery", ["USB-C PD bank 92 Wh",
                                            "PD trigger 12 V → buck 5 V",
                                            "8.4 h tracking + recording"], fc="#fdf6e8")
    arrow(ax, (4.0, 4.3), (4.5, 5.6), "internet: state,\npreview, clips", color=BLUE, lofs=(1.05, -0.35))
    arrow(ax, (7.7, 6.4), (9.2, 6.4), "HTTPS + Firestore", color=BLUE)
    ax.annotate("", xy=(4.05, 4.5), xytext=(10.4, 5.35),
                arrowprops=dict(arrowstyle="<|-|>", color=GREEN, lw=2.2,
                                connectionstyle="arc3,rad=-0.38"))
    ax.text(8.15, 4.85, "DIRECT (same Wi-Fi): mDNS discovery →\nfull-rate video + control, no internet",
            fontsize=9, color=GREEN, ha="center", fontweight="bold",
            bbox=dict(fc="white", ec=GREEN, boxstyle="round,pad=0.28", lw=1.1))
    arrow(ax, (4.6, 1.2), (4.0, 2.4), "5 V", color=RED, lofs=(-0.35, -0.1))
    ax.text(2.2, 5.75, "the whole control loop closes\non the Pi, by vision alone —\nno radios, no second\nmicrocontroller, no slip ring",
            fontsize=8.5, color=GREY, ha="center")
    save(fig, "system-architecture.png")


# ----------------------------------------------------------------------------
# 2. Mechanical layout (side view)
# ----------------------------------------------------------------------------
def mechanical_layout():
    fig, ax = new_fig(9.5, 9, "Camera unit assembly (side view)")
    cx = 4.4

    # tripod legs
    for dx in (-2.6, 2.6):
        ax.plot([cx, cx + dx], [1.9, 0.2], color=INK, lw=3)
    ax.plot([cx, cx], [1.9, 0.2], color=GREY, lw=3)
    ax.text(cx + 2.75, 0.3, "any standard tripod\n(3/8-16, or 1/4-20\nvia bushing)", fontsize=9, color=GREY)

    # battery tray, slung low
    ax.add_patch(Rectangle((cx - 1.7, 1.9), 3.4, 0.75, fc="#fdf6e8", ec=INK, lw=1.4))
    ax.text(cx, 2.27, "BATTERY TRAY — 92 Wh USB-C bank", ha="center",
            fontsize=8.5, color=INK)
    ax.text(cx - 2.6, 2.25, "heaviest item\nlowest", fontsize=8, color=GREY, ha="center")

    # enclosure
    ax.add_patch(Rectangle((cx - 1.5, 2.75), 3.0, 1.9, fc=BGBOX, ec=INK, lw=1.5))
    ax.text(cx, 4.2, "ENCLOSURE (static)", ha="center", fontsize=10,
            fontweight="bold", color=INK)
    ax.text(cx, 3.82, "Raspberry Pi 4", ha="center", fontsize=8.5, color=INK)
    ax.text(cx, 3.5, "PD trigger · buck 5 V · INA226", ha="center", fontsize=8.5, color=INK)
    ax.add_patch(Rectangle((cx - 1.62, 3.0), 0.12, 0.9, fc=GREEN, ec="none"))
    ax.text(cx - 2.4, 3.45, "WS2812\nLED ring", fontsize=8.5, color=GREEN, ha="center")

    # lid
    ax.add_patch(Rectangle((cx - 1.5, 4.65), 3.0, 0.3, fc="#dde3ef", ec=INK, lw=1.5))
    ax.text(cx + 2.55, 4.78, "LID — carries the camera,\nslotted bolt pattern",
            fontsize=8.5, color=INK, ha="center")

    # PTZ base + camera
    ax.add_patch(Rectangle((cx - 0.75, 4.95), 1.5, 0.85, fc="#e8ecf5", ec=INK, lw=1.5))
    ax.text(cx, 5.38, "Arducam metal\npan-tilt base", ha="center", va="center",
            fontsize=8, color=INK)
    ax.add_patch(Circle((cx, 6.5), 0.52, fc="#cfd7e6", ec=INK, lw=1.5))
    ax.add_patch(Rectangle((cx + 0.35, 6.28), 0.75, 0.44, fc=INK, ec=INK))
    ax.text(cx - 3.0, 6.55, "IMX477 + motorized\nzoom lens", fontsize=8.5,
            color=INK, ha="center")

    # motion arcs
    ax.annotate("", xy=(cx + 1.5, 7.45), xytext=(cx - 1.5, 7.45),
                arrowprops=dict(arrowstyle="<|-|>", color=RED, lw=1.6,
                                connectionstyle="arc3,rad=0.3"))
    ax.text(cx, 7.95, "PAN ±80° (not continuous)", ha="center", fontsize=9,
            color=RED, fontweight="bold")
    ax.annotate("", xy=(cx + 1.9, 7.1), xytext=(cx + 1.9, 5.7),
                arrowprops=dict(arrowstyle="<|-|>", color=RED, lw=1.6,
                                connectionstyle="arc3,rad=0.35"))
    ax.text(cx + 2.9, 6.4, "TILT\n−45°…+85°", ha="center", fontsize=9, color=RED)

    ax.text(cx, 8.45, "No pan stage: no slip ring, no stepper, no lazy susan.",
            ha="center", fontsize=9, color=GREY, style="italic")
    save(fig, "mechanical-layout.png")


# ----------------------------------------------------------------------------
# 3. State machine
# ----------------------------------------------------------------------------
def state_machine():
    fig, ax = new_fig(16.5, 8.2, "Camera state machine · LED ring")
    ax.title.set_fontsize(22)
    y = 3.3
    R = 0.9

    def node(x, name, c, r=R, fs=15.2, yy=None):
        yy = y if yy is None else yy
        ax.add_patch(Circle((x, yy), r, fc="white", ec=c, lw=3, zorder=3))
        ax.text(x, yy, name, ha="center", va="center", fontsize=fs, fontweight="bold",
                color=c, zorder=4)

    def link(p1, p2, label="", rad=0.0, color=INK, ls="-", lofs=(0, 0), fs=13.6, ha="center", va="center"):
        ax.annotate("", xy=p2, xytext=p1, zorder=2,
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.5, ls=ls,
                                    connectionstyle=f"arc3,rad={rad}",
                                    shrinkA=0, shrinkB=0))
        if label:
            ax.text(lofs[0], lofs[1], label, ha=ha, va=va, fontsize=fs, color=color, zorder=5,
                    bbox=dict(fc="white", ec="none", pad=1.2))

    xs = dict(sleep=1.0, awake=3.75, search=7.6, found=11.0, rec=14.9)
    yp = 5.55                                   # "person in frame" row

    # initiate-tracking container: two sub-states
    ax.add_patch(FancyBboxPatch((6.15, 1.75), 6.1, 3.2, boxstyle="round,pad=0.08",
                                fc="#f2fbf5", ec=GREEN, lw=2, ls="--", zorder=1))
    ax.text(6.35, 4.67, "INITIATE RECORDING", fontsize=17.6, fontweight="bold", color=GREEN,
            ha="left", va="center")

    # awake container: two sub-states
    ax.add_patch(FancyBboxPatch((2.65, 2.2), 2.2, 4.75, boxstyle="round,pad=0.08",
                                fc="#f2f6ff", ec=BLUE, lw=2, ls="--", zorder=1))
    ax.text(2.8, 6.75, "AWAKE", fontsize=17.6, fontweight="bold", color=BLUE, ha="left", va="center")

    node(xs["sleep"], "SLEEP", SLATE, fs=14.4)
    node(xs["awake"], "no person\nin frame", BLUE, fs=12.8)
    node(xs["awake"], "person\nin frame", BLUE, fs=12.8, yy=yp)
    link((xs["awake"] - 0.25, y + R), (xs["awake"] - 0.25, yp - R), "")
    link((xs["awake"] + 0.25, yp - R), (xs["awake"] + 0.25, y + R), "")
    ax.text(xs["awake"] - 0.32, (y + yp) / 2, "seen", fontsize=12.8, ha="right", va="center", color=INK)
    ax.text(xs["awake"] + 0.32, (y + yp) / 2, "none\n4 s", fontsize=12.8, ha="left", va="center", color=INK)
    node(xs["search"], "SEARCH", GREEN, fs=14.4)
    node(xs["found"], "FOUND", GREEN, fs=14.4)
    node(xs["rec"], "RECORDING", RED, r=1.1, fs=13.6)

    # main path
    link((xs["sleep"] + R, y + 0.25), (xs["awake"] - R, y + 0.25), "wake\nup", lofs=(2.3, y + 0.75))
    link((xs["awake"] - R, y - 0.25), (xs["sleep"] + R, y - 0.25), "30 s, no\nsession or\nlive view", lofs=(2.3, y - 0.95), fs=12.8)
    # power on: Wi-Fi joined, straight to awake
    link((1.75, yp + 0.75), (2.57, yp + 0.75), "")
    ax.text(1.25, yp + 0.75, "power\non", fontsize=12.8, ha="center", va="center", color=INK)
    # record from sleep skips awake: over the top, into SEARCH
    xr, yr = xs["sleep"] - 0.45, 7.55
    ax.plot([xr, xr, xs["search"] - 0.45], [y + 0.78, yr, yr], color=SLATE, lw=1.5, zorder=2)
    link((xs["search"] - 0.45, yr), (xs["search"] - 0.45, y + 0.78), "", color=SLATE)
    ax.text(4.4, yr, "Record from sleep — SEARCH: still until the first look, then sweep", fontsize=13.6, color=SLATE, ha="left", va="center", zorder=5,
            bbox=dict(fc="white", ec="none", pad=1.2))
    link((xs["awake"] + R, y), (xs["search"] - R, y), "Track &\nrecord", lofs=(5.5, y + 0.6), fs=12.8)
    # person already in frame: straight to FOUND
    ax.annotate("", xy=(xs["found"], y + R), xytext=(xs["awake"] + R, yp), zorder=2,
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.5, shrinkA=0, shrinkB=0,
                                connectionstyle="angle,angleA=0,angleB=90,rad=0"))
    ax.text(8.9, yp + 0.3, "Track & record — person already in frame: skip the sweep",
            fontsize=13.6, ha="center", va="center", color=INK, zorder=5,
            bbox=dict(fc="white", ec="none", pad=1.2))
    link((xs["search"] + R, y), (xs["found"] - R, y), "person\nseen", lofs=(9.3, y + 0.5))
    # FOUND lost the person -> search again; the 3 s starts over
    link((xs["found"] - 0.3, y - R), (xs["search"] + 0.3, y - R), "nobody seen 1 s",
         rad=-0.45, lofs=(9.3, 1.95))
    link((xs["found"] + R, y), (xs["rec"] - 1.1, y), "still in\nframe 3 s", lofs=(12.95, y + 0.5))
    # RECORDING lost the person for 6 s: sweep again, still recording
    ax.annotate("", xy=(xs["rec"] + 0.5, y + 0.98), xytext=(xs["rec"] - 0.5, y + 0.98), zorder=2,
                arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.5, shrinkA=0, shrinkB=0,
                                connectionstyle="arc3,rad=-1.3"))
    ax.text(xs["rec"], y + 2.3, "lost 6 s: sweep again,\nstill recording", fontsize=13.6,
            color=RED, ha="center", va="center", bbox=dict(fc="white", ec="none", pad=1.2))

    # stop recording -> AWAKE, under everything
    x_in = xs["awake"] + 0.12
    ax.plot([xs["rec"], xs["rec"], x_in], [y - 1.1, 1.0, 1.0], color=RED, lw=1.5, zorder=2)
    link((x_in, 1.0), (x_in, y - R + 0.01), "", color=RED)
    ax.text(10.6, 1.0, "stop recording → awake", fontsize=13.6, color=RED,
            ha="center", va="center", zorder=5, bbox=dict(fc="white", ec="none", pad=1.2))
    # stop tracking (and the build's automatic exit) -> AWAKE
    link((6.4, 1.75), (xs["awake"] + 0.55, y - 0.38), "", rad=-0.3, color=GREY, ls="--")
    ax.text(5.3, 1.3, "stop tracking, or 180 s\nnobody found → awake", fontsize=13.6,
            color=GREY, ha="center", va="center", bbox=dict(fc="white", ec="none", pad=1.2))

    # per-state captions: the LED ring
    cap = [(xs["sleep"], "LED: one dim pixel;\ncamera off"),
           (xs["awake"], "LED blue: solid,\nbreathing with a person in frame"),
           (xs["search"], "LED chasing green;\nsweep pan ±80°, lens wide"),
           (xs["found"], "LED fills green over 3 s;\nframe them as when recording"),
           (xs["rec"], "LED solid red")]
    for x, t in cap:
        ax.text(x, 0.3, t, ha="center", va="center", fontsize=13.6, color=INK)
    ax.text(1.0, 1.6, "\"sleep\" from\nany awake state", fontsize=13.6, color=GREY, ha="center")
    save(fig, "state-machine.png", dpi=220)


# ----------------------------------------------------------------------------
# 4. Search and track
# ----------------------------------------------------------------------------
def search_and_track():
    fig, ax = new_fig(14.0, 7.0, "Search → found → record")

    # --- left: the sweep, drawn in pan/tilt space -----------------------
    x0, x1, yb, yt = 0.9, 6.4, 1.6, 5.2         # axes box
    ax.text((x0 + x1) / 2, 6.15, "SEARCH: the sweep", fontsize=11, fontweight="bold",
            color=GREEN, ha="center")
    ax.add_patch(Rectangle((x0, yb), x1 - x0, yt - yb, fc="#f4f8ff", ec=INK, lw=1.3))

    def px(pan):  # pan -80..80 -> x
        return x0 + (pan + 80) / 160 * (x1 - x0)

    def py(tilt):  # tilt 0..30 -> y
        return yb + 0.35 + tilt / 30 * (yt - yb - 0.7)

    for p in (-80, -40, 0, 40, 80):
        ax.plot([px(p)] * 2, [yb, yb - 0.1], color=INK, lw=1)
        ax.text(px(p), yb - 0.38, f"{p:+d}°" if p else "0°", ha="center", fontsize=8.5, color=INK)
    ax.text((x0 + x1) / 2, yb - 0.85, "pan (soft limits ±80°)", ha="center", fontsize=9, color=GREY)
    ax.text(x0 - 0.6, (yb + yt) / 2, "tilt", rotation=90, va="center", fontsize=9, color=GREY)
    for t in (5, 22):
        ax.plot([x0 - 0.1, x0], [py(t)] * 2, color=INK, lw=1)
        ax.text(x0 - 0.18, py(t), f"{t}°", ha="right", va="center", fontsize=8.5, color=INK)
        ax.plot([x0, x1], [py(t)] * 2, color="#c8d3e6", lw=0.8, ls=":")
    ax.text(x1 - 0.1, py(5) - 0.28, "row 1", ha="right", fontsize=8, color=GREY)
    ax.text(x1 - 0.1, py(22) + 0.2, "row 2", ha="right", fontsize=8, color=GREY)

    # zig-zag path: row 1 left→right, step up, row 2 right→left, step down
    ax.plot([px(-80), px(80)], [py(5)] * 2, color=GREEN, lw=2.4)
    ax.plot([px(80), px(80)], [py(5), py(22)], color=GREEN, lw=2.4)
    ax.plot([px(80), px(-80)], [py(22)] * 2, color=GREEN, lw=2.4)
    ax.plot([px(-80), px(-80)], [py(22), py(5)], color=GREEN, lw=2.4, ls=(0, (2, 2)))
    for (a, b) in (((px(-30), py(5)), (px(-10), py(5))), ((px(40), py(22)), (px(20), py(22)))):
        ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=2.4))
    ax.text(px(-76), py(5) + 0.2, "start", fontsize=8.5, color=GREEN)
    ax.text(px(-6), py(13.5), "reverse and step the tilt row\nat every end of the sweep", fontsize=8.5,
            color=GREEN, ha="center", va="center",
            bbox=dict(fc="#f4f8ff", ec="none", pad=1))

    # person found
    pp = (px(38), py(5))
    ax.add_patch(Circle((pp[0], pp[1] + 0.32), 0.1, fc="none", ec=RED, lw=1.8))
    ax.plot([pp[0], pp[0]], [pp[1] + 0.22, pp[1] - 0.05], color=RED, lw=1.8)
    ax.text(pp[0] + 0.18, pp[1] + 0.62, "first person\nthe detector sees", fontsize=8.5,
            color=RED, ha="left", va="bottom")

    ax.text((x0 + x1) / 2, 0.45,
            "25°/s pan, lens zoomed wide (96°), focus guessed at 5 m,\ntilt rows 5° and 22° (the lens is about 1.5 m up)",
            fontsize=8.5, color=GREY, ha="center", va="center")

    # --- right: the cycle ----------------------------------------------
    def state(cx, cy, w, h, name, sub, c):
        ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.06",
                                    fc="white", ec=c, lw=2.6, zorder=3))
        ax.text(cx, cy + 0.2, name, ha="center", va="center", fontsize=12, fontweight="bold",
                color=c, zorder=4)
        ax.text(cx, cy - 0.3, sub, ha="center", va="center", fontsize=8.5, color=INK, zorder=4)

    def link(p1, p2, label, lofs, rad=0.0, color=INK, ha="center"):
        ax.annotate("", xy=p2, xytext=p1, zorder=2,
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.7,
                                    connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))
        ax.text(lofs[0], lofs[1], label, ha=ha, va="center", fontsize=8.5, color=color, zorder=5,
                bbox=dict(fc="white", ec="none", pad=1.2))

    ax.text(10.25, 6.15, "The loop", fontsize=11, fontweight="bold", color=INK, ha="center")
    S, C, T = (8.4, 4.55), (12.1, 4.55), (10.25, 1.95)
    state(*S, 2.3, 1.3, "SEARCH", "sweep until someone\nis detected", GREEN)
    state(*C, 2.3, 1.3, "FOUND", "follow and frame\nthem for 3 s", GREEN)
    state(*T, 2.9, 1.3, "RECORDING", "follow the first person\nfound, by vision only", RED)

    link((S[0] + 1.15, S[1] + 0.2), (C[0] - 1.15, C[1] + 0.2), "person seen", (10.25, 5.1))
    # session start: where the loop is entered depends on awake's sub-state
    link((S[0] - 0.5, S[1] + 1.45), (S[0] - 0.5, S[1] + 0.65), "start, nobody in\nframe or just woken",
         (S[0] - 0.6, S[1] + 1.1), ha="right")
    link((C[0] + 0.5, C[1] + 1.45), (C[0] + 0.5, C[1] + 0.65), "start, person in\nframe (no sweep)",
         (C[0] + 0.6, C[1] + 1.1), ha="left")
    link((C[0] - 1.15, C[1] - 0.2), (S[0] + 1.15, S[1] - 0.2), "nobody seen\nfor 1 s", (10.25, 3.95))
    link((C[0] + 0.3, C[1] - 0.65), (T[0] + 1.0, T[1] + 0.65), "still in\nframe 3 s", (12.5, 3.25),
         rad=-0.15)
    link((T[0] - 1.0, T[1] + 0.65), (S[0] + 0.4, S[1] - 0.65), "lost for 6 s", (8.0, 3.2),
         rad=-0.15)
    ax.text(9.0, 0.55, "after a loss the next person found is recorded at once;\nthe 180 s give-up applies only before recording",
            fontsize=8.5, color=GREY, ha="center", va="center")
    save(fig, "search-and-track.png")


# ----------------------------------------------------------------------------
# 5. App UI mock
# ----------------------------------------------------------------------------
def app_ui():
    fig, ax = new_fig(14.3, 7.2, "Companion app — four states")
    labels = [
        ("SLEEP", SLATE, ["Wake up", "Record"], "Asleep — camera off"),
        ("AWAKE", BLUE, ["Sleep", "Track & record"], "Awake"),
        ("INITIATE RECORDING", GREEN, ["Sleep", "Stop tracking"], "Looking for a person…"),
        ("RECORDING", RED, ["Sleep", "Stop recording"], "Recording · following"),
    ]
    for i, (name, c, buttons, status) in enumerate(labels):
        x0 = 0.5 + i * 3.5
        ax.add_patch(FancyBboxPatch((x0, 0.6), 2.9, 5.9, boxstyle="round,pad=0.08",
                                    fc="white", ec=INK, lw=2))
        ax.add_patch(Rectangle((x0 + 0.15, 2.05), 2.6, 4.05, fc="#0d1420", ec="none"))
        ax.text(x0 + 1.45, 4.15, "camera asleep:\nno live view" if i == 0 else "live video\n(WebRTC / MJPEG)",
                ha="center", fontsize=8.5, color="#7f8ea8")
        if i > 1:   # a person is only in frame once one has been found
            sx, sy = x0 + 1.45, 3.1
            ax.add_patch(Circle((sx, sy + 0.55), 0.13, fc="none", ec="#cbd6ea", lw=1.5))
            ax.plot([sx, sx], [sy + 0.42, sy - 0.05], color="#cbd6ea", lw=1.5)
            ax.plot([sx - 0.22, sx, sx + 0.22], [sy - 0.4, sy - 0.05, sy - 0.4], color="#cbd6ea", lw=1.5)
            ax.plot([sx - 0.22, sx + 0.22], [sy + 0.25, sy + 0.25], color="#cbd6ea", lw=1.5)
        ax.add_patch(Circle((x0 + 2.45, 5.75), 0.20, fc=c, ec="white", lw=2))
        if i == 1:
            ax.annotate("status ring", xy=(x0 + 2.45, 5.75), xytext=(x0 + 1.15, 6.75),
                        fontsize=8, color=GREY,
                        arrowprops=dict(arrowstyle="->", color=GREY, lw=1))
        ax.text(x0 + 1.45, 1.8, status, ha="center", va="center", fontsize=8.5, color=INK,
                style="italic")
        for j, b in enumerate(buttons):
            bx = x0 + 0.2 + j * 1.3
            bc = RED if name == "SLEEP" else c     # Record: a session that records
            fc = "#eef1f7" if j == 0 else bc
            tc = INK if j == 0 else "white"
            ax.add_patch(FancyBboxPatch((bx, 0.85), 1.2, 0.8, boxstyle="round,pad=0.05",
                                        fc=fc, ec=INK if j == 0 else bc))
            ax.text(bx + 0.6, 1.25, b.replace(" ", "\n", 1), ha="center", va="center",
                    fontsize=8, color=tc, fontweight="bold")
        ax.text(x0 + 1.45, 0.25, name, ha="center", fontsize=11, fontweight="bold", color=c)
    save(fig, "app-ui.png")


# ----------------------------------------------------------------------------
# 6. Power tree
# ----------------------------------------------------------------------------
def power_tree():
    fig, ax = new_fig(11.5, 6.4, "Power distribution — battery")
    box(ax, 0.3, 4.1, 2.7, 1.7, "USB-C PD power bank",
        ["25 000 mAh · 92 Wh label", "≈ 84 Wh at 12 V", "65 W+, 100 W cable"], fc="#fdf6e8")
    box(ax, 3.7, 4.1, 2.4, 1.7, "PD trigger → 12 V", ["+ power latch", "rocker = on/off"], fc="#fdf6e8")
    box(ax, 6.8, 4.1, 2.3, 1.7, "INA260 gauge",
        ["I2C 0x40", "shunt on die", "Wh integration"], fc="#f2fff5")
    box(ax, 3.7, 2.3, 2.4, 1.3, "Buck 12→5 V 8 A", ["5.1 V under load", "≈ 92 % efficient"], fc="#f2f7ff")
    box(ax, 7.0, 1.95, 3.4, 2.05, "5 V rail — 8.5 W avg",
        ["Pi 4 + HW encode + CV  6.0 W", "PTZ servos + lens  1.0 W",
         "LED ring  1.5 W"], fc="#f2f7ff")
    box(ax, 7.0, 0.1, 3.4, 1.6, "Runtime (84 Wh at 12 V)",
        ["tracking + recording  8.4 h", "tracking only  8.9 h",
         "awake  12 h"], fc="#f2fff5")

    arrow(ax, (3.0, 4.95), (3.7, 4.95), "USB-C PD")
    arrow(ax, (6.1, 4.95), (6.8, 4.95), "12 V")
    arrow(ax, (7.9, 4.1), (5.5, 3.5), "12 V sensed", lofs=(0.55, 0.2))
    arrow(ax, (6.1, 2.95), (7.0, 2.95), "5 V")
    arrow(ax, (8.7, 1.95), (8.7, 1.72), "", color=GREEN)
    ax.text(5.4, 0.9, "No mains. The 7 % cutoff\nstops and saves the recording\nbefore the pack dies.\nSwitching off does the same,\nthen the latch cuts the power.",
            fontsize=8.5, color=GREY, ha="center")
    save(fig, "power-tree.png")


if __name__ == "__main__":
    intro_scene()
    system_architecture()
    mechanical_layout()
    state_machine()
    search_and_track()
    app_ui()
    power_tree()
