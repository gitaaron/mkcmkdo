"""SD-card guard and pending-upload retry, checked without a Pi or a backend.

The card is a buffer: clips are deleted only once the backend confirms them,
so anything that breaks uploads makes files pile up. These cover the two
safeguards that stop that ending in a truncated recording.

    python3 device/tests/test_storage.py
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config, storage, uploader

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
    shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all storage checks passed")


if __name__ == "__main__":
    main()
