"""Head-unit supervisor.

Everything runs on the one Raspberry Pi. The PTZ-base build has no base
controller: pan, tilt, zoom and focus are all I2C writes to the Arducam
controller, and the status ring hangs off the Pi's SPI. This is the
camera-only build: there is no UWB radio, so the only way a session starts is
the app's track / record button, and the camera finds its own subject by
sweeping the room (tracker.py).

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
    and `pairing` if it has no network it knows, before `awake`;
  * **sleep**: awake AWAKE_TIMEOUT_S with no session started and nobody
    watching the live view, the camera sensor stops and the head parks to
    save the battery. Everything above stays up, so a command wakes it, or
    starts a session straight from sleep.

State lives on the device. Whichever channel a command arrives on, it goes
through `apply_state()` and is then broadcast to all of them — so the app, the
LED ring and Firestore never disagree.

So does the session's owner: `session_hash` (owners.py), set when a session
starts (`start_session()`), stamped beside each clip it records, and cleared
when it ends. Only a phone holding its secret may stop it.

Run:  python -m sportcam.main          (from device/)
"""
from __future__ import annotations

import asyncio
import signal
import time

from . import config, owners, wifi_link
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
from .wifi_link import BOOT_STATES, LIVE_STATES, public_state


def boot_state(status: dict | None, waited_s: float) -> str:
    """The head state for the portal's Wi-Fi status, at boot.

    No status file yet: still connecting, unless the portal hasn't written
    one in WIFI_STATUS_WAIT_S — it isn't installed (bench Pi, dev machine),
    so don't wait for it. Online, or told to work offline: awake.
    """
    if status is None:
        return "connecting" if waited_s < config.WIFI_STATUS_WAIT_S else "awake"
    return status["state"] if status["state"] in BOOT_STATES else "awake"


