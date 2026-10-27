"""Who owns a recording, and who may stop it — the camera's half of
src/backend/functions/src/sessions.ts.

Several people share the camera. Whoever taps Record gets a **session
secret**, a random string only their phone holds; the camera keeps just its
SHA-256, the session hash, and

  * refuses to stop or advance the session (stop, sleep, stop tracking,
    record now) unless the call carries the secret, so only the person
    recording can stop it — on the camera's Wi-Fi with no internet as much
    as through Firebase;
  * stamps every clip of the session with the hash, in `<clip>.owner` beside
    it on the card, and sends it up with the clip as its `claimHash`;
  * shows a clip still on the card (direct connection) only to a phone
    holding its secret.

The phone later registers the secret with the backend under the person
signed in, which makes every clip with that hash theirs. The camera needs no
accounts, no internet and no Firebase to do its part.

A tag's session uses the secret of the phone it is paired to (pairing.py).
A session with no owner (an unpaired tag's, when TAG_NEEDS_PAIRING is off)
has no hash: anyone may stop it, and its clips belong to no one.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets as _secrets
from typing import Any

SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_SECRETS = 100


def new_secret() -> str:
    """32 random bytes, base64url: the same shape as the API's."""
    return _secrets.token_urlsafe(32)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def is_secret(s: Any) -> bool:
    return isinstance(s, str) and bool(SECRET_RE.match(s))


def secrets_of(data: Any) -> list[str]:
    """The well-formed secrets in a call's `{"secrets": […]}`; the app sends every one it holds."""
    raw = data.get("secrets") if isinstance(data, dict) else None
    return [s for s in raw if is_secret(s)][:MAX_SECRETS] if isinstance(raw, list) else []


def hashes_of(secrets: list[str]) -> set[str]:
    return {hash_secret(s) for s in secrets}


def holds(secrets: list[str], session_hash: str) -> bool:
    return session_hash in hashes_of(secrets)


def owner_file(mp4_path: str) -> str:
    """`rec_x.mp4` → `rec_x.owner`."""
    return os.path.splitext(mp4_path)[0] + ".owner"


def stamp(mp4_path: str, session_hash: str | None) -> None:
    """Note whose session a clip is from, beside it. Nobody's: no file."""
    if session_hash:
        with open(owner_file(mp4_path), "w") as f:
            f.write(session_hash)


def owner_of(mp4_path: str) -> str | None:
    """The session hash a clip was stamped with, or None."""
    try:
        with open(owner_file(mp4_path)) as f:
            h = f.read().strip()
    except OSError:
        return None
    return h if HASH_RE.match(h) else None
