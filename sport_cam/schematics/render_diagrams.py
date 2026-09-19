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


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name), bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


# ----------------------------------------------------------------------------
# 0. Intro scene — camera tracking a climber wearing the tag
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
    # harness + wearable tag (rear waist, off-spine → faces the camera)
    ax.plot([hx - 0.06, hx + 0.16], [hy + 0.02, hy + 0.06], color="#5a3d2b", lw=5)
    ax.add_patch(Circle((hx + 0.02, hy - 0.06), 0.09, fc=RED, ec="white", lw=1.5, zorder=5))
    ax.annotate("wearable tag\n(rear harness, off-spine)", xy=(hx + 0.02, hy - 0.06),
                xytext=(3.2, 6.9), fontsize=9, color=RED,
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.2))

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
    # UWB anchor arms (perpendicular-ish to view; shown as two pods)
    for s in (-0.62, 0.62):
        ax.add_patch(Circle((tx + s, ty + 2.29), 0.1, fc="#e8f7ee", ec=GREEN, lw=1.5))
    ax.text(tx, ty + 3.35, "SportCam head:\npan · tilt · zoom", fontsize=9, color=INK, ha="center")

    # field-of-view cone from lens to climber
    fov = Polygon([(cam_x - 0.55, cam_y + 0.1), (hx + 0.9, hy + 1.7), (hx + 0.4, hy - 1.4)],
                  closed=True, fc="#2f6fed", ec="none", alpha=0.10)
    ax.add_patch(fov)
    ax.annotate("", xy=(hx + 0.75, hy + 0.35), xytext=(cam_x - 0.6, cam_y + 0.05),
                arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=1.6, ls="-"))
    ax.text(5.1, 4.35, "camera follows,\nzoom holds framing", fontsize=9, color=BLUE, rotation=24)

    # UWB ranging lines anchors → tag
    for s in (-0.62, 0.62):
        ax.plot([tx + s, hx + 0.02], [ty + 2.29, hy - 0.06], color=GREEN, ls="--", lw=1.1)
    ax.text(4.6, 2.95, "UWB ranging 20 Hz", fontsize=9, color=GREEN, rotation=31)

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

    # Home server
    box(ax, 4.5, 5.4, 3.2, 1.9, "Home server (Node.js + TS)",
        ["REST /api/call/*  (fn-style)", "WebSocket hub  /ws", "MJPEG relay + state store", "Vue 3 web app (Vite)"])
    # App
    box(ax, 9.2, 5.4, 2.5, 1.9, "Phone / laptop app",
        ["Vue 3 SPA", "live video", "status ring + buttons"])
    # Head
    box(ax, 0.4, 2.4, 3.4, 2.3, "Head unit (rotating)",
        ["Raspberry Pi 5", "Arducam zoom cam (I2C)", "Tilt servo 270°", "2× UWB anchors (UART)"])
    # Base
    box(ax, 4.6, 0.3, 3.2, 2.0, "Base unit (static)",
        ["ESP32 base controller", "NEMA17 + TMC2209 (pan)", "WS2812 LED status ring", "12 V PSU + slip ring"])
    # Wearable
    box(ax, 9.2, 2.4, 2.5, 1.9, "Wearable tag",
        ["ESP32 + DW1000 UWB", "LiPo + strap", "pair button"])

    arrow(ax, (6.1, 5.4), (6.1, 2.3), "Wi-Fi WS: pan cmds / LED state", color=BLUE, lofs=(1.35, 0))
    arrow(ax, (3.8, 4.0), (4.5, 5.6), "Wi-Fi: state + video", color=BLUE, lofs=(-0.9, 0.1))
    arrow(ax, (7.7, 6.4), (9.2, 6.4), "HTTP + WS + WebRTC", color=BLUE)
    arrow(ax, (9.2, 3.3), (3.8, 3.3), "UWB two-way ranging (6.5 GHz)", color=GREEN, ls="--")
    arrow(ax, (6.2, 2.3), (3.4, 2.55), "5 V via slip ring", color=RED, lofs=(0.2, -0.35))
    ax.text(2.1, 5.05, "camera aims at subject", fontsize=8.5, color=GREY, ha="center")
    save(fig, "system-architecture.png")


