"""The head unit's side of Wi-Fi setup: boot state and the phone's QR code.

Two processes share the job, because they need different things:

  * **sportcam-wifi** (wifi_portal.py, root) owns the radio: it tries the
    saved networks, raises the `SportCam-Setup` hotspot, and joins whatever
    it is given. It writes how that is going to STATUS_PATH.
  * **sportcam-head** (main.py, user pi) owns the camera and the LED ring.
    It reads STATUS_PATH to know whether it is still `connecting`, in
    `pairing`, or done; and while pairing it reads the phone's Wi-Fi share
    QR code through the lens and hands the network to the portal.

A phone won't give its saved Wi-Fi password to an app or a web page, but
both iOS (18+, Passwords → Wi-Fi → Show Network QR Code) and Android
(Settings → Wi-Fi → Share) will show it as a standard QR code:

    WIFI:T:WPA;S:<ssid>;P:<password>;H:<true|false>;;

so you hold the phone up to the camera and type nothing.
"""
from __future__ import annotations

import json
import os
import tempfile

STATUS_PATH = "/run/sportcam-wifi.json"   # written by the portal (root), read by the head
JOIN_URL = "http://127.0.0.1/api/join"    # the portal, while it is pairing

# Portal status → head state. Anything that isn't "still getting on a
# network" lets the camera carry on to idle.
CONNECTING, PAIRING, ONLINE, OFFLINE = "connecting", "pairing", "online", "offline"


# ---- the QR code -------------------------------------------------------------
class NotWifiQr(ValueError):
    """Text that isn't a Wi-Fi share code at all (a URL, a menu…)."""


class UnsupportedWifi(ValueError):
    """A Wi-Fi share code for a network the camera can't join this way."""


def parse_wifi_qr(text: str) -> dict:
    """`WIFI:…;;` → {"ssid", "psk", "hidden"}.

    Fields come in any order; `\\`, `;`, `,`, `:` and `"` are backslash-escaped,
    and a value may be wrapped in double quotes. Unknown fields (Android adds
    `R:` and `K:` for WPA3) are ignored.

    Raises NotWifiQr for any other code, and UnsupportedWifi for enterprise
    (username + password) networks.
    """
    if not text or not text[:5].upper() == "WIFI:":
        raise NotWifiQr(text[:40] if text else "")
    fields: dict[str, str] = {}
    key, buf, esc = None, [], False
    for ch in text[5:]:
        if esc:
            buf.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":" and key is None:
            key, buf = "".join(buf).strip().upper(), []
        elif ch == ";":
            if key:
                fields.setdefault(key, _unquote("".join(buf)))
            key, buf = None, []
        else:
            buf.append(ch)
    if key:                                   # a missing final ';'
        fields.setdefault(key, _unquote("".join(buf)))

    ssid = fields.get("S", "")
    if not ssid:
        raise NotWifiQr("no network name")
    kind = fields.get("T", "").upper()
    if "EAP" in kind or "E" in fields:
        raise UnsupportedWifi(f"{ssid} needs a username (enterprise Wi-Fi)")
    psk = "" if kind == "NOPASS" else fields.get("P", "")
    return {"ssid": ssid, "psk": psk, "hidden": fields.get("H", "").lower() == "true"}


def _unquote(v: str) -> str:
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] == '"' else v


# ---- the status file -----------------------------------------------------------
def read_status(path: str | None = None) -> dict | None:
    """The portal's last word, or None if it hasn't written one (yet, or ever)."""
    try:
        with open(path or STATUS_PATH) as f:
            st = json.load(f)
    except (OSError, ValueError):
        return None
    return st if isinstance(st, dict) and "state" in st else None


def write_status(state: str, message: str = "", ssid: str = "",
                 path: str | None = None) -> None:
    """Atomically, so the head never reads half a file."""
    path = path or STATUS_PATH
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".sportcam-wifi.")
    with os.fdopen(fd, "w") as f:
        json.dump({"state": state, "message": message, "ssid": ssid}, f)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


# ---- handing the network to the portal -------------------------------------------
async def request_join(creds: dict, url: str | None = None) -> bool:
    """Ask the portal to join. It answers at once and joins in the background;
    progress shows up in the status file."""
    import aiohttp

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
            async with s.post(url or JOIN_URL, json=creds) as r:
                return r.status == 202
    except (aiohttp.ClientError, OSError, TimeoutError) as err:
        print(f"[wifi] portal unreachable: {err}")
        return False


# ---- what the apps see ------------------------------------------------------------
# The camera's own states before it has a network. No app can reach it yet,
# so to every app it is still "off".
BOOT_STATES = (CONNECTING, PAIRING)


def public_state(state: str) -> str:
    return "off" if state in BOOT_STATES else state
