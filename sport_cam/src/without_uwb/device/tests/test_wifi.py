"""Wi-Fi setup: connecting → pairing → the phone's QR code → awake, without a Pi.

  1. the Wi-Fi share-code parser, on the formats Android and iOS produce;
  2. a real QR code through Camera.qr_text (needs OpenCV);
  3. the status file the portal and the head share;
  4. the head's boot states through Head.wifi_loop(), with the portal faked;
  5. the portal's own decisions, with nmcli faked.

    python3 device/tests/test_wifi.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config, wifi_link, wifi_portal
from sportcam.led import COLOURS
from sportcam.wifi_link import (NotWifiQr, UnsupportedWifi, parse_wifi_qr,
                                public_state, read_status, write_status)

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception:          # noqa: BLE001 — the wrong exception is a failure too
        return False
    return False


def parser() -> None:
    print("QR code parser")
    c = parse_wifi_qr("WIFI:S:Hogtown Guest;T:WPA;P:climb0n;H:false;;")
    check("Android order", c == {"ssid": "Hogtown Guest", "psk": "climb0n", "hidden": False}, f"{c}")
    c = parse_wifi_qr("WIFI:T:WPA;S:Hogtown Guest;P:climb0n;;")
    check("iOS order", c["ssid"] == "Hogtown Guest" and c["psk"] == "climb0n", f"{c}")
    c = parse_wifi_qr(r"WIFI:S:a\;b\:c;T:WPA;P:p\\w\;d\,x;;")
    check("escaped ; : \\ ,", c["ssid"] == "a;b:c" and c["psk"] == "p\\w;d,x", f"{c}")
    c = parse_wifi_qr('WIFI:S:"12345678";T:WPA;P:"pa ss";;')
    check("quoted values", c["ssid"] == "12345678" and c["psk"] == "pa ss", f"{c}")
    c = parse_wifi_qr("WIFI:S:Open Gym;T:nopass;;")
    check("open network: no password", c["psk"] == "", f"{c}")
    c = parse_wifi_qr("WIFI:S:Back Room;T:WPA;P:x12345678;H:true;;")
    check("hidden network", c["hidden"] is True, f"{c}")
    c = parse_wifi_qr("wifi:S:Gym;T:SAE;P:secret99;R:1;K:abc")
    check("lower-case prefix, WPA3 extras, no final ;;", c["ssid"] == "Gym" and c["psk"] == "secret99", f"{c}")
    check("enterprise refused", raises(
        lambda: parse_wifi_qr("WIFI:T:WPA2-EAP;S:Corp;E:PEAP;I:me;P:pw;;"), UnsupportedWifi))
    check("a URL isn't Wi-Fi", raises(lambda: parse_wifi_qr("https://example.com"), NotWifiQr))
    check("no network name", raises(lambda: parse_wifi_qr("WIFI:T:WPA;P:pw;;"), NotWifiQr))


def camera_reads_qr() -> None:
    print("\nQR code through the camera")
    if cv2 is None or not hasattr(cv2, "QRCodeEncoder"):
        print("  skip  (no OpenCV QR encoder)")
        return
    from sportcam.camera import Camera
    text = "WIFI:S:Hogtown Guest;T:WPA;P:climb0n;;"
    code = cv2.QRCodeEncoder.create().encode(text)
    code = cv2.resize(code, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)
    w, h = config.PREVIEW_SIZE
    frame = np.full((h, w, 3), 90, np.uint8)       # a grey room…
    y, x = (h - code.shape[0]) // 2, (w - code.shape[1]) // 2
    frame[y:y + code.shape[0], x:x + code.shape[1]] = code[:, :, None]   # …and the phone

    class FakeCam:
        def __init__(self, img):
            self.img = img

        def capture_array(self, _stream):        # the lores stream is YUV420
            return cv2.cvtColor(self.img, cv2.COLOR_RGB2YUV_I420)

    cam = Camera.__new__(Camera)
    cam._cam, cam._qr, cam.awake = FakeCam(frame), None, True
    cam._cam_lock = threading.Lock()
    got = cam.qr_text()
    check("decodes a phone's code in the frame", got == text, f"{got!r}")
    cam._cam = FakeCam(np.full((h, w, 3), 90, np.uint8))
    check("nothing in frame → None", cam.qr_text() is None)


def status_file(tmp: str) -> None:
    print("\nstatus file")
    check("missing → None", read_status() is None)
    with open(wifi_link.STATUS_PATH, "w") as f:
        f.write("{not json")
    check("half-written → None", read_status() is None)
    write_status("pairing", "Couldn't join Gym — check the password.", ssid="Gym")
    st = read_status()
    check("round trip", st == {"state": "pairing", "ssid": "Gym",
                               "message": "Couldn't join Gym — check the password."}, f"{st}")
    check("no temp files left", os.listdir(tmp) == [os.path.basename(wifi_link.STATUS_PATH)],
          f"{os.listdir(tmp)}")
    check("readable by the head's user", os.stat(wifi_link.STATUS_PATH).st_mode & 0o044 == 0o044)
    os.remove(wifi_link.STATUS_PATH)


# ---- the head's boot states -------------------------------------------------------
class FakePtz:
    def __init__(self):
        self.calls: list = []

    def park(self):
        self.calls.append("park")

    def home(self):
        self.calls.append("home")

    def set_focus(self, d):
        self.calls.append(("focus", d))


class FakeRing:
    def __init__(self):
        self.seen: list[str] = []

    def set_state(self, s):
        if not self.seen or self.seen[-1] != s:
            self.seen.append(s)


class FakeCamera:
    qr = None
    no_detector = None

    def qr_text(self):
        return self.qr

    def set_detect_fps(self, _fps):
        pass

    def set_awake(self, _on):
        pass


class FakeReporter:
    def __init__(self):
        self.states: list[str] = []

    async def report_state(self, state, _session_hash=None):   # cloud
        self.states.append(public_state(state))

    async def update_state(self, state):         # mDNS
        pass

    async def broadcast(self, _msg):             # local API
        pass

    def state_payload(self):
        return {}


class FakeStorage:
    def can_record(self):
        return True


def make_head():
    from sportcam.main import Head
    head = Head.__new__(Head)
    head.state = "connecting"
    head._boot_at = asyncio.get_event_loop().time()
    head._qr_sent, head._near_focus = {}, False
    head.camera, head.ptz, head.led = FakeCamera(), FakePtz(), FakeRing()
    head.storage = FakeStorage()
    head.cloud = head.mdns = head.local = FakeReporter()
    head._jog, head._jog_at = (0.0, 0.0), float("-inf")
    head.session_hash = None
    return head


async def until(cond, timeout=2.0) -> bool:
    t = asyncio.get_event_loop().time()
    while not cond():
        if asyncio.get_event_loop().time() - t > timeout:
            return False
        await asyncio.sleep(0.005)
    return True


async def head_flow() -> None:
    print("\nhead: connecting → pairing → QR code → awake")
    from sportcam import main as main_mod
    check("boot_state: no file yet → connecting", main_mod.boot_state(None, 1.0) == "connecting")
    check("boot_state: no portal at all → awake",
          main_mod.boot_state(None, config.WIFI_STATUS_WAIT_S + 1) == "awake")
    check("boot_state: offline → awake", main_mod.boot_state({"state": "offline"}, 0) == "awake")
    check("apps see connecting / pairing as off",
          public_state("connecting") == public_state("pairing") == "off"
          and public_state("awake") == "awake")
    check("LED has both boot states", "connecting" in COLOURS and "pairing" in COLOURS)

    config.QR_SCAN_PERIOD_S = 0.01
    sent: list[dict] = []
    outcome = {"ok": False}

    async def fake_join(creds, url=None):
        # As the portal: "connecting" before the 202, the result some time after.
        sent.append(creds)
        write_status("connecting", ssid=creds["ssid"])

        async def result():
            await asyncio.sleep(0.05)
            write_status("online" if outcome["ok"] else "pairing", ssid=creds["ssid"])
        asyncio.create_task(result())
        return True
    main_mod.wifi_link.request_join = fake_join

    head = make_head()
    write_status("connecting")
    task = asyncio.create_task(head.wifi_loop())
    await asyncio.sleep(0.05)
    check("boots connecting, apps see off", head.state == "connecting" and not head.cloud.states)

    write_status("pairing")
    check("no saved network → pairing", await until(lambda: head.state == "pairing"))
    check("pairing: ring blinks white", head.led.seen[-1] == "pairing", f"{head.led.seen}")
    check("pairing: parked, focused near for the phone",
          "park" in head.ptz.calls and ("focus", config.QR_FOCUS_M) in head.ptz.calls,
          f"{head.ptz.calls}")
    check("pairing: apps still see off", head.cloud.states and head.cloud.states[-1] == "off")

    head.camera.qr = "https://example.com/menu"
    await asyncio.sleep(0.05)
    check("some other QR code is ignored", not sent)

    head.camera.qr = "WIFI:S:Hogtown Guest;T:WPA;P:wrong;;"
    check("wrong password: sent once…", await until(lambda: len(sent) == 1))
    check("…shows connecting, then back to pairing",
          await until(lambda: head.led.seen[-2:] == ["connecting", "pairing"]), f"{head.led.seen}")
    await asyncio.sleep(0.1)
    check("…and isn't resent while still in front of the lens", len(sent) == 1, f"{len(sent)}")

    outcome["ok"] = True
    head.camera.qr = "WIFI:S:Hogtown Guest;T:WPA;P:climb0n;;"
    check("right password: joins → awake", await until(lambda: head.state == "awake"))
    check("…with the credentials off the code",
          sent[-1] == {"ssid": "Hogtown Guest", "psk": "climb0n", "hidden": False}, f"{sent[-1]}")
    check("…focus and zoom re-homed for awake", head.ptz.calls[-1] == "home", f"{head.ptz.calls}")
    check("…and the apps see awake", head.cloud.states[-1] == "awake")
    await asyncio.wait_for(task, 1.0)
    check("the gate ends once up", task.done())

    write_status("pairing")
    head = make_head()
    head.state = "awake"
    await asyncio.wait_for(head.wifi_loop(), 1.0)
    check("Wi-Fi lost later never pulls the camera back", head.state == "awake")


async def portal() -> None:
    print("\nportal")
    from types import SimpleNamespace as NS
    out = {"device": "wlan0:connected:sportcam-hotspot\nlo:connected (externally):lo\n"}
    wifi_portal.nmcli = lambda *a, **k: NS(stdout=out["device"], returncode=0)
    check("own hotspot isn't online", not wifi_portal.online())
    out["device"] = "wlan0:connected:Hogtown Guest\n"
    check("a real network is", wifi_portal.online())

    wifi_portal.scan = lambda: [{"ssid": "Hogtown Guest", "signal": 70, "secured": True}]
    wifi_portal.saved_ssids = lambda: {"Home"}
    check("early: give the saved networks a moment", not wifi_portal.should_pair(3))
    check("after the first scan, none in range → pair", wifi_portal.should_pair(wifi_portal.FIRST_SCAN_S))
    wifi_portal.saved_ssids = lambda: {"Home", "Hogtown Guest"}
    check("a saved one in range → keep waiting", not wifi_portal.should_pair(wifi_portal.FIRST_SCAN_S))
    check("…but not forever", wifi_portal.should_pair(wifi_portal.BOOT_GRACE_S))

    joined: list = []
    wifi_portal.join = lambda *a: joined.append(a) or True

    class Req:
        def __init__(self, body):
            self.body = body

        async def json(self):
            if self.body is None:
                raise ValueError("no body")
            return self.body

    r = await wifi_portal.api_join(Req({"ssid": "Hogtown Guest", "psk": "climb0n", "hidden": True}))
    await asyncio.sleep(0.05)
    check("join from the lens answers at once (202)", r.status == 202)
    check("…and joins", joined == [("Hogtown Guest", "climb0n", True)], f"{joined}")
    check("…saying so before it answers", read_status()["state"] == "connecting")
    r = await wifi_portal.api_join(Req(None))
    check("bad body → 400", r.status == 400)
    r = await wifi_portal.offline(None)
    check("Use without Wi-Fi → status offline", read_status()["state"] == "offline")


def main() -> None:
    print("wifi checks\n")
    tmp = tempfile.mkdtemp()
    wifi_link.STATUS_PATH = os.path.join(tmp, "sportcam-wifi.json")
    parser()
    camera_reads_qr()
    status_file(tmp)
    asyncio.run(head_flow())
    asyncio.run(portal())

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all wifi checks passed")


if __name__ == "__main__":
    main()
