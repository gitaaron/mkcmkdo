"""Sample frames from the camera, for improving person detection.

The app's Sample button calls `takeSample`: the camera saves, in SAMPLE_DIR,

    <time>.jpg            the full frame (RECORD_SIZE), as the sensor sees it
    <time>-detector.jpg   the frame the person detector works on (PREVIEW_SIZE)
    <time>.json           what it made of it: the detector run on that very
                          frame, the tracker's labelled boxes from its last
                          detection, and the state, zoom, focus and aim

Both pictures come from one capture, so they are the same instant. They are
as the sensor sees them — on its side on the bench kit; `telemetry.view`
says how the app turns them upright — because that is what detection sees.

Samples are photos of people, often bystanders: they stay on the card and on
your own computer (scripts/pi/samples.sh copies them into samples/, which git
ignores), and never go to the cloud backend.
"""
from __future__ import annotations

import glob
import json
import os
import time

from . import config
from .wifi_link import public_state

JPEG_QUALITY = 92


class NoPicture(Exception):
    """The sensor is off (asleep), so there is nothing to sample."""


def save(head) -> dict:
    """Take a sample now; {"name": …, "count": samples on the card}."""
    import cv2

    shot = head.camera.snapshot()
    if shot is None:
        raise NoPicture("the camera is asleep: wake it to take a sample")
    full, small = shot
    detected = head.camera.detect_frame(small)

    now = time.time()
    name = time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + f"-{int(now * 1000) % 1000:03d}"
    os.makedirs(config.SAMPLE_DIR, exist_ok=True)
    base = os.path.join(config.SAMPLE_DIR, name)
    q = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    cv2.imwrite(base + ".jpg", full[:, :, ::-1], q)
    cv2.imwrite(base + "-detector.jpg", small[:, :, ::-1], q)

    labelled_at = head.tracker.labelled_at
    meta = {
        "name": name,
        "takenAt": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
        "build": config.TRACKING_MODE,
        "state": public_state(head.state),
        "phase": head.phase,
        "fullSize": [int(full.shape[1]), int(full.shape[0])],
        "detectorSize": [int(small.shape[1]), int(small.shape[0])],
        "detector": type(head.camera._detector).__name__ if head.camera._detector else None,
        # the detector on this frame: [x, y, w, h] in detector-frame pixels
        "detected": [[int(v) for v in box] for box in detected],
        # the tracker's view from its last detection (climber / other / unsure)
        "liveBoxes": head.live_boxes(),
        "liveBoxesAgeS": (round(time.monotonic() - labelled_at, 2)
                          if labelled_at is not None else None),
        "telemetry": head.telemetry(),
    }
    with open(base + ".json", "w") as f:
        json.dump(meta, f, indent=1)
    count = len(glob.glob(os.path.join(config.SAMPLE_DIR, "*.json")))
    print(f"[sample] {name}: {len(detected)} detected, {len(meta['liveBoxes'])} live boxes "
          f"({count} on the card)")
    return {"name": name, "count": count}
