#!/usr/bin/env python3
"""Render the recording chimes to assets/sounds/ — the same notes as src/web/src/lib/chime.ts.

    python3 src/app_flutter/tool/make_chimes.py

Start rises C6 → G6, stop falls G6 → C6: a sine with a quiet octave partial,
12 ms attack, exponential decay. 44.1 kHz mono 16-bit WAV. Also writes one
second of digital silence, which the app loops to stay awake in the
background during a session (see lib/session_audio.dart).
"""
import math
import os
import struct
import wave

RATE = 44100
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "sounds")
C6, G6 = 1046.5, 1568.0


def note(freq: float, start: float, buf: list[float], peak: float = 0.5) -> None:
    for i in range(int(0.6 * RATE)):
        t = i / RATE
        env = (t / 0.012) if t < 0.012 else math.exp(-(t - 0.012) / 0.09)
        s = math.sin(2 * math.pi * freq * t) + 0.18 * math.sin(2 * math.pi * 2 * freq * t)
        j = int(start * RATE) + i
        if j < len(buf):
            buf[j] += peak * env * s / 1.18


def write(name: str, samples: list[float]) -> None:
    path = os.path.join(OUT, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))
    print("wrote", os.path.normpath(path))


def chime(first: float, second: float) -> list[float]:
    buf = [0.0] * int(0.8 * RATE)
    note(first, 0.0, buf)
    note(second, 0.16, buf)
    return buf


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    write("rec_start.wav", chime(C6, G6))
    write("rec_stop.wav", chime(G6, C6))
    write("silence.wav", [0.0] * RATE)
