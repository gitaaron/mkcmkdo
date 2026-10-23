"""mDNS/Bonjour advertisement so the phone finds the camera on its own.

Publishes  <camera-name>._sportcam._tcp.local.  on the local API port, plus
an A record for `sportcam.local` so the app (or a browser) can reach the
camera by name without knowing its IP.

TXT records let the app show useful information in its picker *before*
connecting:

    name=SportCam          friendly name
    state=tracking         current camera state
    ver=1                  protocol version
    api=/api/call          callable prefix
    stream=/api/stream.mjpeg

Phones join gym Wi-Fi with a fresh DHCP lease every time and the Pi's IP
changes between visits — mDNS is what makes "open the app and it's there"
work without typing IP addresses.

NOTE: uses AsyncZeroconf. The synchronous Zeroconf API cannot be driven from
inside a running event loop — it schedules work onto that same loop and then
blocks waiting for it, which deadlocks (EventLoopBlocked).
"""
from __future__ import annotations

import socket

from zeroconf import IPVersion, ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

from . import config

SERVICE_TYPE = "_sportcam._tcp.local."


def _local_ips() -> list[bytes]:
    """Non-loopback IPv4 addresses, as packed bytes for zeroconf."""
    ips: list[bytes] = []
    try:
        # UDP connect to a routable address — no packets sent, but the kernel
        # picks the interface/address it would use, i.e. the active network.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.append(socket.inet_aton(s.getsockname()[0]))
        s.close()
    except OSError:
        pass
    if not ips:  # hotspot mode: NetworkManager's shared-mode gateway
        ips.append(socket.inet_aton("10.42.0.1"))
    return ips


def _service_info(state: str) -> ServiceInfo:
    return ServiceInfo(
        SERVICE_TYPE,
        f"{config.CAMERA_NAME}.{SERVICE_TYPE}",
        addresses=_local_ips(),
        port=config.LOCAL_API_PORT,
        properties={
            "name": config.CAMERA_NAME,
            "state": state,
            "ver": "1",
            "api": "/api/call",
            "stream": "/api/stream.mjpeg",
        },
        server=f"{config.MDNS_HOSTNAME}.",
    )


class Advertiser:
    """Async mDNS advertiser. All methods must be awaited from the loop."""

    def __init__(self) -> None:
        self._azc: AsyncZeroconf | None = None
        self._info: ServiceInfo | None = None

    async def start(self, state: str = "awake") -> None:
        self._azc = AsyncZeroconf(ip_version=IPVersion.V4Only)
        self._info = _service_info(state)
        await self._azc.async_register_service(self._info)
        print(f"[mdns] advertising {config.CAMERA_NAME}.{SERVICE_TYPE} "
              f"as {config.MDNS_HOSTNAME}:{config.LOCAL_API_PORT}")

    async def update_state(self, state: str) -> None:
        """Refresh the TXT record so pickers show the live state.

        ServiceInfo.properties is read-only, so re-announce a fresh info
        object rather than mutating the registered one.
        """
        if not self._azc:
            return
        try:
            self._info = _service_info(state)
            await self._azc.async_update_service(self._info)
        except Exception as err:  # noqa: BLE001 — never let mDNS break control
            print(f"[mdns] update failed: {err}")

    async def stop(self) -> None:
        if self._azc and self._info:
            await self._azc.async_unregister_service(self._info)
            await self._azc.async_close()
            self._azc = None
