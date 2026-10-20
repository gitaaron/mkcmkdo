"""Phone-driven Wi-Fi provisioning for the head unit (gym workflow).

If the Pi has no network connection a minute after boot, it raises its own
hotspot and serves a one-page setup portal:

  1. On your phone, join Wi-Fi network  "SportCam-Setup"  (pw: sportcam123)
  2. Open  http://10.42.0.1  (Android often pops the portal automatically)
  3. Pick the gym's Wi-Fi from the scan list, type the password, Connect.

The Pi then drops the hotspot and joins the gym network; NetworkManager
remembers it for next time. If joining fails (wrong password), the hotspot
comes back up so you can retry.

Uses NetworkManager (default on Raspberry Pi OS Bookworm) via nmcli.
Run as a systemd unit: device/sportcam-wifi.service.
"""
from __future__ import annotations

import asyncio
import html
import subprocess

from aiohttp import web

AP_SSID = "SportCam-Setup"
AP_PASS = "sportcam123"
AP_CON = "sportcam-hotspot"
IFACE = "wlan0"
BOOT_GRACE_S = 60


def nmcli(*args: str, timeout: int = 45) -> subprocess.CompletedProcess:
    return subprocess.run(["nmcli", *args], capture_output=True, text=True, timeout=timeout)


def online() -> bool:
    out = nmcli("-t", "-f", "STATE", "general").stdout.strip()
    return out.startswith("connected")


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


def hotspot_up() -> None:
    nmcli("device", "wifi", "hotspot", "ifname", IFACE, "con-name", AP_CON,
          "ssid", AP_SSID, "password", AP_PASS)


def hotspot_down() -> None:
    nmcli("connection", "down", AP_CON)


def join(ssid: str, psk: str) -> bool:
    hotspot_down()
    args = ["device", "wifi", "connect", ssid, "ifname", IFACE]
    if psk:
        args += ["password", psk]
    ok = nmcli(*args, timeout=60).returncode == 0 and online()
    if not ok:
        nmcli("connection", "delete", ssid)  # drop the bad profile
        hotspot_up()
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


async def connect(req: web.Request) -> web.Response:
    form = await req.post()
    ssid, psk = str(form.get("ssid", "")), str(form.get("psk", ""))
    if not ssid:
        return web.Response(text=render("Pick a network first."), content_type="text/html")
    ok = await asyncio.get_event_loop().run_in_executor(None, join, ssid, psk)
    if ok:
        return web.Response(
            text=f"<h1>Connected to {html.escape(ssid)} &#10003;</h1>"
                 "<p>The camera is online — you can close this page and rejoin the gym Wi-Fi.</p>",
            content_type="text/html")
    return web.Response(text=render(f"Couldn't join {ssid} — check the password."),
                        content_type="text/html")


async def main() -> None:
    await asyncio.sleep(BOOT_GRACE_S)
    if online():
        print("[wifi] already online — portal not needed")
        return
    print(f"[wifi] no network — raising hotspot '{AP_SSID}'")
    hotspot_up()
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/generate_204", index)      # Android captive-portal probe
    app.router.add_get("/hotspot-detect.html", index)  # iOS captive-portal probe
    app.router.add_post("/connect", connect)
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
