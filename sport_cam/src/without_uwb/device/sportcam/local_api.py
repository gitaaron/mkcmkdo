"""Direct phone ↔ camera API (aiohttp) served by the head unit itself.

This is the second implementation of the callable protocol the Firebase
API speaks (src/backend/functions), so the app talks to both identically:

    POST /api/call/<name>          {"data": …} → {"result": …} | {"error": …}
    GET  /api/stream.mjpeg         live MJPEG (multipart/x-mixed-replace)
    GET  /api/recordings/:name     local clip, HTTP Range supported
    WS   /ws                       state + recordings broadcasts
    GET  /api/health               {"ok":true,"backend":"device", …}

Why the camera serves its own API: on gym Wi-Fi (or the camera's own
hotspot) the phone can reach the Pi directly, so live video and control work
with no internet — and at full frame rate, where the Firebase path only
carries a low-rate preview.
The Pi advertises itself over mDNS (see discovery.py) so the app finds it.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import time
from typing import Any, Awaitable, Callable

from aiohttp import WSMsgType, web

from . import config

CallableFn = Callable[[Any], Awaitable[Any]]

HTTP_BY_CODE = {
    "invalid-argument": 400,
    "not-found": 404,
    "failed-precondition": 412,
    "internal": 500,
}

TRANSITIONS = {
    "off": ["idle"],
    "idle": ["off", "tracking"],
    "tracking": ["off", "idle", "recording"],
    "recording": ["off", "idle", "tracking"],
}


class FnError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class LocalApi:
    """Serves the callable API, MJPEG stream and WS from the head unit.

    `head` is the Head supervisor; we call back into it to change state and
    to read telemetry, so the device behaves identically whether a command
    arrives from the phone directly or through Firebase.
    """

    def __init__(self, head: Any) -> None:
        self.head = head
        self._ws_clients: set[web.WebSocketResponse] = set()
        self._frame: bytes | None = None
        self._frame_seq = 0
        self._frame_event = asyncio.Event()

        self.fns: dict[str, CallableFn] = {
            "getState": self._get_state,
            "setPower": self._set_power,
            "startTracking": lambda d: self._transition("tracking"),
            "stopTracking": lambda d: self._transition("idle"),
            "startRecording": lambda d: self._transition("recording"),
            "stopRecording": lambda d: self._transition("tracking"),
            "getRecordings": self._get_recordings,
        }

    # ---- lifecycle --------------------------------------------------------
    async def start(self) -> web.AppRunner:
        app = web.Application(client_max_size=0)
        app.router.add_post("/api/call/{name}", self._handle_call)
        app.router.add_get("/api/stream.mjpeg", self._handle_mjpeg)
        app.router.add_get("/api/recordings/{name}", self._handle_recording)
        app.router.add_get("/api/health", self._handle_health)
        app.router.add_get("/ws", self._handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", config.LOCAL_API_PORT).start()
        print(f"[local-api] serving on http://0.0.0.0:{config.LOCAL_API_PORT}")
        return runner

    # ---- called by the head ----------------------------------------------
    def publish_frame(self, jpeg: bytes) -> None:
        """Newest preview frame, for /api/stream.mjpeg."""
        self._frame = jpeg
        self._frame_seq += 1
        self._frame_event.set()
        self._frame_event.clear()

    async def broadcast(self, msg: dict) -> None:
        """Push a message to every connected app client."""
        dead = []
        for ws in self._ws_clients:
            try:
                await ws.send_json(msg)
            except (ConnectionResetError, RuntimeError):
                dead.append(ws)
        for ws in dead:
            self._ws_clients.discard(ws)

    def state_payload(self) -> dict:
        return {
            "type": "state",
            "mode": config.TRACKING_MODE,
            "state": self.head.state,
            "telemetry": {
                "pan": round(self.head.pan_deg, 1),
                "tilt": round(self.head.tilt_deg, 1),
                "dist": round(self.head.tracker.dist_m, 2) if self.head.tracker.dist_m else None,
                "phase": self.head.phase,
                "centred": self.head.tracker.centred if self.head.state in ("tracking", "recording") else 0,
                "acquireStalled": self.head.acquire_stalled,
                **self.head.power.telemetry(),
                **self.head.storage.telemetry(),
            },
            "deviceOnline": True,        # you're talking to the device itself
            "whepUrl": config.WHEP_URL,  # None unless MediaMTX is running
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    # ---- callables --------------------------------------------------------
    async def _get_state(self, _data: Any) -> dict:
        return {k: v for k, v in self.state_payload().items() if k != "type"}

    async def _set_power(self, data: Any) -> dict:
        if not isinstance(data, dict) or not isinstance(data.get("on"), bool):
            raise FnError("invalid-argument", "expected { on: boolean }")
        target = "idle" if data["on"] else "off"
        if self.head.state == target or (data["on"] and self.head.state != "off"):
            return await self._get_state(None)
        return await self._transition(target)

    async def _transition(self, target: str) -> dict:
        if target not in TRANSITIONS[self.head.state]:
            raise FnError("failed-precondition",
                          f"cannot go from '{self.head.state}' to '{target}'")
        await self.head.apply_state(target)
        await self.head.report_state()
        return await self._get_state(None)

    async def _get_recordings(self, _data: Any) -> dict:
        """Clips still on the Pi (i.e. not yet uploaded and deleted)."""
        out = []
        if os.path.isdir(config.RECORD_DIR):
            for name in sorted(os.listdir(config.RECORD_DIR), reverse=True):
                if not name.endswith(".mp4"):
                    continue
                st = os.stat(os.path.join(config.RECORD_DIR, name))
                out.append({
                    "name": name,
                    "bytes": st.st_size,
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime)),
                    "durationS": None,
                    "url": f"/api/recordings/{name}",
                })
        return {"recordings": out}

    # ---- HTTP handlers ----------------------------------------------------
    async def _handle_call(self, req: web.Request) -> web.Response:
        name = req.match_info["name"]
        fn = self.fns.get(name)
        if fn is None:
            return web.json_response(
                {"error": {"code": "not-found", "message": f"no function '{name}'"}}, status=404)
        try:
            body = await req.json() if req.can_read_body else {}
            return web.json_response({"result": await fn(body.get("data"))})
        except FnError as err:
            return web.json_response({"error": {"code": err.code, "message": err.message}},
                                     status=HTTP_BY_CODE.get(err.code, 500))
        except Exception as err:  # noqa: BLE001
            print(f"[local-api] {name} failed: {err}")
            return web.json_response(
                {"error": {"code": "internal", "message": "internal error"}}, status=500)

    async def _handle_health(self, _req: web.Request) -> web.Response:
        return web.json_response({"ok": True, "backend": "device",
                                  "state": self.head.state, "name": config.CAMERA_NAME})

    async def _handle_mjpeg(self, req: web.Request) -> web.StreamResponse:
        boundary = "sportcamframe"
        resp = web.StreamResponse(headers={
            "Content-Type": f"multipart/x-mixed-replace; boundary={boundary}",
            "Cache-Control": "no-store",
        })
        await resp.prepare(req)
        last = -1
        try:
            while True:
                if self._frame is not None and self._frame_seq != last:
                    last = self._frame_seq
                    frame = self._frame
                    await resp.write(
                        f"--{boundary}\r\nContent-Type: image/jpeg\r\n"
                        f"Content-Length: {len(frame)}\r\n\r\n".encode())
                    await resp.write(frame)
                    await resp.write(b"\r\n")
                await asyncio.wait_for(self._frame_event.wait(), timeout=5.0)
        except (asyncio.TimeoutError, ConnectionResetError, asyncio.CancelledError):
            pass
        return resp

    async def _handle_recording(self, req: web.Request) -> web.StreamResponse:
        name = req.match_info["name"]
        if "/" in name or ".." in name or not name.endswith(".mp4"):
            return web.json_response(
                {"error": {"code": "invalid-argument", "message": "bad name"}}, status=400)
        path = os.path.join(config.RECORD_DIR, name)
        if not os.path.isfile(path):
            return web.json_response(
                {"error": {"code": "not-found", "message": "no such recording"}}, status=404)
        # FileResponse implements Range/If-Range — phones need it to seek.
        return web.FileResponse(path, headers={"Content-Type": "video/mp4"})

    async def _handle_ws(self, req: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(req)
        self._ws_clients.add(ws)
        await ws.send_json(self.state_payload())
        await ws.send_json({"type": "recordings", **(await self._get_recordings(None))})
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue
                    if data.get("type") == "ping":
                        await ws.send_json({"type": "pong"})
        finally:
            self._ws_clients.discard(ws)
        return ws
