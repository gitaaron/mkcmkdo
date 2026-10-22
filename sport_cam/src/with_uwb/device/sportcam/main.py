"""Head-unit supervisor.

Everything runs on the one Raspberry Pi now. The PTZ-base build has no base
controller: pan, tilt, zoom and focus are all I2C writes to the Arducam
controller, and the status ring hangs off the Pi's SPI. What used to be a
pan-velocity message relayed Pi → server → ESP32 is now a local function call.

Runs at once:

  * the **local API** (local_api.py) — the phone talks to the camera
    directly over the LAN for live video and control, with no internet in
    the path;
  * an **mDNS advertisement** (discovery.py) so the phone finds it;
  * an optional **Firebase link** (cloud.py) — keeps the camera's Firestore
    document current so the app works from anywhere, and picks up the app's
    commands from it;
  * the **status ring** and the **battery gauge**;
  * the **Wi-Fi gate** (wifi_link.py): the camera boots into `connecting`,
    and `pairing` if it has no network it knows, before `idle`.

State lives on the device. Whichever channel a command arrives on, it goes
through `apply_state()` and is then broadcast to all of them — so the app, the
LED ring and Firestore never disagree.

Run:  python -m sportcam.main          (from device/)
"""
from __future__ import annotations

import asyncio
import time

from . import config, wifi_link
from .boxlog import BoxLog
from .camera import Camera
from .cloud import CloudLink
from .discovery import Advertiser
from .led import StatusRing
from .local_api import LocalApi
from .power import PowerMonitor
from .ptz import Ptz
from .session import AutoSession
from .storage import StorageMonitor
from .tracker import Tracker
from .uploader import drain_pending, upload_with_retry
from .wifi_link import BOOT_STATES, public_state


def boot_state(status: dict | None, waited_s: float) -> str:
    """The head state for the portal's Wi-Fi status, at boot.

    No status file yet: still connecting, unless the portal hasn't written
    one in WIFI_STATUS_WAIT_S — it isn't installed (bench Pi, dev machine),
    so don't wait for it. Online, or told to work offline: idle.
    """
    if status is None:
        return "connecting" if waited_s < config.WIFI_STATUS_WAIT_S else "idle"
    return status["state"] if status["state"] in BOOT_STATES else "idle"
from .uwb import UwbArray