# ----------------------------------------------------------------------------
# 2. Mechanical layout (side view)
# ----------------------------------------------------------------------------
def mechanical_layout():
    fig, ax = new_fig(9.5, 9, "Head + base assembly (side view)")
    cx = 4.4

    # tripod legs
    for dx in (-2.6, 2.6):
        ax.plot([cx, cx + dx], [1.6, 0.2], color=INK, lw=3)
    ax.plot([cx, cx], [1.6, 0.2], color=GREY, lw=3)
    ax.text(cx + 2.0, 0.55, "standard tripod\n(1/4-20 mount)", fontsize=9, color=GREY)

    # base housing
    ax.add_patch(Rectangle((cx - 1.5, 1.6), 3.0, 1.5, fc=BGBOX, ec=INK, lw=1.5))
    ax.text(cx, 2.62, "BASE (static)", ha="center", fontsize=10, fontweight="bold", color=INK)
    ax.text(cx, 2.28, "ESP32 · TMC2209 · 12V in", ha="center", fontsize=8.5, color=INK)
    # LED ring
    ax.add_patch(Rectangle((cx - 1.62, 1.72), 0.12, 1.0, fc=GREEN, ec="none"))
    ax.text(cx - 2.35, 2.2, "WS2812\nLED ring", fontsize=8.5, color=GREEN, ha="center")
    # stepper + belt
    ax.add_patch(Rectangle((cx + 0.55, 1.75), 0.8, 0.8, fc="#dde3ef", ec=INK))
    ax.text(cx + 0.95, 2.15, "NEMA\n17", ha="center", va="center", fontsize=7.5, color=INK)
    ax.text(cx + 1.9, 1.95, "GT2 belt 6:1", fontsize=8.5, color=INK)

    # turntable bearing + slip ring
    ax.add_patch(Rectangle((cx - 1.2, 3.1), 2.4, 0.28, fc="#c9d2e4", ec=INK))
    ax.text(cx + 2.15, 3.2, "lazy-susan bearing\n(120 T GT2 ring pulley bolted under)", fontsize=8.5, color=INK)
    ax.add_patch(Rectangle((cx - 0.22, 2.6), 0.44, 0.9, fc="#ffe9c7", ec=INK))
    ax.text(cx - 1.05, 2.85, "slip ring\n(5 V ×2 + GND ×2)", fontsize=8.5, ha="center", color="#9a6b00")

    # rotating platform
    ax.add_patch(Rectangle((cx - 1.7, 3.45), 3.4, 0.25, fc=BGBOX, ec=INK))
    ax.text(cx - 2.6, 3.5, "rotating\nplatform", fontsize=8.5, color=INK, ha="center")

    # Pi
    ax.add_patch(Rectangle((cx - 1.55, 3.8), 1.3, 0.75, fc=BGBOX, ec=INK))
    ax.text(cx - 0.9, 4.17, "Pi 5", ha="center", va="center", fontsize=9, fontweight="bold", color=INK)
    # tilt tower
    ax.add_patch(Rectangle((cx + 0.4, 3.7), 0.5, 1.9, fc=BGBOX, ec=INK))
    ax.text(cx + 1.5, 4.4, "tilt tower +\nDS3225 270° servo", fontsize=8.5, color=INK)
    # camera
    ax.add_patch(Circle((cx + 0.65, 5.9), 0.34, fc="#dde3ef", ec=INK, lw=1.5))
    ax.add_patch(Rectangle((cx + 0.28, 6.0), 0.74, 0.55, fc=BGBOX, ec=INK))
    ax.text(cx + 0.65, 6.28, "cam", ha="center", fontsize=8, color=INK)
    ax.add_patch(Wedge((cx + 0.65, 6.3), 1.4, 55, 125, fc="#eaf1ff", ec="none"))
    ax.text(cx + 0.65, 7.45, "motorized zoom lens (I2C)", fontsize=8.5, ha="center", color=BLUE)

    # UWB anchor arms
    for sx, name in ((-1, "anchor A1"), (1, "anchor A2")):
        x = cx + sx * 2.0
        ax.plot([cx + sx * 0.6, x], [5.1, 5.1], color=INK, lw=2)
        ax.add_patch(Rectangle((x - 0.22, 4.95), 0.44, 0.5, fc="#e8f7ee", ec=GREEN, lw=1.4))
        ax.text(x, 5.75, name, ha="center", fontsize=8.5, color=GREEN)
    ax.annotate("", xy=(cx - 2.0, 4.75), xytext=(cx + 2.0, 4.75),
                arrowprops=dict(arrowstyle="<->", color=GREEN))
    ax.text(cx, 4.5, "UWB baseline b = 40 cm", ha="center", fontsize=8.5, color=GREEN)

    # motion arrows
    ax.annotate("", xy=(cx + 2.6, 3.35), xytext=(cx + 3.3, 2.9),
                arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=2,
                                connectionstyle="arc3,rad=0.5"))
    ax.text(cx + 3.45, 3.35, "pan 360°\ncontinuous", fontsize=9, color=BLUE)
    ax.annotate("", xy=(cx - 0.35, 6.6), xytext=(cx + 1.7, 6.6),
                arrowprops=dict(arrowstyle="<|-|>", color=BLUE, lw=2,
                                connectionstyle="arc3,rad=-0.6"))
    ax.text(cx - 1.6, 6.75, "tilt 270°\n(−45°…+225°)", fontsize=9, color=BLUE, ha="center")
    save(fig, "mechanical-layout.png")