class Head:
    def __init__(self) -> None:
        self.state = "connecting"     # until the Wi-Fi gate lets it go (wifi_loop)
        self._boot_at = time.monotonic()
        self._qr_sent: dict[str, float] = {}   # Wi-Fi QR code → when it was last sent
        self._near_focus = False      # focus moved in for the QR code; home() before awake
        self.camera = Camera()
        self.ptz = Ptz()
        self.tracker = Tracker(self.camera, self.ptz)
        self.session = AutoSession()
        self.led = StatusRing()
        self.power = PowerMonitor()
        self.storage = StorageMonitor()
        self.local = LocalApi(self)
        self.cloud = CloudLink(self)
        self.mdns = Advertiser()
        self.session_hash: str | None = None   # whose session this is (owners.py)
        self._rec_path = ""
        self._rec_started = 0.0
        self.boxlog = BoxLog()     # person boxes beside the clip, for the players' overlay
        self._awake_since = time.monotonic()   # awake this long untouched → sleep
        self._warned = ""          # which warning we last announced
        self._tasks: set[asyncio.Task] = set()   # background uploads, kept alive
        self._countdown_sent = 0   # tracker.countdown as last sent to the app
        self._boxes_sent_at: float | None = None   # tracker.labelled_at last sent live
        self._jog = (0.0, 0.0)              # the app's joystick: pan, tilt in −1…1
        self._jog_at = float("-inf")        # when it last sent one

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

        awake: "person-in-frame" or "no-person-in-frame". Tracking: "search",
        then "found" (FOUND_CONFIRM_S to recording). Recording: "track", or
        "search" while it sweeps for a person it has lost.
        """
        if self.state == "awake":
            return "person-in-frame" if self.tracker.awake_person_in_frame else "no-person-in-frame"
        if self.state not in ("tracking", "recording"):
            return None
        return self.tracker.mode

    @property
    def acquire_stalled(self) -> bool:
        """Sweeping for a while and nobody has been found."""
        return self.state == "tracking" and self.tracker.acquire_stalled

    # ---- entry point ------------------------------------------------------
    async def run(self) -> None:
        self.ptz.start()
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

    async def serve(self) -> None:
        """run() until systemd stops the service with SIGTERM, then power_off().

        The power switch going off is a shutdown (docs/04, the power latch),
        so this is how a recording survives it."""
        task = asyncio.current_task()
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)
        try:
            await self.run()
        except asyncio.CancelledError:
            await self.power_off()

    async def power_off(self) -> None:
        """Close any recording, park the head and darken the ring.

        The latch keeps the power on until the Pi has halted, but not a
        moment longer. The clip is complete on the card; upload_loop sends
        it after the next boot.
        """
        print(f"[power] switched off in {self.state} — saving and parking")
        if self.state == "recording":
            await self.apply_state("sleep")     # stops the encoder, closing the file
        try:
            await asyncio.wait_for(self.report_state(), 2.0)
        except Exception:                       # noqa: BLE001 — going down regardless
            pass
        self.ptz.park()
        self.led.park()
        await self.mdns.stop()

    # ---- state ------------------------------------------------------------
    async def apply_state(self, new: str) -> None:
        """Single place state changes happen, whatever asked for it."""
        # No person detector (an OpenCV without HOG): a session could never
        # find anyone, nor record. Decline and say why.
        if (new in ("tracking", "recording") and self.state not in ("tracking", "recording")
                and self.camera.no_detector):
            print(f"[camera] refusing to start a session — {self.camera.no_detector}")
            await self.warn("no-detector", reason=self.camera.no_detector)
            return
        # Refuse to start filming onto a card that cannot hold the clip. The
        # encoder has no graceful failure: it writes until ENOSPC and leaves a
        # truncated file. Better to decline and say why.
        if new == "recording" and not self.storage.can_record():
            print(f"[storage] refusing to record — {self.storage.minutes_left:.0f} min left")
            await self.warn("storage-full", **self.storage.telemetry())
            new = "awake" if self.state == "tracking" else self.state
        if self.state == "recording" and new == "tracking":
            new = "awake"                  # stopping a recording ends the session

        old, self.state = self.state, new
        self.camera.set_awake(new != "sleep")
        if new == "awake":
            self._awake_since = time.monotonic()
        elif new == "sleep":
            self.tracker.forget_awake()
        if old not in ("tracking", "recording") and new in ("tracking", "recording"):
            self.tracker.reset_lock()     # a new session acquires afresh
        if new not in ("tracking", "recording"):
            self.session_hash = None       # the session is over, by whatever route
        if old != "recording" and new == "recording":
            self._rec_path = self.camera.start_recording()
            self._rec_started = time.monotonic()
            owners.stamp(self._rec_path, self.session_hash)
            self.boxlog.start(self._rec_path, self._rec_started)
            self.tracker.confirm()
            print(f"[rec] → {self._rec_path}")
        elif old == "recording" and new != "recording":
            self.camera.stop_recording()
            self.boxlog.stop()
            duration = time.monotonic() - self._rec_started
            print(f"[rec] stopped ({duration:.0f}s) — uploading in background")
            task = asyncio.create_task(
                upload_with_retry(self._rec_path, round(duration, 1), self.on_upload_progress))
            # The loop holds tasks only weakly: without a reference one can be
            # garbage-collected mid-upload.
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        self.led.set_state(new)
        self.camera.set_detect_fps(
            config.DETECT_FPS_TRACKING if new in ("tracking", "recording")
            else config.DETECT_FPS_AWAKE)
        if new in ("awake", "sleep", *BOOT_STATES):
            self.ptz.park()
        if new == "pairing" and not self._near_focus:
            self.ptz.set_focus(config.QR_FOCUS_M)   # a phone held up to the lens
            self._near_focus = True
        elif new not in BOOT_STATES and self._near_focus:
            self.ptz.home()                         # back to the boot focus and zoom
            self._near_focus = False

    async def start_session(self, target: str, session_hash: str | None) -> None:
        """Start a session — tracking, or straight to recording — owned by
        `session_hash`. apply_state() may still refuse (no detector, card
        full); then there is no session, and nobody owns it."""
        self.session_hash = session_hash
        await self.apply_state(target)
        if self.state not in ("tracking", "recording"):
            self.session_hash = None

    def session_secret(self, _pairing: object = None) -> str:
        """The secret for a session the app starts: a new one each time."""
        return owners.new_secret()

    async def report_state(self) -> None:
        """Tell everyone: direct app clients, Firestore, mDNS TXT."""
        await self.local.broadcast(self.local.state_payload())
        await self.cloud.report_state(self.state, self.session_hash)
        await self.mdns.update_state(public_state(self.state))

    async def warn(self, code: str, **detail) -> None:
        """Something the apps should show the user: direct clients now, and
        Firestore for apps connected through the relay."""
        await self.local.broadcast({"type": "warning", "code": code, **detail})
        await self.cloud.warning(code)

    async def on_upload_progress(self, msg: dict) -> None:
        await self.cloud.upload_progress(msg)
        await self.local.broadcast(msg)
        if msg.get("sent") == msg.get("total"):
            # Not the list: each phone asks for its own clips (local_api.py).
            await self.local.broadcast({"type": "recordingsChanged"})

    # ---- loops ------------------------------------------------------------
    async def control_loop(self) -> None:
        period = 1.0 / config.CONTROL_RATE_HZ
        while True:
            t0 = time.monotonic()
            await self.control_tick()
            await asyncio.sleep(max(0.0, period - (time.monotonic() - t0)))

    async def control_tick(self) -> None:
        """One 20 Hz tick: watch (awake) / search / track, and advance the session."""
        if self.state in BOOT_STATES:
            return                            # no tracking, no sessions, until it is up
        if self.state in ("tracking", "recording"):
            self.tracker.step()
            if self.state == "recording":
                self.boxlog.note(self.tracker.labelled_at, self.tracker.labelled)
            await self.announce_countdown()
            self.led.lost = self.tracker.lost_for() > config.LOST_HOLD_S
        else:
            if self.state == "awake":
                self.manual_aim()
                self.tracker.watch_awake()     # person in frame? (a session started now skips the sweep)
            self.led.lost = False
        # The person found for FOUND_CONFIRM_S starting the recording, or an
        # empty room ending the search, move the state through the same
        # apply_state() as any command.
        want = self.session.update(self.state, self.tracker.ready_to_record,
                                   self.tracker.searching_for())
        if want and want != self.state:
            print(f"[session] {self.state} → {want}")
            await self.apply_state(want)
            await self.report_state()
        if self.state == "awake" and self.watched:
            self._awake_since = time.monotonic()   # live view open: stay awake
        if (self.state == "awake"
                and time.monotonic() - self._awake_since > config.AWAKE_TIMEOUT_S):
            print(f"[sleep] awake {config.AWAKE_TIMEOUT_S:.0f} s with no session → sleep")
            await self.apply_state("sleep")
            await self.report_state()
        await self.send_boxes()
        self.led.awake_person = self.phase == "person-in-frame"
        self.led.searching = self.state == "tracking" and self.phase == "search"
        self.led.found = (self.tracker.found_for() / config.FOUND_CONFIRM_S
                          if self.state == "tracking" and self.phase == "found" else None)

    def jog(self, pan: float, tilt: float) -> None:
        """The app's joystick, sent ≈ 20 times a second while it is held.

        Only noted here; control_tick turns the head (manual_aim), so it moves
        at the control rate however fast messages arrive.
        """
        self._jog = (pan, tilt)
        self._jog_at = time.monotonic()

    def manual_aim(self) -> None:
        """Awake: turn the head by the joystick, until it stops sending.

        Only in awake. Tracking and recording own the head, and sleep and
        the boot states have no picture to aim by.
        """
        if time.monotonic() - self._jog_at > config.JOG_TIMEOUT_S:
            return
        pan, tilt = self._jog
        if pan or tilt:
            self.ptz.jog(pan, tilt, 1.0 / config.CONTROL_RATE_HZ)
            self._awake_since = time.monotonic()   # someone is using it

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

            if batt == "critical" and self.state not in ("sleep", *BOOT_STATES):
                print("[power] critical — stopping, parking and going to sleep")
                await self.apply_state("sleep")
                await self.report_state()
            elif store == "critical" and self.state == "recording":
                print("[storage] critical — stopping recording while it is still valid")
                await self.apply_state("awake")
                await self.report_state()

            for code, level, tele in (("battery-low", batt, self.power.telemetry),
                                      ("storage-low", store, self.storage.telemetry)):
                if level == "low" and self._warned != code:
                    self._warned = code
                    print(f"[health] {code}")
                    await self.warn(code, **tele())
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
            if self.state in LIVE_STATES:         # sleep and boot: no live view
                # Off the loop: the capture waits up to a frame and the JPEG
                # encode takes a few ms more, and the control tick shares it.
                jpg = await asyncio.to_thread(self.camera.preview_jpeg)
                if jpg:
                    self.local.publish_frame(jpg)   # direct viewers
                    await self.cloud.preview(jpg, self.live_boxes())   # and, while watched, the app anywhere
            await asyncio.sleep(max(0.0, period - (time.monotonic() - t0)))

    @property
    def watched(self) -> bool:
        """An app has the live view open: the stream here, or through Firebase."""
        return self.local.viewers > 0 or self.cloud.watched

    def live_boxes(self) -> list[list]:
        """The last detection's labelled boxes for the live view, `[[x, y, w,
        h, label], …]` in PREVIEW_SIZE pixels; none once stale or not up."""
        at = self.tracker.labelled_at
        if (at is None or self.state not in LIVE_STATES
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
        asyncio.run(head.serve())
    except KeyboardInterrupt:
        head.ptz.park()
        head.led.park()
        asyncio.run(head.mdns.stop())
