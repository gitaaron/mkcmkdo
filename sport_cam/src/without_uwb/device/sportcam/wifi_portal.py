"""Phone-driven Wi-Fi provisioning for the head unit (gym workflow).

At boot the camera is **connecting**: NetworkManager tries the saved
networks. If none of them is in range, or none has joined BOOT_GRACE_S after
boot, the camera goes into **pairing**: it raises its own hotspot and waits
to be given a network, either way:

  * **QR code** — show the phone's Wi-Fi share code to the lens. The head
    unit reads it (wifi_link.py) and POSTs it to /api/join here.
  * **Setup page** — join "SportCam-Setup" (its password is printed on the head's
    label), open http://10.42.0.1 (usually pops up by itself), pick
    the network and paste its password.

The Pi then drops the hotspot and joins; NetworkManager remembers it for
next time. If joining fails (wrong password), the hotspot comes back up so
you can retry. **Use without Wi-Fi** on the setup page lets the camera carry
on offline, controlled by a phone on the hotspot.

How it is going is written to wifi_link.STATUS_PATH for the head unit,
which shows it on the LED ring.

Uses NetworkManager (default on Raspberry Pi OS Bookworm) via nmcli.
Run as a systemd unit: device/sportcam-wifi.service.
"""
from __future__ import annotations

import asyncio
import html
import subprocess

from aiohttp import web

from .wifi_link import CONNECTING, OFFLINE, ONLINE, PAIRING, write_status

AP_SSID = "SportCam-Setup"
# Each camera's own hotspot password, set at install and printed on its
# label (docs/setup). The fallback is only for a bench Pi that has none.
AP_PASS_FILE = "/etc/sportcam/hotspot-password"
AP_PASS_DEFAULT = "sportcam123"
AP_CON = "sportcam-hotspot"
IFACE = "wlan0"
BOOT_GRACE_S = 60      # give the saved networks this long before pairing…
FIRST_SCAN_S = 10      # …unless the first scan shows none of them in range


def ap_password() -> str:
    try:
        with open(AP_PASS_FILE) as f:
            pw = f.read().strip()
        if len(pw) >= 8:            # WPA2 minimum
            return pw
    except OSError:
        pass
    return AP_PASS_DEFAULT


def nmcli(*args: str, timeout: int = 45) -> subprocess.CompletedProcess:
    return subprocess.run(["nmcli", *args], capture_output=True, text=True, timeout=timeout)


def online() -> bool:
    """wlan0 is on a network — not merely running our own hotspot, which
    NetworkManager also counts as "connected"."""
    out = nmcli("-t", "-f", "DEVICE,STATE,CONNECTION", "device").stdout
    for line in out.splitlines():
        dev, _, rest = line.partition(":")
        state, _, con = rest.partition(":")
        if dev == IFACE:
            return state == "connected" and con != AP_CON
    return False


def scan() -> list[dict]:
    nmcli("device", "wifi", "rescan")
    out = nmcli("-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list").stdout
    seen: dict[str, dict] = {}
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 3 or not parts[0] or parts[0] == AP_SSID:
            continue
        ssid, signal, security = parts[0], parts[1], ":".join(parts[2:])
        if ssid not in seen or int(signal or 0) > seen[ssid]["signal"]:
            seen[ssid] = {"ssid": ssid, "signal": int(signal or 0), "secured": security not in ("", "--")}
    return sorted(seen.values(), key=lambda n: -n["signal"])


def saved_ssids() -> set[str]:
    """SSIDs of the Wi-Fi networks NetworkManager has a profile for."""
    out = nmcli("-t", "-f", "NAME,TYPE", "connection", "show").stdout
    ssids = set()
    for line in out.splitlines():
        name, _, kind = line.rpartition(":")
        name = name.replace("\\:", ":")
        if kind != "802-11-wireless" or name == AP_CON:
            continue
        ssid = nmcli("-g", "802-11-wireless.ssid", "connection", "show", name).stdout.strip()
        ssids.add(ssid or name)
    return ssids


def hotspot_up() -> None:
    nmcli("device", "wifi", "hotspot", "ifname", IFACE, "con-name", AP_CON,
          "ssid", AP_SSID, "password", ap_password())


def hotspot_down() -> None:
    nmcli("connection", "down", AP_CON)