class Head:
    def __init__(self) -> None:
        self.state = "connecting"     # until the Wi-Fi gate lets it go (wifi_loop)
        self._boot_at = time.monotonic()
        self._qr_sent: dict[str, float] = {}   # Wi-Fi QR code → when it was last sent
        self._near_focus = False      # focus moved in for the QR code; home() before idle
        self.camera = Camera()
        self.ptz = Ptz()
        self.uwb = UwbArray()
        self.tracker = Tracker(self.uwb, self.camera, self.ptz)
        self.session = AutoSession()
        self.led = StatusRing()
        self.power = PowerMonitor()
        self.storage = StorageMonitor()
        self.local = LocalApi(self)
        self.cloud = CloudLink(self)
        self.mdns = Advertiser()
        self._rec_path = ""
        self._rec_started = 0.0
        self.boxlog = BoxLog()     # person boxes beside the clip, for the players' overlay
        self._warned = ""          # which warning we last announced
        self._countdown_sent = 0   # tracker.countdown as last sent to the app
        self._boxes_sent_at: float | None = None   # tracker.labelled_at last sent live

    # convenience for local_api/telemetry — pan and tilt are commanded angles
    @property
    def pan_deg(self) -> float:
        return self.ptz.pan_deg

    @property
    def tilt_deg(self) -> float:
        return self.ptz.tilt_deg

    @property
    def phase(self) -> str | None:
        """The sub-state.

        idle: "person-in-frame" or "no-person-in-frame". Tracking: "search",
        then "found" (FOUND_CONFIRM_S to recording). Recording: "track".
        """
        if self.state == "idle":
            return "person-in-frame" if self.tracker.idle_person_in_frame else "no-person-in-frame"
        if self.state not in ("tracking", "recording"):
            return None
        return self.tracker.mode

    @property
    def acquire_stalled(self) -> bool:
        """Acquiring for a while and vision still has not seen the subject."""
        return self.state == "tracking" and self.tracker.acquire_stalled

    # ---- entry point ------------------------------------------------------
    async def run(self) -> None:
        self.ptz.park()
        self.ptz.home()
        self.uwb.start()
        await self.local.start()
        await self.mdns.start(public_state(self.state))
        # The local API and mDNS stay up regardless of the internet; the
        # Firebase link reconnects forever in the background.
        await asyncio.gather(
            self.cloud.run(),
            self.control_loop(),
            self.frame_loop(),
            self.telemetry_loop(),
            self.led.run(),
            self.power.run(),
            self.health_loop(),
            self.upload_loop(),
            self.wifi_loop(),
        )

    # ---- state ------------------------------------------------------------
    async def apply_state(self, new: str) -> None:
        """Single place state changes happen, whatever asked for it."""
        # Refuse to start filming onto a card that cannot hold the clip. The
        # encoder has no graceful failure: it writes until ENOSPC and leaves a
        # truncated file. Better to decline and say why.
        if new == "recording" and not self.storage.can_record():
            print(f"[storage] refusing to record — {self.storage.minutes_left:.0f} min left")
            await self.local.broadcast({"type": "warning", "code": "storage-full",
                                        **self.storage.telemetry()})
            new = "idle" if self.state == "tracking" else self.state
        if self.state == "recording" and new == "tracking":
            new = "idle"                  # stopping a recording ends the session

        old, self.state = self.state, new
        if old not in ("tracking", "recording") and new in ("tracking", "recording"):
            self.tracker.reset_lock()     # a new session acquires afresh
        if old != "recording" and new == "recording":
            self._rec_path = self.camera.start_recording()
            self._rec_started = time.monotonic()
            self.boxlog.start(self._rec_path, self._rec_started)
            self.tracker.confirm()
            print(f"[rec] → {self._rec_path}")
        elif old == "recording" and new != "recording":
            self.camera.stop_recording()
            self.boxlog.stop()
            duration = time.monotonic() - self._rec_started
            print(f"[rec] stopped ({duration:.0f}s) — uploading in background")
            asyncio.create_task(
                upload_with_retry(self._rec_path, round(duration, 1), self.on_upload_progress)
            )
        self.led.set_state(new)
        self.camera.set_detect_fps(
            config.DETECT_FPS_TRACKING if new in ("tracking", "recording")
            else config.DETECT_FPS_IDLE)
        if new in ("idle", "off", *BOOT_STATES):
            self.ptz.park()
        if new == "pairing" and not self._near_focus:
            self.ptz.set_focus(config.QR_FOCUS_M)   # a phone held up to the lens
            self._near_focus = True
        elif new not in BOOT_STATES and self._near_focus:
            self.ptz.home()                         # back to the boot focus and zoom
            self._near_focus = False

    async def report_state(self) -> None:
        """Tell everyone: direct app clients, Firestore, mDNS TXT."""
        await self.local.broadcast(self.local.state_payload())
        await self.cloud.report_state(self.state)
        await self.mdns.update_state(public_state(self.state))

    async def on_upload_progress(self, msg: dict) -> None:
        await self.cloud.upload_progress(msg)
        await self.local.broadcast(msg)
        if msg.get("sent") == msg.get("total"):
            await self.local.broadcast(
                {"type": "recordings", **(await self.local._get_recordings(None))})

    # ---- loops ------------------------------------------------------------
    async def control_loop(self) -> None:
        period = 1.0 / config.UWB_RATE_HZ
        while True:
            t0 = time.monotonic()
            await self.control_tick(t0)
            await asyncio.sleep(max(0.0, period - (time.monotonic() - t0)))

    async def control_tick(self, now: float) -> None:
        """One 20 Hz tick: track, notice a lost tag, and run the tag session."""
        if self.state in BOOT_STATES:
            return                            # no tracking, no sessions, until it is up
        if self.state in ("tracking", "recording"):
            self.tracker.step()
            if self.state == "recording":
                self.boxlog.note(self.tracker.labelled_at, self.tracker.labelled)
            await self.announce_countdown()
            self.led.lost = self.tracker.lost_for() > config.LOST_HOLD_S
            if self.tracker.lost_for() > config.LOST_IDLE_S:
                await self.apply_state("idle")
                await self.report_state()
        else:
            if self.state == "idle":
                self.tracker.watch_idle()     # person in frame? (LED and app only: sessions start in SEARCH)
            self.led.lost = False
        # The tag switching on (or the person found for FOUND_CONFIRM_S) can move the
        # state, through the same apply_state() as any other command.
        want = self.session.update(now, self.uwb.frame_age(), self.state,
                                   self.tracker.ready_to_record)
        if want and want != self.state:
            print(f"[session] {self.state} → {want}")
            await self.apply_state(want)
            await self.report_state()
        await self.send_boxes()
        self.led.idle_person = self.phase == "person-in-frame"
        self.led.searching = self.state == "tracking" and self.phase == "search"
        self.led.found = (self.tracker.found_for() / config.FOUND_CONFIRM_S
                          if self.state == "tracking" and self.phase == "found" else None)

    async def health_loop(self) -> None:
        """Watch the two things that run out: charge and card space.

        Both get the same treatment — warn early, then stop and save before
        the resource is gone. A recording that ends deliberately is a file you
        can watch; one that ends because the pack died or the card filled
        often is not.
        """
        while True:
            self.storage.sample()
            batt, store = self.power.level(), self.storage.level()
            self.led.warn = "low" in (batt, store)

            if batt == "critical" and self.state not in ("off", *BOOT_STATES):
                print("[power] critical — stopping and parking")
                await self.apply_state("idle")
                await self.report_state()
            elif store == "critical" and self.state == "recording":
                print("[storage] critical — stopping recording while it is still valid")
                await self.apply_state("idle")
                await self.report_state()

            for code, level, tele in (("battery-low", batt, self.power.telemetry),
                                      ("storage-low", store, self.storage.telemetry)):
                if level == "low" and self._warned != code:
                    self._warned = code
                    print(f"[health] {code}")
                    await self.local.broadcast({"type": "warning", "code": code, **tele()})
            if batt == "ok" and store == "ok":
                self._warned = ""
            await asyncio.sleep(10.0)

    async def upload_loop(self) -> None:
        """Retry anything still on the card, at boot and then periodically.

        Without this a session filmed with the backend unreachable stays on
        the card forever: the per-recording retry ladder gives up after about
        fifteen minutes and nothing ever looks again. Skipped while recording,
        so uploads never compete with the encoder or touch the open file.
        """
        await asyncio.sleep(5.0)       # let the network come up first
        while True:
            if self.state != "recording":
                try:
                    sent = await drain_pending(self.on_upload_progress, exclude=self._rec_path)
                    if sent:
                        print(f"[upload] drained {sent} pending recording(s)")
                except Exception as err:        # noqa: BLE001 — never fatal
                    print(f"[upload] drain failed: {err}")
            await asyncio.sleep(config.UPLOAD_RETRY_INTERVAL_S)

    async def wifi_loop(self) -> None:
        """Hold the camera in connecting / pairing until it has a network.

        Only at boot: Wi-Fi dropping later is NetworkManager's to fix and
        never interrupts a session. While pairing, read the phone's Wi-Fi
        share QR code through the lens and hand it to the portal, which
        joins it and reports back through the status file.
        """
        while self.state in BOOT_STATES:
            want = boot_state(wifi_link.read_status(), time.monotonic() - self._boot_at)
            if want != self.state:
                print(f"[wifi] {self.state} → {want}")
                await self.apply_state(want)
                await self.report_state()
            if self.state == "pairing":
                await self.scan_qr()
            await asyncio.sleep(config.QR_SCAN_PERIOD_S)

    async def scan_qr(self) -> None:
        text = await asyncio.to_thread(self.camera.qr_text)
        if not text:
            return
        try:
            creds = wifi_link.parse_wifi_qr(text)
        except wifi_link.NotWifiQr:
            return                            # some other QR code
        except wifi_link.UnsupportedWifi as err:
            print(f"[wifi] QR code: {err}")
            return
        # The phone is held up for several scans, and a code that failed
        # (wrong password) is still in front of the lens: don't resend it at once.
        key = f"{creds['ssid']}\0{creds['psk']}"
        now = time.monotonic()
        if now - self._qr_sent.get(key, float("-inf")) < config.QR_RETRY_S:
            return
        self._qr_sent[key] = now
        print(f"[wifi] QR code for {creds['ssid']!r} — joining")
        await wifi_link.request_join(creds)

    async def frame_loop(self) -> None:
        period = 1.0 / config.MJPEG_FPS
        while True:
            t0 = time.monotonic()
            if self.state != "off":
                jpg = self.camera.preview_jpeg()
                if jpg:
                    self.local.publish_frame(jpg)   # direct viewers
                    await self.cloud.preview(jpg, self.live_boxes())   # and, while watched, the app anywhere
            await asyncio.sleep(max(0.0, period - (time.monotonic() - t0)))

    def live_boxes(self) -> list[list]:
        """The last detection's labelled boxes for the live view, `[[x, y, w,
        h, label], …]` in PREVIEW_SIZE pixels; none once stale or not up."""
        at = self.tracker.labelled_at
        if (at is None or self.state in ("off", *BOOT_STATES)
                or time.monotonic() - at > config.LIVE_BOXES_MAX_AGE_S):
            return []
        return [[*map(int, box), label] for box, label in self.tracker.labelled]

    async def send_boxes(self) -> None:
        """Each fresh detection to direct viewers at once, for their overlay
        (an empty list means it looked and saw nobody)."""
        if self.tracker.labelled_at == self._boxes_sent_at:
            return
        self._boxes_sent_at = self.tracker.labelled_at
        await self.local.broadcast({"type": "boxes", "size": list(config.PREVIEW_SIZE),
                                    "boxes": self.live_boxes()})

    def telemetry(self) -> dict:
        return {
            "pan": round(self.ptz.pan_deg, 1),
            "tilt": round(self.ptz.tilt_deg, 1),
            "zoomMm": round(self.ptz.zoom_mm, 1),
            "dist": round(self.tracker.dist_m, 2) if self.tracker.dist_m else None,
            "phase": self.phase,
            "countdown": self.tracker.countdown if self.state == "tracking" else 0,
            "acquireStalled": self.acquire_stalled,
            "tagPresent": self.session.tag_present,
            **self.power.telemetry(),
            **self.storage.telemetry(),
        }

    async def send_telemetry(self) -> None:
        await self.cloud.telemetry({"type": "telemetry", **self.telemetry()})
        await self.local.broadcast(self.local.state_payload())

    async def announce_countdown(self) -> None:
        """Each second of the FOUND countdown goes to the app at once, so it
        can beep for it.

        The app beeps once per second counted (3, 2, 1), then chimes when
        recording starts. Telemetry otherwise goes out once a second, out of
        step with the count.
        """
        countdown = self.tracker.countdown if self.state == "tracking" else 0
        if countdown != self._countdown_sent:
            self._countdown_sent = countdown
            await self.send_telemetry()

    async def telemetry_loop(self) -> None:
        while True:
            await self.send_telemetry()
            await asyncio.sleep(1.0)

if __name__ == "__main__":
    head = Head()
    try:
        asyncio.run(head.run())
    except KeyboardInterrupt:
        head.ptz.park()
        head.led.park()
        asyncio.run(head.mdns.stop())
