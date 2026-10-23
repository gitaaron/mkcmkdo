"""Run the device's direct API against stubbed hardware, and keep it up.

Lets you drive the real camera protocol with no Pi — used by the Flutter
app's contract check (src/app_flutter/tool/verify_against_device.dart) and handy
for poking at the API by hand:

    python3 device/tests/stub_device.py
    curl -s localhost:8787/api/health
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config  # noqa: E402
from sportcam.discovery import Advertiser  # noqa: E402
from sportcam.local_api import LocalApi  # noqa: E402

config.RECORD_DIR = os.path.join(os.path.dirname(__file__), "_stub_recordings")
os.makedirs(config.RECORD_DIR, exist_ok=True)


class StubPtz:
    pan_deg = 0.0
    tilt_deg = 12.0
    zoom_mm = 4.0

    def park(self):
        pass

    def home(self):
        pass


class StubPower:
    def telemetry(self):
        return {"battery": 0.82, "batteryWatts": 10.9,
                "batteryMinutes": 420, "batteryLevel": "ok"}


class StubStorage:
    def telemetry(self):
        return {"storageFreeGb": 48.2, "storageMinutes": 535,
                "storageLevel": "ok", "pendingUploads": 0}

    def can_record(self):
        return True

    def sample(self):
        pass


class StubTracker:
    dist_m = 4.2
    countdown = 0

    def step(self):
        return 0.0

    def lost_for(self):
        return 0.0


class StubSession:
    tag_present = False


class StubHead:
    def __init__(self):
        self.state = "awake"
        self.ptz = StubPtz()
        self.power = StubPower()
        self.storage = StubStorage()
        self.tracker = StubTracker()
        self.session = StubSession()
        self.phase = None
        self.acquire_stalled = False
        self.pan_deg = 0.0
        self.tilt_deg = 0.0
        self.local = LocalApi(self)

    def jog(self, pan: float, tilt: float) -> None:
        print(f"[stub] jog pan {pan:+.2f} tilt {tilt:+.2f}")

    async def apply_state(self, new: str) -> None:
        if new == "recording":
            with open(os.path.join(config.RECORD_DIR, "rec_stub.mp4"), "wb") as f:
                f.write(b"\0" * 4096)
        self.state = new

    async def report_state(self) -> None:
        await self.local.broadcast(self.local.state_payload())


async def main() -> None:
    head = StubHead()
    await head.local.start()
    mdns = Advertiser()
    await mdns.start(head.state)

    # keep a frame flowing so /api/stream.mjpeg has something to serve
    async def frames():
        while True:
            head.local.publish_frame(b"\xff\xd8stub-jpeg-frame\xff\xd9")
            await asyncio.sleep(1 / 15)

    print(f"[stub] device API on http://127.0.0.1:{config.LOCAL_API_PORT}")
    try:
        await frames()
    finally:
        await mdns.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
