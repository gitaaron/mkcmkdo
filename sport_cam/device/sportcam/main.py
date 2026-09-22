"""Head-unit supervisor: WebSocket client to the home server, state
handling, 20 Hz tracking loop, MJPEG frame push.

Run:  python -m sportcam.main          (from device/)
"""
from __future__ import annotations

import asyncio
import json
import time

import websockets

from . import config
from .camera import Camera
from .lens import Lens
from .tilt import Tilt
from .tracker import Tracker
from .uploader import upload_with_retry
from .uwb import UwbArray


class Head:
    def __init__(self) -> None:
        self.state = "idle"
        self.camera = Camera()
        self.lens = Lens()
        self.tilt = Tilt()
        self.uwb = UwbArray()
        self.tracker = Tracker(self.uwb, self.camera, self.lens, self.tilt)
        self.ws: websockets.WebSocketClientProtocol | None = None
        self.pan_deg = 0.0  # dead-reckoned from base telemetry, for display
        self._rec_path = ""
        self._rec_started = 0.0

    async def run(self) -> None:
        self.lens.home()
        self.uwb.start()
        while True:
            try:
                async with websockets.connect(config.SERVER_WS) as ws:
                    self.ws = ws
                    await self.send({"type": "hello", "device": "head",
                                     "caps": ["video", "tilt", "zoom", "uwb"]})
                    await asyncio.gather(self.reader(ws), self.control_loop(),
                                         self.frame_loop(), self.telemetry_loop())
            except (OSError, websockets.WebSocketException):
                self.ws = None
                await asyncio.sleep(2.0)

    async def send(self, msg: dict) -> None:
        if self.ws:
            await self.ws.send(json.dumps(msg))

    async def reader(self, ws) -> None:
        async for raw in ws:
            if isinstance(raw, bytes):
                continue
            msg = json.loads(raw)
            if msg.get("type") == "state":
                await self.apply_state(msg["state"])
            elif msg.get("type") == "shutdown":
                self.tilt.park()
                await self.send({"type": "telemetry", "note": "parked"})

    async def apply_state(self, new: str) -> None:
        old, self.state = self.state, new
        if old != "recording" and new == "recording":
            self._rec_path = self.camera.start_recording()
            self._rec_started = time.monotonic()
            print(f"[rec] → {self._rec_path}")
        elif old == "recording" and new != "recording":
            self.camera.stop_recording()
            duration = time.monotonic() - self._rec_started
            print(f"[rec] stopped ({duration:.0f}s) — uploading in background")
            asyncio.create_task(
                upload_with_retry(self._rec_path, round(duration, 1), self.send)
            )
        if new in ("idle", "off"):
            await self.send({"type": "panVel", "dps": 0.0})
            if new == "off":
                self.tilt.park()

    async def control_loop(self) -> None:
        period = 1.0 / config.UWB_RATE_HZ
        while True:
            t0 = time.monotonic()
            if self.state in ("tracking", "recording"):
                dps = self.tracker.step()
                await self.send({"type": "panVel", "dps": round(dps, 2)})
                if self.tracker.lost_for() > config.LOST_IDLE_S:
                    # server drives the transition (stops/saves recording first)
                    await self.send({"type": "lost"})
            await asyncio.sleep(max(0.0, period - (time.monotonic() - t0)))

    async def frame_loop(self) -> None:
        period = 1.0 / config.MJPEG_FPS
        while True:
            t0 = time.monotonic()
            if self.state != "off" and self.ws:
                jpg = self.camera.preview_jpeg()
                if jpg:
                    await self.send({"type": "frame"})
                    await self.ws.send(jpg)
            await asyncio.sleep(max(0.0, period - (time.monotonic() - t0)))

    async def telemetry_loop(self) -> None:
        while True:
            await self.send({
                "type": "telemetry",
                "pan": round(self.pan_deg, 1),
                "tilt": round(self.tilt.degrees, 1),
                "dist": round(self.tracker.dist_m, 2) if self.tracker.dist_m else None,
            })
            await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(Head().run())
