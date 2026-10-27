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
from sportcam import owners
from sportcam.local_api import LocalApi
from sportcam.pairing import Pairings

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


class StubUwb:
    def __init__(self):
        self.on: list[int] = []          # tags switched on

    def tag_ages(self):
        return {t: 0.1 for t in self.on}


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
        self.session_hash = None
        self.uwb = StubUwb()
        self.pairings = Pairings(os.path.join(config.RECORD_DIR, "pairings.json"))
        self.local = LocalApi(self)

    def jog(self, pan: float, tilt: float) -> None:
        self.jogs.append((pan, tilt))

    async def apply_state(self, new: str) -> None:
        if new not in ("tracking", "recording"):
            self.session_hash = None
        if new == "recording":
            path = os.path.join(config.RECORD_DIR, "rec_stub.mp4")
            with open(path, "wb") as f:
                f.write(b"\0" * 2048)
            owners.stamp(path, self.session_hash)
            self.recorded.append(path)
        self.state = new

    async def start_session(self, target: str, session_hash) -> None:
        self.session_hash = session_hash
        await self.apply_state(target)

    def session_secret(self, pairing=None) -> str:
        if owners.is_secret(pairing) and self.pairings.tag_for(owners.hash_secret(pairing)) is not None:
            return pairing
        return owners.new_secret()

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
            secret = body["result"].get("sessionSecret", "")
            mine = {"secrets": [secret]}
            check("…handing this phone the session's secret, and everyone its hash",
                  owners.is_secret(secret)
                  and body["result"]["sessionHash"] == owners.hash_secret(secret), str(body))

            st, body = await call(s, "startRecording")
            check("another phone can't advance someone's session (403)",
                  st == 403 and body["error"]["code"] == "permission-denied", str(body))
            st, body = await call(s, "startRecording", mine)
            check("startRecording → recording",
                  st == 200 and body["result"]["state"] == "recording", str(body))
            check("recording actually started", len(head.recorded) == 1)
            check("…stamped with its session's owner",
                  owners.owner_of(head.recorded[0]) == owners.hash_secret(secret))

            st, body = await call(s, "startRecording", mine)
            check("illegal transition rejected (412)",
                  st == 412 and body["error"]["code"] == "failed-precondition", str(body))

            for fn, data in (("stopRecording", {}), ("stopTracking", {}), ("setPower", {"on": False})):
                st, body = await call(s, fn, {**data, "secrets": ["someone-elses-secret-0123"]})
                check(f"nobody else can stop it: {fn} (403)", st == 403, str(body))
            st, body = await call(s, "stopRecording", {"secrets": ["another-of-mine-0123456", secret]})
            check("stopRecording with its secret → awake (the session ends)",
                  st == 200 and body["result"]["state"] == "awake"
                  and body["result"]["sessionHash"] is None, str(body))

            st, body = await call(s, "setPower", {"on": False})
            check("setPower off → sleep", st == 200 and body["result"]["state"] == "sleep", str(body))
            st, body = await call(s, "startRecording")
            check("sleep: no recording without a session (412)", st == 412, str(body))
            st, body = await call(s, "startTracking")
            check("startTracking from sleep → tracking, skipping awake (Record)",
                  st == 200 and body["result"]["state"] == "tracking", str(body))
            second = {"secrets": [body["result"]["sessionSecret"]]}
            st, body = await call(s, "setPower", {"on": False})
            check("Sleep stops a session only for its owner (403)", st == 403, str(body))
            st, body = await call(s, "setPower", {"on": False, **second})
            check("…who can", st == 200 and body["result"]["state"] == "sleep", str(body))
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

            # --- pairing a tag ------------------------------------------
            st, body = await call(s, "pairTag")
            check("pairTag with no tag on → 412", st == 412, str(body))
            head.uwb.on = [2, 5]
            st, body = await call(s, "pairTag")
            check("pairTag with two tags on → 412, saying so", st == 412 and "2 tags" in body["error"]["message"],
                  str(body))
            head.uwb.on = [5]
            st, body = await call(s, "pairTag")
            pairing = body.get("result", {}).get("pairingSecret", "")
            check("pairTag pairs the one tag on, and hands this phone its secret",
                  st == 200 and body["result"]["tag"] == 5 and owners.is_secret(pairing)
                  and head.pairings.hash_for(5) == owners.hash_secret(pairing), str(body))
            check("…kept across a restart",
                  Pairings(head.pairings.path).hash_for(5) == owners.hash_secret(pairing))
            st, body = await call(s, "startTracking", {"pairing": pairing})
            check("a phone with a paired tag starts its session with the pairing secret",
                  st == 200 and body["result"].get("sessionSecret") == pairing, str(body))
            await call(s, "stopTracking", {"secrets": [pairing]})
            st, body = await call(s, "startTracking", {"pairing": "not-a-pairing-secret-0123"})
            check("…and one that isn't a pairing gets a fresh secret",
                  st == 200 and body["result"].get("sessionSecret") not in ("", "not-a-pairing-secret-0123"),
                  str(body))
            await call(s, "stopTracking", {"secrets": [body["result"]["sessionSecret"]]})
            head.uwb.on = []

            # --- recordings --------------------------------------------
            st, body = await call(s, "getRecordings")
            check("getRecordings shows nobody else's clips", body["result"]["recordings"] == [], str(body))
            st, body = await call(s, "getRecordings", mine)
            names = [r["name"] for r in body["result"]["recordings"]]
            check("getRecordings lists the caller's local clip", names == ["rec_stub.mp4"], str(names))

            async with s.get(f"{BASE}/api/recordings/rec_stub.mp4",
                             headers={"Range": "bytes=0-99", "X-Session-Secrets": secret}) as r:
                chunk = await r.read()
            check("recording playback supports Range",
                  r.status == 206 and len(chunk) == 100, f"status={r.status} len={len(chunk)}")
            for headers in ({}, {"X-Session-Secrets": "someone-elses-secret-0123"}):
                async with s.get(f"{BASE}/api/recordings/rec_stub.mp4", headers=headers) as r:
                    pass
                check(f"…but not to a phone without its secret ({headers or 'none'})", r.status == 404,
                      f"status={r.status}")

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
                check("WS pushes state on connect", first["type"] == "state", str(first)[:80])
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

    # A client connecting or dropping while a broadcast is mid-send changes
    # the set being sent to; that must not escape into the caller (the
    # control loop).
    api = LocalApi(head=None)

    class Client:
        def __init__(self, on_send=None):
            self.got, self.on_send = [], on_send

        async def send_json(self, msg):
            await asyncio.sleep(0)
            self.got.append(msg)
            if self.on_send:
                self.on_send()

    late = Client()
    first = Client(on_send=lambda: api._ws_clients.add(late))
    api._ws_clients.update({first, Client(on_send=lambda: api._ws_clients.discard(first))})
    try:
        await api.broadcast({"type": "state"})
        ok, err = True, ""
    except RuntimeError as e:
        ok, err = False, str(e)
    check("a client joining or leaving mid-broadcast doesn't break it", ok, err)

    print()
    if failures:
        print(f"{len(failures)} FAILED: {', '.join(failures)}")
        sys.exit(1)
    print("all direct-API checks passed")


if __name__ == "__main__":
    asyncio.run(main())