# ----------------------------------------------------------------------------
# 3. State machine
# ----------------------------------------------------------------------------
def state_machine():
    fig, ax = new_fig(10.5, 5.2, "Camera state machine · LED colours")
    states = [
        (1.6, 2.6, "OFF", GREY, "LED off"),
        (4.4, 2.6, "IDLE", BLUE, "on, not tracking\nLED solid blue"),
        (7.2, 2.6, "TRACKING", GREEN, "following subject\nLED solid green"),
        (9.4, 2.6, "RECORDING", RED, "tracking + saving\nLED pulsing red"),
    ]
    for x, y, name, c, sub in states:
        ax.add_patch(Circle((x, y), 0.78, fc="white", ec=c, lw=3))
        ax.text(x, y + 0.1, name, ha="center", fontsize=10, fontweight="bold", color=c)
        ax.text(x, y - 1.15, sub, ha="center", fontsize=8.5, color=INK)

    def edge(x1, x2, label, rad, ytxt):
        ax.annotate("", xy=(x2, 2.6 + (0.55 if rad < 0 else -0.55)),
                    xytext=(x1, 2.6 + (0.55 if rad < 0 else -0.55)),
                    arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.5,
                                    connectionstyle=f"arc3,rad={rad}"))
        ax.text((x1 + x2) / 2, ytxt, label, ha="center", fontsize=8.5, color=INK,
                bbox=dict(fc="white", ec="none", pad=1))

    edge(1.6, 4.4, "power on", -0.35, 4.05)
    edge(4.4, 1.6, "turn off", -0.55, 0.9)
    edge(4.4, 7.2, "start tracking", -0.35, 4.05)
    edge(7.2, 4.4, "stop tracking / lost tag", -0.5, 1.25)
    edge(7.2, 9.4, "start recording", -0.45, 4.15)
    edge(9.4, 7.2, "stop recording", -0.5, 1.5)
    ax.text(5.25, 0.25, "\"turn off\" is available from every powered state", fontsize=8.5,
            color=GREY, ha="center")
    save(fig, "state-machine.png")


