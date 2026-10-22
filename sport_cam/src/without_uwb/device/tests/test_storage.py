"""SD-card guard and pending-upload retry, checked without a Pi or a backend.

The card is a buffer: clips are deleted only once the backend confirms them,
so anything that breaks uploads makes files pile up. These cover the two
safeguards that stop that ending in a truncated recording.

    python3 device/tests/test_storage.py
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aiohttp import web

from sportcam import boxlog, config, storage, uploader

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def make_clip(d: str, name: str, mb: int = 1, age_s: float = 0.0) -> str:
    p = os.path.join(d, name)
    with open(p, "wb") as f:
        f.write(b"\0" * (mb * 1_000_000))
    if age_s:
        t = time.time() - age_s
        os.utime(p, (t, t))
    return p


def main() -> None:
    print("storage checks\n")
    tmp = tempfile.mkdtemp()
    config.RECORD_DIR = tmp

    mon = storage.StorageMonitor(tmp)

    # ---- 1. minutes-left maths agrees with the encoder bitrate ------------
    per_min = config.RECORD_BITRATE / 8 * 60
    mon.free_bytes = int(config.STORAGE_RESERVE_MB * 1_000_000 + per_min * 30)
    check("30 min of space reads as 30 min", abs(mon.minutes_left - 30) < 0.5,
          f"{mon.minutes_left:.1f}")

    # ---- 2. the reserve is never counted as recordable --------------------
    mon.free_bytes = config.STORAGE_RESERVE_MB * 1_000_000
    check("reserve alone leaves zero minutes", mon.minutes_left == 0,
          f"{mon.minutes_left:.2f}")
    mon.free_bytes = 0
    check("an empty card does not go negative", mon.minutes_left == 0)

    # ---- 3. thresholds ----------------------------------------------------
    def at(minutes: float) -> str:
        mon.free_bytes = int(config.STORAGE_RESERVE_MB * 1_000_000 + per_min * minutes)
        return mon.level()

    check("plenty of space → ok", at(60) == "ok", at(60))
    check("below the low mark → low", at(config.STORAGE_LOW_MIN - 1) == "low")
    check("below the critical mark → critical", at(config.STORAGE_CRITICAL_MIN - 1) == "critical")
    check("critical blocks recording", (at(1), mon.can_record()) == ("critical", False))
    check("low still allows recording", (at(config.STORAGE_LOW_MIN - 1), mon.can_record()) == ("low", True))
    check("telemetry reports the level", at(1) == "critical" and
          mon.telemetry()["storageLevel"] == "critical")

    # ---- 4. pending files -------------------------------------------------
    old = make_clip(tmp, "rec_old.mp4", age_s=600)
    new = make_clip(tmp, "rec_new.mp4", age_s=10)
    make_clip(tmp, "notes.txt")
    found = storage.pending_files(tmp)
    check("only mp4s are counted", len(found) == 2, f"{[os.path.basename(f) for f in found]}")
    check("oldest first", found == [old, new],
          f"{[os.path.basename(f) for f in found]}")

    # ---- 5. the drain uploads oldest first and skips the open file --------
    sent: list[str] = []

    async def fake_upload(path, duration_s, progress):
        sent.append(os.path.basename(path))
        os.remove(path)

    real, uploader.upload_recording = uploader.upload_recording, fake_upload

    async def noop(_msg):
        return None

    n = asyncio.run(uploader.drain_pending(noop, exclude=new))
    check("the file being recorded is skipped", sent == ["rec_old.mp4"], f"{sent}")
    check("drain reports what it sent", n == 1, f"{n}")
    check("skipped file is still on the card", os.path.exists(new))

    # ---- 6. a dead backend stops the drain rather than hammering ----------
    sent.clear()
    make_clip(tmp, "rec_a.mp4", age_s=300)
    make_clip(tmp, "rec_b.mp4", age_s=200)
    attempts = {"n": 0}

    async def failing_upload(path, duration_s, progress):
        attempts["n"] += 1
        raise RuntimeError("backend down")

    uploader.upload_recording = failing_upload
    n = asyncio.run(uploader.drain_pending(noop))
    check("a failing backend stops after one attempt", attempts["n"] == 1, f"{attempts['n']}")
    check("nothing is reported as sent", n == 0, f"{n}")
    check("files survive a failed drain", len(storage.pending_files(tmp)) == 3)

    # ---- 7. an empty card is a no-op --------------------------------------
    uploader.upload_recording = fake_upload
    for f in storage.pending_files(tmp):
        os.remove(f)
    check("empty card → nothing to do", asyncio.run(uploader.drain_pending(noop)) == 0)

    uploader.upload_recording = real

    # ---- 8. the person boxes are written beside the clip -------------------
    clip = make_clip(tmp, "rec_boxes.mp4")
    log = boxlog.BoxLog()
    log.start(clip, started=100.0)
    log.note(100.5, [((10, 20, 30, 90), boxlog.CLIMBER), ((300, 20, 30, 90), boxlog.OTHER)])
    log.note(100.5, [((10, 20, 30, 90), boxlog.CLIMBER)])      # the same detection again
    log.note(100.9, [])
    side = log.stop()
    doc = json.load(open(side)) if side else {}
    check("boxes are saved as <clip>.boxes.json",
          side == os.path.join(tmp, "rec_boxes.boxes.json"), f"{side}")
    check("…one frame per detection, timed from the clip's start, labels kept",
          doc.get("frames") == [[0.5, [[10, 20, 30, 90, "climber"], [300, 20, 30, 90, "other"]]],
                                [0.9, []]], f"{doc.get('frames')}")
    check("…with the frame size the boxes are measured in",
          doc.get("size") == list(config.PREVIEW_SIZE) and doc.get("v") == 1)
    check("nothing recording → nothing written", boxlog.BoxLog().stop() is None)

    # ---- 9. the clip and its boxes upload together -------------------------
    got: dict[str, object] = {}

    async def call(req: web.Request) -> web.Response:
        data = (await req.json())["data"]
        if req.match_info["fn"] == "createUploadUrl":
            return web.json_response({"result": {"url": f"/put/{data['name']}", "method": "PUT"}})
        got["finalize"] = data
        return web.json_response({"result": {"name": data["name"]}})

    async def put(req: web.Request) -> web.Response:
        got[req.match_info["name"]] = len(await req.read())
        return web.json_response({})

    async def run_upload() -> None:
        app = web.Application()
        app.router.add_post("/api/call/{fn}", call)
        app.router.add_put("/put/{name}", put)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        base, key, keep = config.UPLOAD_API_BASE, config.CAMERA_KEY, config.DELETE_AFTER_UPLOAD
        config.UPLOAD_API_BASE, config.CAMERA_KEY = f"http://127.0.0.1:{port}", "k"
        config.DELETE_AFTER_UPLOAD = True
        try:
            await uploader.upload_recording(clip, 12.0, noop)
        finally:
            config.UPLOAD_API_BASE, config.CAMERA_KEY, config.DELETE_AFTER_UPLOAD = base, key, keep
            await runner.cleanup()

    asyncio.run(run_upload())
    check("the clip and its boxes are both uploaded",
          got.get("rec_boxes.mp4") == 1_000_000 and got.get("rec_boxes.boxes.json", 0) > 0,
          f"{list(got)}")
    check("…and the backend is told the clip has boxes",
          isinstance(got.get("finalize"), dict) and got["finalize"].get("boxes") is True,
          f"{got.get('finalize')}")
    check("…and both leave the card once confirmed",
          not os.path.exists(clip) and not os.path.exists(side or ""))

    shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all storage checks passed")


if __name__ == "__main__":
    main()
