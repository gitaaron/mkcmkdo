"""Exercise the device's direct API against stubbed hardware.

Runs anywhere (no Pi, no camera): stubs Camera/PTZ/UWB, starts the real
aiohttp app plus the real mDNS advertiser, and drives the whole surface the
phone app uses.

    python3 device/tests/test_local_api.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import aiohttp

from sportcam import config
from sportcam.discovery import SERVICE_TYPE, Advertiser
from sportcam.local_api import LocalApi

config.RECORD_DIR = os.path.join(os.path.dirname(__file__), "_recordings")
os.makedirs(config.RECORD_DIR, exist_ok=True)
BASE = f"http://127.0.0.1:{config.LOCAL_API_PORT}"

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'' if ok else f' — {detail}'}")
    if not ok:
        failures.append(name)


class StubPtz:
    pan_deg = 0.0
    tilt_deg = 12.0
    zoom_mm = 4.0
    def park(self): pass
    def home(self): pass


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
    def step(self): return 0.0
    def lost_for(self): return 0.0


class StubHead:
    """Minimal stand-in for Head: same attributes local_api touches."""
    def __init__(self):
        self.state = "awake"
        self.ptz = StubPtz()
        self.power = StubPower()
        self.storage = StubStorage()
        self.tracker = StubTracker()
        self.session = type("StubSession", (), {"tag_present": False})()
        self.phase = None
        self.acquire_stalled = False
        self.pan_deg = 0.0
        self.tilt_deg = 0.0
        self.recorded: list[str] = []
        self.jogs: list[tuple[float, float]] = []
        self.local = LocalApi(self)

    def jog(self, pan: float, tilt: float) -> None:
        self.jogs.append((pan, tilt))

    async def apply_state(self, new: str) -> None:
        if new == "recording":
            path = os.path.join(config.RECORD_DIR, "rec_stub.mp4")
            with open(path, "wb") as f:
                f.write(b"\0" * 2048)
            self.recorded.append(path)
        self.state = new

    async def report_state(self) -> None:
        await self.local.broadcast(self.local.state_payload())


async def call(session, name, data=None):
    async with session.post(f"{BASE}/api/call/{name}", json={"data": data}) as r:
        return r.status, await r.json()


async def main() -> None:
    head = StubHead()
    runner = await head.local.start()
    mdns = Advertiser()

    try:
        async with aiohttp.ClientSession() as s:
            # --- health -------------------------------------------------
            async with s.get(f"{BASE}/api/health") as r:
                body = await r.json()
            check("health reports device backend", body.get("backend") == "device", str(body))

            # --- state machine over the direct connection ---------------
            st, body = await call(s, "getState")
            check("getState", st == 200 and body["result"]["state"] == "awake", str(body))
            check("getState reports this build's mode",
                  body["result"].get("mode") == "with_uwb", str(body))

            st, body = await call(s, "startTracking")
            check("startTracking → tracking",
                  st == 200 and body["result"]["state"] == "tracking", str(body))

            st, body = await call(s, "startRecording")
            check("startRecording → recording",
                  st == 200 and body["result"]["state"] == "recording", str(body))
            check("recording actually started", len(head.recorded) == 1)

            st, body = await call(s, "startRecording")
            check("illegal transition rejected (412)",
                  st == 412 and body["error"]["code"] == "failed-precondition", str(body))

            st, body = await call(s, "stopRecording")
            check("stopRecording → awake (the session ends)",
                  st == 200 and body["result"]["state"] == "awake", str(body))

            st, body = await call(s, "setPower", {"on": False})
            check("setPower off → sleep", st == 200 and body["result"]["state"] == "sleep", str(body))
            st, body = await call(s, "startRecording")
            check("sleep: no recording without a session (412)", st == 412, str(body))
            st, body = await call(s, "startTracking")
            check("startTracking from sleep → tracking, skipping awake (Record)",
                  st == 200 and body["result"]["state"] == "tracking", str(body))
            await call(s, "setPower", {"on": False})
            st, body = await call(s, "setPower", {"on": True})
            check("setPower on wakes it → awake (Wake up)",
                  st == 200 and body["result"]["state"] == "awake", str(body))
            st, body = await call(s, "setPower", {"on": True})
            check("…and again is a no-op", st == 200 and body["result"]["state"] == "awake", str(body))

            st, body = await call(s, "setPower", {"on": "yes"})
            check("setPower validates payload (400)",
                  st == 400 and body["error"]["code"] == "invalid-argument", str(body))

            st, body = await call(s, "nope")
            check("unknown function → 404", st == 404, str(body))

            # --- recordings --------------------------------------------
            st, body = await call(s, "getRecordings")
            names = [r["name"] for r in body["result"]["recordings"]]
            check("getRecordings lists local clip", "rec_stub.mp4" in names, str(names))

            async with s.get(f"{BASE}/api/recordings/rec_stub.mp4",
                             headers={"Range": "bytes=0-99"}) as r:
                chunk = await r.read()
            check("recording playback supports Range",
                  r.status == 206 and len(chunk) == 100, f"status={r.status} len={len(chunk)}")

            async with s.get(f"{BASE}/api/recordings/../config.py") as r:
                pass
            check("path traversal blocked", r.status in (400, 404), f"status={r.status}")

            # --- live MJPEG ---------------------------------------------
            head.local.publish_frame(b"\xff\xd8stub-jpeg\xff\xd9")

            async def read_one_frame():
                async with s.get(f"{BASE}/api/stream.mjpeg") as r:
                    assert r.status == 200
                    got = b""
                    while b"\xff\xd9" not in got:
                        got += await r.content.read(64)
                    return r.headers["Content-Type"], got

            asyncio.get_event_loop().call_later(
                0.2, lambda: head.local.publish_frame(b"\xff\xd8stub-jpeg\xff\xd9"))
            ctype, got = await asyncio.wait_for(read_one_frame(), timeout=5)
            check("MJPEG stream serves frames",
                  "multipart/x-mixed-replace" in ctype and b"stub-jpeg" in got, ctype)

            # --- websocket ----------------------------------------------
            async with s.ws_connect(f"{BASE}/ws") as ws:
                first = json.loads((await ws.receive(timeout=5)).data)
                second = json.loads((await ws.receive(timeout=5)).data)
                check("WS pushes state on connect", first["type"] == "state", str(first)[:80])
                check("WS pushes recordings on connect",
                      second["type"] == "recordings", str(second)[:80])
                await call(s, "startTracking")
                third = json.loads((await ws.receive(timeout=5)).data)
                check("WS broadcasts state change",
                      third["type"] == "state" and third["state"] == "tracking", str(third)[:80])

                # the app's joystick, over the same socket
                await ws.send_json({"type": "jog", "pan": -0.4, "tilt": 0.25})
                await ws.send_json({"type": "jog", "pan": 3, "tilt": -9})
                await ws.send_json({"type": "jog", "pan": "left", "tilt": 0})
                await ws.send_json({"type": "ping"})
                await ws.receive(timeout=5)            # the pong: the jogs before it are in
                check("WS jog reaches the head, clamped to −1…1, malformed dropped",
                      head.jogs == [(-0.4, 0.25), (1.0, -1.0)], str(head.jogs))

        # --- mDNS -------------------------------------------------------
        await mdns.start("awake")
        from zeroconf.asyncio import AsyncZeroconf
        azc = AsyncZeroconf()
        await asyncio.sleep(1.0)
        info = await azc.async_get_service_info(
            SERVICE_TYPE, f"{config.CAMERA_NAME}.{SERVICE_TYPE}", timeout=3000)
        check("mDNS service discoverable", info is not None)
        if info:
            check("mDNS advertises the API port", info.port == config.LOCAL_API_PORT, str(info.port))
            props = {k.decode(): v.decode() for k, v in info.properties.items()}
            check("mDNS TXT carries state + stream path",
                  props.get("state") == "awake" and props.get("stream") == "/api/stream.mjpeg",
                  str(props))
            await mdns.update_state("tracking")
            check("mDNS state update applied",
                  mdns._info.properties[b"state"] == b"tracking")
        await azc.async_close()
    finally:
        await mdns.stop()
        await runner.cleanup()
        for f in os.listdir(config.RECORD_DIR):
            os.remove(os.path.join(config.RECORD_DIR, f))
        os.rmdir(config.RECORD_DIR)

    print()
    if failures:
        print(f"{len(failures)} FAILED: {', '.join(failures)}")
        sys.exit(1)
    print("all direct-API checks passed")


if __name__ == "__main__":
    asyncio.run(main())
