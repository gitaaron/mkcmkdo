"""Person boxes beside a recording, for the players' overlay.

While recording, every fresh detection is noted with the label the tracker
gave each box, and when the recording stops they are written next to the
clip as `<clip>.boxes.json`. The uploader sends it with the clip; the apps
draw the boxes over the video and can hide them.

    {"v": 1, "size": [1280, 720],
     "frames": [[0.33, [[412, 160, 96, 288, "climber"], ...]], [0.66, []], ...]}

Each frame is one detection: seconds from the start of the clip, then the
boxes as (x, y, w, h) in pixels of a `size` frame (the preview stream, which
has the same field of view as the recording). An empty list means the
detector looked and saw nobody. A player shows a frame's boxes until the next
frame, or for `HOLD_S` at most.

Labels (docs 05, "Boxes in the recording"):
    climber  the person the camera knows is the climber        green
    other    anyone else                                       yellow
    unsure   the camera cannot yet tell who is the climber     red
"""
from __future__ import annotations

import json
import os
import time

from . import config

Box = tuple[int, int, int, int]
CLIMBER, OTHER, UNSURE = "climber", "other", "unsure"
HOLD_S = 1.0


def sidecar(mp4_path: str) -> str:
    """`rec_x.mp4` → `rec_x.boxes.json`."""
    return os.path.splitext(mp4_path)[0] + ".boxes.json"


class BoxLog:
    def __init__(self) -> None:
        self._path: str | None = None
        self._started = 0.0
        self._frames: list[list] = []
        self._last_at: float | None = None

    def start(self, mp4_path: str, started: float | None = None) -> None:
        self._path = mp4_path
        self._started = time.monotonic() if started is None else started
        self._frames, self._last_at = [], None

    def note(self, at: float | None, labelled: list[tuple[Box, str]]) -> None:
        """One detection, at monotonic time `at`; repeats of the last are ignored."""
        if self._path is None or at is None or at == self._last_at:
            return
        self._last_at = at
        self._frames.append([round(max(0.0, at - self._started), 2),
                             [[*map(int, box), label] for box, label in labelled]])

    def stop(self) -> str | None:
        """Write the sidecar; its path, or None if nothing was recording."""
        if self._path is None:
            return None
        path, self._path = sidecar(self._path), None
        doc = {"v": 1, "size": list(config.PREVIEW_SIZE), "frames": self._frames}
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(doc, f, separators=(",", ":"))
            os.replace(tmp, path)
        except OSError as err:          # the clip matters more than its boxes
            print(f"[boxes] could not write {path}: {err}")
            return None
        return path
