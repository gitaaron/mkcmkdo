"""Picamera2 wrapper: 720p preview (JPEG for MJPEG relay + CV) and
1080p H.264 record stream.

On a Raspberry Pi 4 `H264Encoder` is the **hardware** encoder, so recording
costs almost no CPU. That is the main reason this build is on a Pi 4 rather
than a Pi 5, which dropped the block and has to encode in software.

Person detection is the expensive part here, so it is rate-limited, cropped
to a vertical strip around where ultra-wideband says the subject is, and
reports whether a result is fresh so the tracker never integrates the same
measurement twice.
"""
from __future__ import annotations

import io
import os
import threading
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
        self._qr = None
        if Picamera2:
            self._cam = Picamera2()
            cfg = self._cam.create_video_configuration(
                main={"size": config.RECORD_SIZE, "format": "YUV420"},
                lores={"size": config.PREVIEW_SIZE, "format": "RGB888"},
            )
            self._cam.configure(cfg)
            self._cam.start()
        # Why sessions cannot run on this install, or None. The head refuses
        # to start one and the app says why, rather than tracking blind.
        self.no_detector: str | None = None
        if cv2 and hasattr(cv2, "HOGDescriptor"):
            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        elif cv2:
            # OpenCV 5 moved HOG out of the main module. apt's python3-opencv
            # (4.x) has it; without it, boot (pairing still reads QR codes)
            # but run no sessions.
            self.no_detector = f"OpenCV {cv2.__version__} has no person detector (HOG)"
        elif self._cam:
            self.no_detector = "OpenCV is not installed"
        if self.no_detector:
            print(f"[camera] {self.no_detector} — tracking sessions disabled")
        # Detection is the biggest CPU cost on this board, so it is
        # rate-limited and throttled further when nothing is being tracked
        # (docs/03, "Running on a battery"). Between runs the cached box is
        # returned with fresh=False, which is what stops the tilt loop
        # integrating one measurement over and over.
        self._detect_period = 1.0 / config.DETECT_FPS_TRACKING
        self._detect_at = 0.0
        self._boxes: list[tuple[int, int, int, int]] = []
        self._fresh = False
        self.awake = True                        # sensor running (stopped in sleep)
        self._warm_until = 0.0
        self._strip_cx: float | None = None      # where UWB thinks the subject is
        # Detection runs on its own thread (_detect_loop): HOG takes a few
        # hundred ms on a Pi 4, and run inside the 20 Hz control tick it froze
        # the servos for that long every detection. OpenCV releases the GIL
        # while it works, so the control loop keeps easing meanwhile.
        self._lock = threading.Lock()
        # Held for every capture and for starting/stopping the sensor: a
        # capture waiting on a frame from a sensor stopped under it (sleep)
        # would wait for good. Captures are one frame, so it is held briefly.
        self._cam_lock = threading.Lock()
        self._seq = 0                            # results published
        self._seq_read = 0                       # results handed to the tracker
        self._gen = 0                            # bumped on sleep/wake: drops in-flight results
        self.captured_at: float | None = None    # when the latest boxes' frame was taken
        self._wake = threading.Event()
        if self._cam and self._hog:
            self._start_detector()

    def _start_detector(self) -> None:
        threading.Thread(target=self._detect_loop, name="detector", daemon=True).start()

    def _detect_loop(self) -> None:
        """Detect at `set_detect_fps` while awake, publishing each result once."""
        while True:
            now = time.monotonic()
            wait = max(self._warm_until, self._detect_at + self._detect_period) - now
            if not self.awake or wait > 0:
                self._wake.wait(0.05 if not self.awake else min(wait, 0.05))
                self._wake.clear()
                continue
            gen, strip = self._gen, self._strip_cx
            self._detect_at = now
            try:
                boxes = self._detect(strip)
            except Exception:                    # asleep now, or a bad frame
                continue
            with self._lock:
                if gen == self._gen:
                    self._boxes, self.captured_at = boxes, now
                    self._seq += 1

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
        with self._lock:
            self._gen += 1
            self._boxes = []
            self._seq_read = self._seq
        self._detect_at = 0.0
        self._warm_until = time.monotonic() + config.CAMERA_WARMUP_S if on else 0.0
        if self._cam:
            with self._cam_lock:
                if on:
                    self._cam.start()
                else:
                    self.stop_recording()
                    self._cam.stop()

    def set_detect_fps(self, fps: float) -> None:
        self._detect_period = 1.0 / max(0.1, fps)
        self._wake.set()

    def set_search_column(self, cx_px: float | None) -> None:
        """Hint the detector where to look horizontally.

        The tracker knows the subject's bearing and the camera's own angle, so
        it can say which column of the frame the subject must be in. Searching
        a strip instead of the whole frame is the cheapest speed-up available,
        and costs nothing in accuracy because vision is only being asked for
        the *vertical* position.
        """
        self._strip_cx = cx_px

    def _capture(self):
        """One preview frame (RGB), or None while the sensor sleeps. Any thread."""
        with self._cam_lock:
            if not (self._cam and self.awake):
                return None
            return self._cam.capture_array("lores")

    def preview_jpeg(self) -> bytes | None:
        rgb = self._capture()
        if rgb is None:
            return None
        ok, jpg = cv2.imencode(".jpg", rgb[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 80])
        return jpg.tobytes() if ok else None

    def person_bbox(self) -> tuple[tuple[int, int, int, int] | None, bool]:
        """Largest detected person → ((x, y, w, h) | None, fresh)."""
        boxes, fresh = self.person_boxes()
        return (max(boxes, key=lambda b: b[2] * b[3]) if boxes else None), fresh

    def person_boxes(self) -> tuple[list[tuple[int, int, int, int]], bool]:
        """Every detected person → ([(x, y, w, h), ...], fresh).

        All of them, not just the largest: the tracker has to pick out the
        one wearing the tag, and a bystander can be the bigger box.
        Rate-limited to `set_detect_fps`. Between detections the previous
        boxes come back with ``fresh=False`` so the caller can tell a new
        measurement from a repeat of the last one. `captured_at` says when
        the frame behind them was taken: the head has moved since.
        """
        if not (self._cam and self._hog and self.awake):
            return [], False
        with self._lock:
            fresh = self._seq != self._seq_read
            self._seq_read = self._seq
            return self._boxes, fresh

    def _detect(self, strip_cx: float | None) -> list[tuple[int, int, int, int]]:
        rgb = self._capture()
        if rgb is None:
            raise RuntimeError("asleep")         # set_awake(False) since the loop looked
        pw, ph = config.PREVIEW_SIZE

        # Crop to a vertical strip around the known bearing, when we have one.
        x0 = 0
        if strip_cx is not None and config.DETECT_STRIP_FRACTION:
            half = pw * config.DETECT_STRIP_FRACTION / 2
            x0 = int(max(0, min(pw - 2 * half, strip_cx - half)))
            rgb = rgb[:, x0:x0 + int(2 * half)]

        sw = config.DETECT_DOWNSCALE_W
        sh = max(1, int(round(rgb.shape[0] * sw / rgb.shape[1])))
        small = cv2.resize(rgb, (sw, sh))
        rects, _ = self._hog.detectMultiScale(small, winStride=(8, 8))
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
        rgb = self._capture()
        if rgb is None:
            return None
        grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
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