# ----------------------------------------------------------------------------
# 4. Tracking geometry
# ----------------------------------------------------------------------------
def tracking_geometry():
    fig, ax = new_fig(9.5, 7, "UWB tracking geometry (top view)")
    a1, a2 = (3.2, 2.2), (6.2, 2.2)
    tag = (7.3, 5.6)
    mid = ((a1[0] + a2[0]) / 2, a1[1])

    ax.add_patch(Circle(mid, 0.35, fc="#dde3ef", ec=INK, lw=1.5))
    ax.text(mid[0], mid[1] - 0.75, "camera axis", ha="center", fontsize=9, color=INK)
    for p, name in ((a1, "A1"), (a2, "A2")):
        ax.add_patch(Circle(p, 0.22, fc="#e8f7ee", ec=GREEN, lw=2))
        ax.text(p[0], p[1] - 0.55, name, ha="center", fontsize=9, color=GREEN)
    ax.plot([a1[0], a2[0]], [a1[1], a2[1]], color=GREEN, lw=1.5)
    ax.text(mid[0] - 0.05, 2.32, "baseline b", fontsize=8.5, color=GREEN, ha="right")

    ax.add_patch(Circle(tag, 0.26, fc="#fdecea", ec=RED, lw=2))
    ax.text(tag[0] + 0.4, tag[1] + 0.15, "wearable tag", fontsize=9, color=RED)

    for p, r, dy in ((a1, "r₁", 0.25), (a2, "r₂", 0.25)):
        ax.plot([p[0], tag[0]], [p[1], tag[1]], color=RED, ls="--", lw=1.4)
        ax.text((p[0] + tag[0]) / 2 - 0.25, (p[1] + tag[1]) / 2 + dy, r, fontsize=10, color=RED)

    # camera boresight and error angle
    ax.annotate("", xy=(mid[0], 6.4), xytext=mid,
                arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=2))
    ax.text(mid[0] - 0.15, 6.35, "boresight", fontsize=9, color=BLUE, ha="right")
    ang = math.degrees(math.atan2(tag[1] - mid[1], tag[0] - mid[0]))
    ax.add_patch(Wedge(mid, 1.5, ang, 90, fc="#eaf1ff", ec="none", alpha=0.9))
    ax.text(mid[0] + 0.75, 3.9, "θ error", fontsize=10, color=BLUE)

    ax.text(1.0, 6.3, "θ ≈ asin( (r₁² − r₂²) / (2·b·d) )\nd = (r₁ + r₂) / 2",
            fontsize=11, color=INK, family="monospace",
            bbox=dict(fc=BGBOX, ec=INK, boxstyle="round,pad=0.5"))
    ax.text(1.0, 4.9, "pan loop drives θ → 0\nzoom loop holds d at target framing\ntilt from person-detect bounding box",
            fontsize=9, color=GREY)
    save(fig, "tracking-geometry.png")


