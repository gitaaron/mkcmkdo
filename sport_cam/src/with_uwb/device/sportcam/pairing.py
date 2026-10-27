"""Which wearable tag is whose: tag number → the pairing hash of one phone.

A tag starts a session by being switched on (session.py), with no phone in
the loop, so the camera has to know already whose sessions it starts. A
phone pairs a tag over the direct connection (`pairTag` in local_api.py):
with that tag the only one switched on, it is given a **pairing secret**,
and the camera keeps the tag's number with the secret's hash. Every session
that tag starts then has that hash as its session hash (owners.py): only
that phone may stop it, and its clips are that person's.

Pairing a tag again replaces the earlier pairing, so a gym's tags can be
lent out: whoever has the tag in hand and the camera's Wi-Fi pairs it.

Tags are numbered by the ULA1's DIP switch (T0–T7; 14 — Software setup).
Kept on the card at PAIRINGS_FILE, so pairings survive a restart.
"""
from __future__ import annotations

import json
import os

from . import config, owners


class Pairings:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or config.PAIRINGS_FILE
        self._by_tag: dict[int, str] = {}
        try:
            with open(self.path) as f:
                raw = json.load(f)
            self._by_tag = {int(t): h for t, h in raw.items() if owners.HASH_RE.match(str(h))}
        except (OSError, ValueError, AttributeError):
            pass

    def pair(self, tag: int) -> str:
        """Pair `tag` to a new secret, replacing any earlier pairing; returns the secret."""
        secret = owners.new_secret()
        self._by_tag[tag] = owners.hash_secret(secret)
        self._save()
        return secret

    def hash_for(self, tag: int | None) -> str | None:
        return self._by_tag.get(tag) if tag is not None else None

    def tag_for(self, session_hash: str | None) -> int | None:
        """The tag a pairing hash belongs to; None for an ordinary session's hash."""
        for tag, h in self._by_tag.items():
            if h == session_hash:
                return tag
        return None

    def paired(self, tag: int | None) -> bool:
        return tag in self._by_tag

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({str(t): h for t, h in self._by_tag.items()}, f)
        os.replace(tmp, self.path)