def join(ssid: str, psk: str, hidden: bool = False) -> bool:
    write_status(CONNECTING, ssid=ssid)
    hotspot_down()
    args = ["device", "wifi", "connect", ssid, "ifname", IFACE]
    if psk:
        args += ["password", psk]
    if hidden:
        args += ["hidden", "yes"]
    ok = nmcli(*args, timeout=60).returncode == 0 and online()
    if ok:
        write_status(ONLINE, ssid=ssid)
    else:
        nmcli("connection", "delete", ssid)  # drop the bad profile
        hotspot_up()
        write_status(PAIRING, f"Couldn't join {ssid} — check the password.", ssid=ssid)
    return ok


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SportCam Wi-Fi setup</title>
<style>
 body{{font-family:system-ui;background:#0d1420;color:#e8edf6;margin:0;padding:24px;max-width:480px}}
 h1{{font-size:20px;color:#2f6fed}} li{{list-style:none;margin:6px 0}}
 button,input{{font-size:16px;padding:12px;border-radius:10px;border:1px solid #2a3850;width:100%;box-sizing:border-box}}
 button{{background:#131c2c;color:#e8edf6;text-align:left;cursor:pointer}}
 .sel{{border-color:#2f6fed}} #go{{background:#2f6fed;text-align:center;margin-top:10px}}
 .sig{{float:right;color:#7f8ea8}} #msg{{color:#f2a93b}}
</style></head><body>
<h1>&#128247; SportCam &mdash; connect to Wi-Fi</h1>
<p>Pick the gym's network, enter its password, and the camera will join it.</p>
<ul>{items}</ul>
<form method="POST" action="/connect">
 <input type="hidden" name="ssid" id="ssid">
 <input type="password" name="psk" id="psk" placeholder="Wi-Fi password">
 <button id="go" type="submit">Connect</button>
</form>
<p id="msg">{msg}</p>
<p>Or hold your phone's Wi-Fi QR code up to the camera: Android, Settings &rarr;
Wi-Fi &rarr; Share; iPhone, Passwords &rarr; Wi-Fi &rarr; Show Network QR Code.</p>
<form method="POST" action="/offline"><button type="submit">Use without Wi-Fi</button></form>
<script>
 for (const b of document.querySelectorAll('button[data-ssid]'))
   b.onclick = (e) => {{ e.preventDefault();
     document.getElementById('ssid').value = b.dataset.ssid;
     document.querySelectorAll('.sel').forEach(x=>x.classList.remove('sel'));
     b.classList.add('sel'); }};
</script></body></html>"""


def render(msg: str = "") -> str:
    items = "".join(
        f'<li><button data-ssid="{html.escape(n["ssid"], quote=True)}">'
        f'{html.escape(n["ssid"])}{"" if n["secured"] else " (open)"}'
        f'<span class="sig">{n["signal"]}%</span></button></li>'
        for n in scan()
    )
    return PAGE.format(items=items or "<li>No networks found — refresh.</li>", msg=html.escape(msg))


async def index(_req: web.Request) -> web.Response:
    return web.Response(text=render(), content_type="text/html")


_joining = asyncio.Lock()     # one join at a time, from the page or the lens
_tasks: set[asyncio.Task] = set()


async def connect(req: web.Request) -> web.Response:
    form = await req.post()
    ssid, psk = str(form.get("ssid", "")), str(form.get("psk", ""))
    if not ssid:
        return web.Response(text=render("Pick a network first."), content_type="text/html")
    async with _joining:
        ok = await asyncio.to_thread(join, ssid, psk)
    if ok:
        return web.Response(
            text=f"<h1>Connected to {html.escape(ssid)} &#10003;</h1>"
                 "<p>The camera is online — you can close this page and rejoin the gym Wi-Fi.</p>",
            content_type="text/html")
    return web.Response(text=render(f"Couldn't join {ssid} — check the password."),
                        content_type="text/html")


async def api_join(req: web.Request) -> web.Response:
    """A network read off the phone's QR code by the head unit.

    Answers at once: the hotspot goes down while joining, so a caller
    waiting on the reply would never get it. Progress is in the status file.
    """
    try:
        body = await req.json()
        ssid, psk = str(body["ssid"]), str(body.get("psk", ""))
        hidden = bool(body.get("hidden", False))
    except (ValueError, KeyError, TypeError):
        return web.json_response({"error": "expected {ssid, psk, hidden}"}, status=400)
    if _joining.locked():
        return web.json_response({"error": "already joining"}, status=409)
    write_status(CONNECTING, ssid=ssid)   # before answering, so the head never re-reads "pairing"

    async def run() -> None:
        async with _joining:
            await asyncio.to_thread(join, ssid, psk, hidden)
    # The loop holds tasks only weakly: keep this one until the join is done.
    task = asyncio.create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return web.json_response({"joining": ssid}, status=202)


async def offline(_req: web.Request) -> web.Response:
    """Carry on without Wi-Fi: the hotspot stays up for direct control."""
    write_status(OFFLINE, "Using the camera without Wi-Fi.")
    return web.Response(
        text="<h1>Using the camera without Wi-Fi</h1>"
             f"<p>Stay on {html.escape(AP_SSID)} and open the SportCam app; it connects "
             "to the camera directly. Recordings upload once it's on a network.</p>",
        content_type="text/html")


def should_pair(elapsed_s: float) -> bool:
    """Still offline: give up on the saved networks yet?"""
    if elapsed_s >= BOOT_GRACE_S:
        return True
    if elapsed_s >= FIRST_SCAN_S:
        in_range = {n["ssid"] for n in scan()}
        return not (saved_ssids() & in_range)
    return False


async def main() -> None:
    write_status(CONNECTING)
    t0 = asyncio.get_running_loop().time()
    while not online():
        if await asyncio.to_thread(should_pair, asyncio.get_running_loop().time() - t0):
            break
        await asyncio.sleep(2)
    else:
        print("[wifi] online — portal not needed")
        write_status(ONLINE)
        return
    print(f"[wifi] no network — raising hotspot '{AP_SSID}'")
    hotspot_up()
    write_status(PAIRING)
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/generate_204", index)      # Android captive-portal probe
    app.router.add_get("/hotspot-detect.html", index)  # iOS captive-portal probe
    app.router.add_post("/connect", connect)
    app.router.add_post("/offline", offline)
    app.router.add_post("/api/join", api_join)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 80).start()
    print("[wifi] portal at http://10.42.0.1")
    while not online():
        await asyncio.sleep(5)
    print("[wifi] connected — portal exiting")
    await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
