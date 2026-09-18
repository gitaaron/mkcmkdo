"""Picamera2 wrapper: 720p preview (JPEG for MJPEG relay + CV) and
1080p H.264 record stream."""
from __future__ import annotations

import io
import os
import time

try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FfmpegOutput
except ImportError:  # dev machine
    Picamera2 = None

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None

from . import config


class Camera:
    def __init__(self) -> None:
        self._cam = None
        self._encoder = None
        self._hog = None
        if Picamera2:
            self._cam = Picamera2()
            cfg = self._cam.create_video_configuration(
                main={"size": config.RECORD_SIZE, "format": "YUV420"},
                lores={"size": config.PREVIEW_SIZE, "format": "RGB888"},
            )
            self._cam.configure(cfg)
            self._cam.start()
        if cv2:
            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def preview_jpeg(self) -> bytes | None:
        if not self._cam:
            return None
        rgb = self._cam.capture_array("lores")
        ok, jpg = cv2.imencode(".jpg", rgb[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 80])
        return jpg.tobytes() if ok else None

    def person_bbox(self) -> tuple[int, int, int, int] | None:
        """Largest detected person in the preview frame → (x, y, w, h)."""
        if not (self._cam and self._hog):
            return None
        rgb = self._cam.capture_array("lores")
        small = cv2.resize(rgb, (640, 360))
        rects, _ = self._hog.detectMultiScale(small, winStride=(8, 8))
        if len(rects) == 0:
            return None
        x, y, w, h = max(rects, key=lambda r: r[2] * r[3])
        sx = config.PREVIEW_SIZE[0] / 640
        sy = config.PREVIEW_SIZE[1] / 360
        return int(x * sx), int(y * sy), int(w * sx), int(h * sy)

    def start_recording(self) -> str:
        os.makedirs(config.RECORD_DIR, exist_ok=True)
        path = os.path.join(config.RECORD_DIR, time.strftime("rec_%Y%m%d_%H%M%S.mp4"))
        if self._cam:
            self._encoder = H264Encoder(bitrate=12_000_000)
            self._cam.start_encoder(self._encoder, FfmpegOutput(path))
        return path

    def stop_recording(self) -> None:
        if self._cam and self._encoder:
            self._cam.stop_encoder()
            self._encoder = None
