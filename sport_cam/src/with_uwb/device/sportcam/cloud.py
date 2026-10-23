"""The camera's link to Firebase — replaces the old home-server WebSocket.

The camera keeps one Firestore document, `cameras/{CAMERA_KEY}`, up to date:
its build (`mode`), its `state`, its telemetry and a heartbeat. The apps
read that document live. When an app asks for a new state, the API function
writes it with `stateBy: "app"`; this module's listener sees that, runs it
through `Head.apply_state()` like any other command, and writes back what the
camera actually did (`stateBy: "device"`).

While an app is watching (`viewerAt` in the last minute) it also posts a
low-rate preview frame to `cameras/{CAMERA_KEY}/live/preview`, so the live
view works from anywhere without a video relay.

Writes are throttled to keep well inside Firestore's free tier: a heartbeat
every HEARTBEAT_S, telemetry with it (sooner on a phase change), previews
only while watched.

Credentials: a service-account key file (FIREBASE_CREDENTIALS) for a
service account that may only use Firestore. Against the emulator
(FIRESTORE_EMULATOR_HOST set) none is needed.

Nothing here is required for the camera to work: with no network, or no
CAMERA_KEY set, it tracks, records and serves the phone directly as before.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Callable

from . import config
from .wifi_link import BOOT_STATES, public_state

try:                                    # not installed on a bench without the cloud link
    from google.cloud import firestore
except ImportError:                     # pragma: no cover - exercised on machines without it
    firestore = None                    # type: ignore[assignment]


def make_client(project: str) -> Any:
    """A Firestore client for the real project, or the emulator if one is set."""
    if firestore is None:
        raise RuntimeError("google-cloud-firestore is not installed (pip install -r requirements.txt)")
    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        from google.auth.credentials import AnonymousCredentials
        return firestore.Client(project=project, credentials=AnonymousCredentials())
    if config.FIREBASE_CREDENTIALS:
        return firestore.Client.from_service_account_json(config.FIREBASE_CREDENTIALS, project=project)
    return firestore.Client(project=project)


def server_time() -> Any:
    return firestore.SERVER_TIMESTAMP if firestore is not None else time.time()


class CloudLink:
    def __init__(self, head: Any, client_factory: Callable[[str], Any] = make_client) -> None:
        self.head = head
        self._factory = client_factory
        self._doc: Any = None
        self._preview: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.connected = False
        self.viewer_at = 0.0             # epoch seconds of the last app "watch"
        self._telemetry: dict = {}
        self._tele_sent = 0.0
        self._tele_phase: Any = None
        self._preview_sent = 0.0
        self._upload_sent = 0.0

    @property
    def enabled(self) -> bool:
        return bool(config.CAMERA_KEY and config.FIREBASE_PROJECT)

    @property
    def watched(self) -> bool:
        return time.time() - self.viewer_at < config.VIEWER_WINDOW_S

    # ---- connection -------------------------------------------------------
    async def run(self) -> None:
        if not self.enabled:
            print("[cloud] off — set CAMERA_KEY and FIREBASE_PROJECT in config.py to use the app away from the camera")
            return
        self._loop = asyncio.get_running_loop()
        while True:
            try:
                await asyncio.to_thread(self._connect)
                print(f"[cloud] connected to {config.FIREBASE_PROJECT}")
                while True:
                    await self._beat()
                    await asyncio.sleep(config.HEARTBEAT_S)
            except Exception as err:     # noqa: BLE001 — offline at the gym is normal
                if self.connected:
                    print(f"[cloud] lost: {err}")
                self.connected = False
                await asyncio.sleep(10.0)

    def _connect(self) -> None:
        client = self._factory(config.FIREBASE_PROJECT)
        self._doc = client.collection("cameras").document(config.CAMERA_KEY)
        self._preview = self._doc.collection("live").document("preview")
        # We own our state — the tag or a lock-on may have started a session
        # while we were offline — so it goes up first, and any request an app
        # left behind is superseded.
        self._doc.set({
            "mode": config.TRACKING_MODE,
            "state": public_state(self.head.state),
            "stateBy": "device",
            "telemetry": self._telemetry,
            "deviceSeenAt": server_time(),
            "whepUrl": config.WHEP_URL,
            "upload": None,
            "warning": None,
            "updatedAt": server_time(),
        }, merge=True)
        self._doc.on_snapshot(self._on_snapshot)
        self.connected = True

    def _on_snapshot(self, docs: list, _changes: Any, _read_time: Any) -> None:
        """Runs on Firestore's listener thread: hand anything to do to the event loop."""
        for snap in docs:
            d = snap.to_dict() or {}
            seen = d.get("viewerAt")
            if seen is not None:
                self.viewer_at = seen.timestamp() if hasattr(seen, "timestamp") else float(seen)
            want = d.get("state")
            if d.get("stateBy") == "app" and want and want != self.head.state and self._loop:
                asyncio.run_coroutine_threadsafe(self._adopt(want), self._loop)

    async def _adopt(self, want: str) -> None:
        if want == self.head.state or self.head.state in BOOT_STATES:
            return                       # not up yet: nothing to adopt
        if want not in ("sleep", "awake", "tracking", "recording"):
            return                       # "off" is a boot state, never a request
        print(f"[cloud] app asked for {want}")
        await self.head.apply_state(want)
        await self.head.report_state()

    async def _write(self, ref: Any, fields: dict) -> None:
        if not self.connected or ref is None:
            return
        try:
            await asyncio.to_thread(ref.update, fields)
        except Exception as err:         # noqa: BLE001 — the heartbeat loop reconnects
            print(f"[cloud] write failed: {err}")

    async def _beat(self) -> None:
        fields: dict = {"deviceSeenAt": server_time()}
        if self._telemetry:
            fields["telemetry"] = self._telemetry
            self._tele_sent = time.monotonic()
        await self._write(self._doc, fields)

    # ---- what the head reports ------------------------------------------
    async def report_state(self, state: str) -> None:
        await self._write(self._doc, {"state": public_state(state), "stateBy": "device", "updatedAt": server_time()})

    async def telemetry(self, payload: dict) -> None:
        """Keep the latest; send it now only if the phase or the countdown
        changed (the heartbeat carries the rest)."""
        self._telemetry = {k: v for k, v in payload.items() if k != "type"}
        key = (self._telemetry.get("phase"), self._telemetry.get("countdown"))
        if key != self._tele_phase:
            self._tele_phase = key
            self._tele_sent = time.monotonic()
            await self._write(self._doc, {"telemetry": self._telemetry})

    async def preview(self, jpeg: bytes, boxes: list[list] | None = None) -> None:
        """One frame for the remote live view, with the person boxes seen in
        it (`[[x, y, w, h, label], …]` in PREVIEW_SIZE pixels). Firestore
        can't nest arrays, so each box is stored as a map."""
        now = time.monotonic()
        if not self.watched or now - self._preview_sent < 1.0 / config.PREVIEW_FPS:
            return
        if len(jpeg) > config.PREVIEW_MAX_BYTES:
            return                       # a Firestore document holds at most 1 MiB
        self._preview_sent = now
        if self.connected and self._preview is not None:
            try:
                await asyncio.to_thread(self._preview.set, {
                    "jpeg": jpeg, "at": server_time(),
                    "size": list(config.PREVIEW_SIZE),
                    "boxes": [{"x": x, "y": y, "w": w, "h": h, "label": label}
                              for x, y, w, h, label in boxes or []],
                })
            except Exception as err:     # noqa: BLE001
                print(f"[cloud] preview failed: {err}")

    async def upload_progress(self, msg: dict) -> None:
        now = time.monotonic()
        done = msg.get("sent") == msg.get("total")
        if not done and now - self._upload_sent < 2.0:
            return
        self._upload_sent = now
        # finalizeRecording clears this once the clip is in the library
        await self._write(self._doc, {"upload": {"name": msg.get("name"), "sent": msg.get("sent"),
                                                 "total": msg.get("total")}})
