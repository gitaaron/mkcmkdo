"""Picamera2 wrapper: 720p preview (JPEG for MJPEG relay + CV) and
1080p H.264 record stream.

On a Raspberry Pi 4 `H264Encoder` is the **hardware** encoder, so recording
costs almost no CPU. That is the main reason this build is on a Pi 4 rather
than a Pi 5, which dropped the block and has to encode in software.

Person detection is the expensive part here, so it is rate-limited, cropped
to a vertical strip around the person once the tracker has locked on, and
reports whether a result is fresh so the tracker never integrates the same
measurement twice. It is the only sensor in this build.
"""
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

Box = tuple[int, int, int, int]      # x, y, w, h in preview pixels


class Camera:
    def __init__(self) -> None:
        self._cam = None
        self._encoder = None
        self._hog = None
        self._qr = None
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
        # Detection is the biggest CPU cost on this board, so it is
        # rate-limited and throttled further when nothing is being tracked
        # (docs/03, "Running on a battery"). Between runs the cached box is
        # returned with fresh=False, which is what stops the pan/tilt goals
        # integrating one measurement over and over.
        self._detect_period = 1.0 / config.DETECT_FPS_TRACKING
        self._detect_at = 0.0
        self._boxes: list[Box] = []
        self._fresh = False
        self.awake = True                        # sensor running (stopped in sleep)
        self._warm_until = 0.0
        self._strip_cx: float | None = None      # column to search, once locked on

    def set_awake(self, on: bool) -> None:
        """Start or stop the sensor: stopped in sleep to save the battery.

        Nothing is captured while it sleeps (no preview, detection or QR
        reads). On waking the first CAMERA_WARMUP_S are skipped by the
        detector so exposure can settle, and the cached boxes are dropped: a
        session started from sleep must not act on what was seen before it.
        """
        if on == self.awake:
            return
        self.awake = on
        self._boxes = []
        self._detect_at = 0.0
        self._warm_until = time.monotonic() + config.CAMERA_WARMUP_S if on else 0.0
        if self._cam:
            if on:
                self._cam.start()
            else:
                self.stop_recording()
                self._cam.stop()

    def set_detect_fps(self, fps: float) -> None:
        self._detect_period = 1.0 / max(0.1, fps)

    def set_search_column(self, cx_px: float | None) -> None:
        """Hint the detector which column of the frame to search.

        The tracker passes the followed person's last x position once locked
        on, so only a vertical strip around it is searched: the cheapest
        speed-up available. ``None`` (while sweeping for someone) searches the
        whole frame.
        """
        self._strip_cx = cx_px

    def preview_jpeg(self) -> bytes | None:
        if not (self._cam and self.awake):
            return None
        rgb = self._cam.capture_array("lores")
        ok, jpg = cv2.imencode(".jpg", rgb[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 80])
        return jpg.tobytes() if ok else None

    def person_boxes(self) -> tuple[list[Box], bool]:
        """Every detected person → ([(x, y, w, h), ...], fresh).

        Rate-limited to `set_detect_fps`. Between detections the previous list
        comes back with ``fresh=False`` so the caller can tell a new
        measurement from a repeat of the last one.
        """
        if not (self._cam and self._hog and self.awake):
            return [], False
        now = time.monotonic()
        if now < self._warm_until or now - self._detect_at < self._detect_period:
            return self._boxes, False
        self._detect_at = now
        self._boxes = self._detect()
        return self._boxes, True

    def _detect(self) -> list[Box]:
        rgb = self._cam.capture_array("lores")
        pw, ph = config.PREVIEW_SIZE

        # Crop to a vertical strip around the followed person, when locked on.
        x0 = 0
        if self._strip_cx is not None and config.DETECT_STRIP_FRACTION:
            half = pw * config.DETECT_STRIP_FRACTION / 2
            x0 = int(max(0, min(pw - 2 * half, self._strip_cx - half)))
            rgb = rgb[:, x0:x0 + int(2 * half)]

        sw = config.DETECT_DOWNSCALE_W
        sh = max(1, int(round(rgb.shape[0] * sw / rgb.shape[1])))
        small = cv2.resize(rgb, (sw, sh))
        rects, _ = self._hog.detectMultiScale(
            small, hitThreshold=config.DETECT_HIT_THRESHOLD, winStride=(8, 8))
        sx = rgb.shape[1] / sw
        sy = ph / sh
        return [(int(x * sx) + x0, int(y * sy), int(w * sx), int(h * sy))
                for x, y, w, h in rects]

    def qr_text(self) -> str | None:
        """Whatever QR code is in front of the lens, or None.

        Used only while pairing, to read the phone's Wi-Fi share code
        (wifi_link.py). A full-frame decode costs ≈ 50–100 ms on a Pi 4, so
        the caller runs it off the event loop, a couple of times a second.
        """
        if not (self._cam and cv2 and self.awake):
            return None
        if self._qr is None:
            self._qr = cv2.QRCodeDetector()
        grey = cv2.cvtColor(self._cam.capture_array("lores"), cv2.COLOR_RGB2GRAY)
        text, _pts, _ = self._qr.detectAndDecode(grey)
        return text or None

    def start_recording(self) -> str:
        os.makedirs(config.RECORD_DIR, exist_ok=True)
        path = os.path.join(config.RECORD_DIR, time.strftime("rec_%Y%m%d_%H%M%S.mp4"))
        if self._cam:
            self._encoder = H264Encoder(bitrate=config.RECORD_BITRATE)
            self._cam.start_encoder(self._encoder, FfmpegOutput(path))
        return path

    def stop_recording(self) -> None:
        if self._cam and self._encoder:
            self._cam.stop_encoder()
            self._encoder = None
