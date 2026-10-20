"""The Firebase link (cloud.py), against an in-memory Firestore.

Checks what the apps depend on: the camera's document goes up on connect,
an app's request is adopted through Head.apply_state() and the result written
back, previews flow only while someone watches, and writes stay throttled.

    python3 device/tests/test_cloud.py

To run the same link against the real emulator instead, start
`npm run dev` at the repo root and run with FIRESTORE_EMULATOR_HOST set
(docs/appendix/appendix-c-development.md shows how).
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import cloud, config

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


class FakeSnap:
    def __init__(self, d: dict) -> None:
        self._d = d

    def to_dict(self) -> dict:
        return dict(self._d)


class FakeDoc:
    def __init__(self, store: dict, path: str) -> None:
        self.store, self.path = store, path
        self.listeners: list = []
        self.writes = 0

    def collection(self, name: str) -> "FakeCol":
        return FakeCol(self.store, f"{self.path}/{name}")

    def set(self, data: dict, merge: bool = False) -> None:
        self.writes += 1
        cur = self.store.get(self.path, {}) if merge else {}
        self.store[self.path] = {**cur, **data}
        self._fire()

    def update(self, data: dict) -> None:
        self.writes += 1
        self.store[self.path] = {**self.store.get(self.path, {}), **data}
        self._fire()

    def on_snapshot(self, fn) -> None:
        self.listeners.append(fn)
        self._fire()

    def _fire(self) -> None:
        for fn in self.listeners:
            fn([FakeSnap(self.store.get(self.path, {}))], None, None)


class FakeCol:
    docs: dict = {}

    def __init__(self, store: dict, path: str) -> None:
        self.store, self.path = store, path

    def document(self, name: str) -> FakeDoc:
        key = f"{self.path}/{name}"
        return FakeCol.docs.setdefault(key, FakeDoc(self.store, key))


class FakeClient:
    def __init__(self) -> None:
        self.store: dict = {}

    def collection(self, name: str) -> FakeCol:
        return FakeCol(self.store, name)


class FakeHead:
    def __init__(self) -> None:
        self.state = "idle"
        self.applied: list[str] = []
        self.link: cloud.CloudLink | None = None
        self.refuse_recording = False

    async def apply_state(self, new: str) -> None:
        if new == "recording" and self.refuse_recording:   # e.g. the card is full
            new = "tracking"
        self.applied.append(new)
        self.state = new

    async def report_state(self) -> None:
        await self.link.report_state(self.state)


async def main() -> None:
    config.FIREBASE_PROJECT, config.CAMERA_KEY = "demo-sportcam", "test-camera-key"
    config.HEARTBEAT_S = 0.05
    client = FakeClient()
    head = FakeHead()
    link = cloud.CloudLink(head, client_factory=lambda _p: client)
    head.link = link
    doc_path = "cameras/test-camera-key"
    doc = lambda: client.store.get(doc_path, {})      # noqa: E731

    print("connect")
    task = asyncio.create_task(link.run())
    for _ in range(50):
        if link.connected:
            break
        await asyncio.sleep(0.02)
    check("connects", link.connected)
    check("writes mode, state and a heartbeat", doc().get("mode") == config.TRACKING_MODE
          and doc().get("state") == "idle" and doc().get("stateBy") == "device"
          and "deviceSeenAt" in doc(), str(doc()))

    print("commands from the app")
    the_doc = FakeCol.docs[doc_path]
    the_doc.update({"state": "tracking", "stateBy": "app"})
    await asyncio.sleep(0.1)
    check("adopts the app's request", head.applied == ["tracking"], str(head.applied))
    check("writes back what it did", doc().get("state") == "tracking" and doc().get("stateBy") == "device",
          str(doc()))
    head.refuse_recording = True
    the_doc.update({"state": "recording", "stateBy": "app"})
    await asyncio.sleep(0.1)
    check("a refused request is corrected in the document", doc().get("state") == "tracking"
          and doc().get("stateBy") == "device", str(doc()))
    before = list(head.applied)
    the_doc.update({"state": "idle", "stateBy": "device"})
    await asyncio.sleep(0.1)
    check("ignores its own writes", head.applied == before, str(head.applied))

    print("telemetry and heartbeat")
    await link.telemetry({"type": "telemetry", "pan": 3.0, "phase": "acquiring"})
    check("a phase change goes up at once", doc().get("telemetry", {}).get("phase") == "acquiring")
    await asyncio.sleep(0.15)
    check("the heartbeat carries telemetry", doc().get("telemetry", {}).get("pan") == 3.0)

    print("preview")
    preview = lambda: client.store.get(f"{doc_path}/live/preview")   # noqa: E731
    await link.preview(b"\xff\xd8jpeg")
    check("no preview while nobody watches", preview() is None)
    the_doc.update({"viewerAt": time.time()})
    await asyncio.sleep(0.05)
    await link.preview(b"\xff\xd8one")
    check("posts a preview while watched", preview() is not None and preview()["jpeg"] == b"\xff\xd8one")
    await link.preview(b"\xff\xd8two")
    check("previews are rate-limited", preview()["jpeg"] == b"\xff\xd8one")
    await link.preview(b"x" * (config.PREVIEW_MAX_BYTES + 1))
    check("oversized frames are skipped", preview()["jpeg"] == b"\xff\xd8one")

    print("upload progress")
    writes = the_doc.writes
    await link.upload_progress({"name": "a.mp4", "sent": 1, "total": 10})
    await link.upload_progress({"name": "a.mp4", "sent": 2, "total": 10})
    await link.upload_progress({"name": "a.mp4", "sent": 10, "total": 10})
    check("throttled, but the last one always goes", doc().get("upload") == {"name": "a.mp4", "sent": 10, "total": 10}
          and the_doc.writes - writes <= 3, f"{the_doc.writes - writes} writes")

    task.cancel()

    print("stand-alone")
    config.CAMERA_KEY = ""
    off = cloud.CloudLink(FakeHead(), client_factory=lambda _p: (_ for _ in ()).throw(AssertionError("connected")))
    await off.run()
    check("does nothing without a camera key", not off.connected)


asyncio.run(main())
print("\nall passed" if not failures else f"\n{len(failures)} FAILED: {failures}")
sys.exit(1 if failures else 0)
