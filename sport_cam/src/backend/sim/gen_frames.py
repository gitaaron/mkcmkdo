#!/usr/bin/env python3
"""Generate the device-simulator test frames (src/backend/sim/frames/*.jpg).

Usage:  python3 src/backend/sim/gen_frames.py
"""
import math
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "frames")
os.makedirs(OUT, exist_ok=True)

W, H, N = 640, 360, 16

for i in range(N):
    t = i / N
    img = Image.new("RGB", (W, H), (13, 20, 32))
    d = ImageDraw.Draw(img)

    # ground + horizon
    d.rectangle([0, H * 0.72, W, H], fill=(19, 28, 44))
    d.line([0, H * 0.72, W, H * 0.72], fill=(42, 56, 80), width=2)

    # walking stick figure
    x = int(W * (0.2 + 0.6 * (0.5 - 0.5 * math.cos(2 * math.pi * t))))
    y = int(H * 0.62)
    swing = math.sin(4 * math.pi * t) * 14
    c = (203, 214, 234)
    d.ellipse([x - 12, y - 68, x + 12, y - 44], outline=c, width=3)          # head
    d.line([x, y - 44, x, y - 6], fill=c, width=3)                           # torso
    d.line([x - 20, y - 30, x + 20, y - 30], fill=c, width=3)                # arms
    d.line([x, y - 6, x - 14 + swing, y + 28], fill=c, width=3)              # legs
    d.line([x, y - 6, x + 14 - swing, y + 28], fill=c, width=3)

    # tracking reticle around subject
    d.rectangle([x - 34, y - 80, x + 34, y + 34], outline=(47, 111, 237), width=2)

    # HUD
    d.text((12, 10), "SPORTCAM SIMULATOR", fill=(127, 142, 168))
    d.text((12, H - 24), f"frame {i + 1:02d}/{N}   pan {int(360 * t):03d}°", fill=(90, 104, 130))

    img.save(os.path.join(OUT, f"frame_{i:02d}.jpg"), quality=82)

print(f"wrote {N} frames to {OUT}")
