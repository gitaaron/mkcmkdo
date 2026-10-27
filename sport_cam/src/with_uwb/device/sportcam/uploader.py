"""Background recording uploader.

After a recording stops, pushes the finished MP4 to the recording backend and
(on confirmation) deletes the local copy — the Pi's SD card is a buffer, not
a store. Talks to the Firebase API (config.UPLOAD_API_BASE,
"https://<project>.web.app"), naming this camera with config.CAMERA_KEY.

Flow:  createUploadUrl → PUT file (chunked, with progress) → the same for its
       person boxes (`<clip>.boxes.json`, boxlog.py), if any → finalizeRecording

The PUT goes straight to Cloud Storage on a signed URL; under the emulator
the URL is relative and points back at the API.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Awaitable, Callable

import aiohttp

from . import config
from .boxlog import sidecar
from .storage import pending_files

ProgressFn = Callable[[dict], Awaitable[None]]

# Clips being uploaded right now. A clip still in its retry ladder is also on
# the card, so drain_pending would otherwise send it a second time alongside
# — and the first to finish deletes the file under the other.
_uploading: set[str] = set()

CHUNK = 256 * 1024


async def _call(session: aiohttp.ClientSession, name: str, data: dict) -> dict:
    async with session.post(
        f"{config.UPLOAD_API_BASE}/api/call/{name}",
        json={"data": data},
        headers={"X-Camera-Key": config.CAMERA_KEY},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        body = await resp.json()
        if resp.status != 200:
            raise RuntimeError(f"{name}: {body.get('error', {}).get('message', resp.status)}")
        return body["result"]


async def _put(session: aiohttp.ClientSession, path: str,
               progress: ProgressFn | None) -> None:
    """PUT one file to the URL the backend signs for it."""
    name = os.path.basename(path)
    total = os.path.getsize(path)
    target = await _call(session, "createUploadUrl", {"name": name})
    url = target["url"]
    if url.startswith("/"):
        url = config.UPLOAD_API_BASE + url

    sent = 0
    last_report = 0.0

    async def body():
        nonlocal sent, last_report
        with open(path, "rb") as f:
            while chunk := f.read(CHUNK):
                yield chunk
                sent += len(chunk)
                now = asyncio.get_event_loop().time()
                if progress and (now - last_report > 1.0 or sent == total):
                    last_report = now
                    await progress({"type": "uploadProgress", "name": name,
                                    "sent": sent, "total": total})

    async with session.request(
        target.get("method", "PUT"), url, data=body(),
        headers={**target.get("headers", {}), "Content-Length": str(total)},
        timeout=aiohttp.ClientTimeout(total=3600),
    ) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f"upload HTTP {resp.status}: {(await resp.text())[:200]}")


async def upload_recording(path: str, duration_s: float | None, progress: ProgressFn) -> None:
    """Upload one clip and its boxes; reports {"type":"uploadProgress",...} via `progress`."""
    if not (config.UPLOAD_API_BASE and config.CAMERA_KEY):
        raise RuntimeError("no recording backend set (UPLOAD_API_BASE, CAMERA_KEY) — kept on the card")
    name = os.path.basename(path)
    total = os.path.getsize(path)
    boxes = sidecar(path)
    has_boxes = os.path.exists(boxes)

    async with aiohttp.ClientSession() as session:
        await _put(session, path, progress)
        if has_boxes:
            await _put(session, boxes, None)
        meta = await _call(session, "finalizeRecording",
                           {"name": name, "bytes": total, "durationS": duration_s,
                            "boxes": has_boxes})
        print(f"[upload] confirmed: {json.dumps(meta)[:120]}")

    if config.DELETE_AFTER_UPLOAD:
        os.remove(path)
        if has_boxes:
            os.remove(boxes)
        print(f"[upload] local copy removed: {path}")


async def upload_with_retry(path: str, duration_s: float | None, progress: ProgressFn) -> None:
    """Retry with backoff — gym Wi-Fi drops, uploads must survive it."""
    if path in _uploading:
        return
    _uploading.add(path)
    try:
        delay = 5.0
        for attempt in range(8):
            try:
                await upload_recording(path, duration_s, progress)
                return
            except Exception as err:  # noqa: BLE001 — any failure → retry
                print(f"[upload] attempt {attempt + 1} failed: {err}; retry in {delay:.0f}s")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 300)
        print(f"[upload] giving up on {path} — kept locally, will retry later")
    finally:
        _uploading.discard(path)


async def drain_pending(progress: ProgressFn, exclude: str | None = None) -> int:
    """Upload everything still sitting on the card, oldest first.

    Called once at start-up and then on `UPLOAD_RETRY_INTERVAL_S`. Anything
    here either failed its retry ladder or was interrupted by a restart, and
    nothing else would ever pick it up again — that is how a card fills.

    Oldest first matters: if space is tight, clearing the oldest clip frees
    the card soonest for whatever is being filmed now.
    """
    files = [p for p in pending_files() if p != exclude and p not in _uploading]
    if not files:
        return 0
    print(f"[upload] {len(files)} recording(s) pending")
    done = 0
    for path in files:
        if path in _uploading or not os.path.exists(path):   # another upload has it
            continue
        _uploading.add(path)
        try:
            await upload_recording(path, None, progress)
            done += 1
        except Exception as err:              # noqa: BLE001 — try the rest
            print(f"[upload] still cannot send {os.path.basename(path)}: {err}")
            break                             # backend is down; stop hammering
        finally:
            _uploading.discard(path)
    return done