# ----------------------------------------------------------------------------
# 5. App UI mock
# ----------------------------------------------------------------------------
def app_ui():
    fig, ax = new_fig(10.8, 7.2, "Companion app — three states")
    labels = [
        ("IDLE", BLUE, ["Turn off", "Start tracking"]),
        ("TRACKING", GREEN, ["Turn off", "Start recording"]),
        ("RECORDING", RED, ["Stop recording", "Stop tracking"]),
    ]
    for i, (name, c, buttons) in enumerate(labels):
        x0 = 0.5 + i * 3.5
        # phone body
        ax.add_patch(FancyBboxPatch((x0, 0.6), 2.9, 5.9, boxstyle="round,pad=0.08",
                                    fc="white", ec=INK, lw=2))
        # video area
        ax.add_patch(Rectangle((x0 + 0.15, 2.0), 2.6, 4.1, fc="#0d1420", ec="none"))
        ax.text(x0 + 1.45, 4.15, "live video\n(WebRTC / MJPEG)", ha="center",
                fontsize=8.5, color="#7f8ea8")
        # subject stick figure
        sx, sy = x0 + 1.45, 3.1
        ax.add_patch(Circle((sx, sy + 0.55), 0.13, fc="none", ec="#cbd6ea", lw=1.5))
        ax.plot([sx, sx], [sy + 0.42, sy - 0.05], color="#cbd6ea", lw=1.5)
        ax.plot([sx - 0.22, sx, sx + 0.22], [sy - 0.4, sy - 0.05, sy - 0.4], color="#cbd6ea", lw=1.5)
        ax.plot([sx - 0.22, sx + 0.22], [sy + 0.25, sy + 0.25], color="#cbd6ea", lw=1.5)
        # status ring, top-right
        ax.add_patch(Circle((x0 + 2.45, 5.75), 0.20, fc=c, ec="white", lw=2))
        ax.annotate("status ring", xy=(x0 + 2.45, 5.75), xytext=(x0 + 1.15, 6.75),
                    fontsize=8, color=GREY,
                    arrowprops=dict(arrowstyle="->", color=GREY, lw=1)) if i == 0 else None
        # buttons
        for j, b in enumerate(buttons):
            bx = x0 + 0.2 + j * 1.3
            fc = "#eef1f7" if j == 0 else c
            tc = INK if j == 0 else "white"
            ax.add_patch(FancyBboxPatch((bx, 0.85), 1.2, 0.8, boxstyle="round,pad=0.05",
                                        fc=fc, ec=INK if j == 0 else c))
            ax.text(bx + 0.6, 1.25, b.replace(" ", "\n", 1), ha="center", va="center",
                    fontsize=8, color=tc, fontweight="bold")
        ax.text(x0 + 1.45, 0.25, name, ha="center", fontsize=11, fontweight="bold", color=c)
    save(fig, "app-ui.png")


# ----------------------------------------------------------------------------
# 6. Power tree
# ----------------------------------------------------------------------------
def power_tree():
    fig, ax = new_fig(11, 6.2, "Power distribution")
    box(ax, 0.4, 4.4, 2.5, 1.3, "12 V 5 A PSU", ["barrel jack, 60 W"])
    box(ax, 4.0, 4.7, 2.6, 1.1, "TMC2209 + NEMA17", ["12 V · ≤1.2 A"], fc="#fff4f2")
    box(ax, 4.0, 3.2, 2.6, 1.1, "Buck #1 → 5 V 3 A", ["base: ESP32 + LED ring"], fc="#f2fff5")
    box(ax, 4.0, 1.7, 2.6, 1.1, "Buck #2 → 5 V 5 A", ["through slip ring →"], fc="#f2f7ff")
    box(ax, 7.8, 2.6, 2.8, 1.4, "Head rail 5 V", ["Pi 5 (≤5 A pk)", "camera + UWB ×2"], fc="#f2f7ff")
    box(ax, 7.8, 0.6, 2.8, 1.2, "Servo rail 5 V", ["DS3225 stall 2.5 A", "own buck #3 on head"], fc="#fffbe8")
    box(ax, 0.4, 0.6, 2.5, 1.3, "Wearable LiPo", ["1000 mAh + TP4056", "USB-C charge"], fc="#fdf2f2")
    arrow(ax, (2.9, 5.1), (4.0, 5.25), "12 V")
    arrow(ax, (2.9, 4.9), (4.0, 3.75), "12 V")
    arrow(ax, (2.9, 4.7), (4.0, 2.25), "12 V")
    arrow(ax, (6.6, 2.25), (7.8, 3.1), "slip ring 2+2 wires", lofs=(0.1, -0.3))
    arrow(ax, (6.6, 2.0), (7.8, 1.3), "12 V up, buck on head", lofs=(0.15, -0.35))
    ax.text(1.65, 0.25, "independent — never wired to tripod", fontsize=8, color=GREY, ha="center")
    save(fig, "power-tree.png")


if __name__ == "__main__":
    intro_scene()
    system_architecture()
    mechanical_layout()
    state_machine()
    tracking_geometry()
    app_ui()
    power_tree()
