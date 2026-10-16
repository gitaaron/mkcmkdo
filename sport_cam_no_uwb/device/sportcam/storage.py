"""SD-card space monitoring.

The card is a buffer, not a store: clips upload in the background and are
deleted once the backend confirms the byte count. That works until something
breaks the upload path — a gym with no backend, a server that is down — and
then files accumulate with nothing to stop them.

This module gives storage the same treatment the battery already gets in
`power.py`: a measurement, two thresholds, and an automatic save-and-stop
before the resource runs out. Without it a full card simply fails the encoder
mid-write and leaves a truncated clip with no warning anywhere.

Space is expressed in **minutes of recording left**, because that is the unit
the decision is actually in. A reserve is held back so the operating system
never hits zero, which corrupts filesystems.
"""
from __future__ import annotations

import os
import shutil

from . import config


class StorageMonitor:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or config.RECORD_DIR
        os.makedirs(self.path, exist_ok=True)
        self.free_bytes = 0
        self.total_bytes = 0
        self.pending = 0
        self.sample()

    # ---- measurement ------------------------------------------------------
    def sample(self) -> None:
        try:
            usage = shutil.disk_usage(self.path)
            self.total_bytes, self.free_bytes = usage.total, usage.free
        except OSError:
            return
        self.pending = len(pending_files(self.path))

    @property
    def usable_bytes(self) -> int:
        """Free space we are willing to spend on video."""
        return max(0, self.free_bytes - config.STORAGE_RESERVE_MB * 1_000_000)

    @property
    def minutes_left(self) -> float:
        bytes_per_min = config.RECORD_BITRATE / 8 * 60
        return self.usable_bytes / bytes_per_min if bytes_per_min else 0.0

    def level(self) -> str:
        """`ok`, `low` or `critical` — mirrors PowerMonitor.level()."""
        mins = self.minutes_left
        if mins <= config.STORAGE_CRITICAL_MIN:
            return "critical"
        if mins <= config.STORAGE_LOW_MIN:
            return "low"
        return "ok"

    def can_record(self) -> bool:
        return self.level() != "critical"

    def telemetry(self) -> dict:
        return {
            "storageFreeGb": round(self.free_bytes / 1e9, 2),
            "storageMinutes": round(self.minutes_left),
            "storageLevel": self.level(),
            "pendingUploads": self.pending,
        }


def pending_files(path: str | None = None) -> list[str]:
    """Recordings still on the card, oldest first.

    With `DELETE_AFTER_UPLOAD` on, anything left here either failed to upload
    or was never attempted because the service restarted mid-flight. Both are
    retried; see `uploader.drain_pending`.
    """
    path = path or config.RECORD_DIR
    try:
        names = [n for n in os.listdir(path) if n.lower().endswith(".mp4")]
    except OSError:
        return []
    full = [os.path.join(path, n) for n in names]
    return sorted(full, key=lambda p: os.path.getmtime(p))
