"""WS2812B status ring, driven by the Pi over SPI.

This used to live on the base ESP32. With the pan stepper gone there is no
base controller any more, so the ring is wired straight to the Pi.

Data goes out of SPI0 MOSI (GPIO10) through a 74AHCT125, which shifts 3.3 V
logic up to 5 V. Enable SPI with `raspi-config` → Interface Options → SPI.

A Pi 4 could instead use the classic `rpi_ws281x` PWM+DMA driver on GPIO18,
which this build deliberately avoids: it needs the whole service to run as
root. SPI does not, and it keeps the module working unchanged if the camera
ever moves to a Pi 5, whose RP1 I/O chip cannot run the PWM+DMA driver at
all.
"""
from __future__ import annotations

import asyncio
import math
import time

try:
    import board
    import neopixel_spi
except (ImportError, NotImplementedError):   # dev machine / no SPI
    board = None
    neopixel_spi = None

from . import config

# state → (r, g, b), matching the app's status ring and docs/01
COLOURS = {
    "off":       (0, 0, 0),
    "connecting": (0xC8, 0xC8, 0xC8),   # white chasing: trying the saved Wi-Fi networks
    "pairing":   (0xC8, 0xC8, 0xC8),    # white, slow blink: show me a Wi-Fi QR code
    "sleep":     (0x2F, 0x6F, 0xED),    # one dim blue pixel: on, camera off
    "awake":      (0x2F, 0x6F, 0xED),    # blue: solid, or breathing slowly with a person in frame
    "tracking":  (0x1F, 0x9D, 0x55),    # green: chasing (search), filling (found)
    "recording": (0xD6, 0x45, 0x41),    # solid red, never blinks
    "error":     (0xF2, 0xA9, 0x3B),    # flashing orange
}


class StatusRing:
    def __init__(self) -> None:
        self._pixels = None
        self.state = "awake"
        self.lost = False          # tracking but no ranges → flash (not while recording)
        self.warn = False          # battery or storage low: dim + orange blink
        self.awake_person = False   # awake, person in frame → slow blue breath
        self.searching = False     # tracking, search → green chase
        self.found: float | None = None   # tracking, found: 0 → 1 over FOUND_CONFIRM_S → ring fills
        if neopixel_spi is not None:
            try:
                self._pixels = neopixel_spi.NeoPixel_SPI(
                    board.SPI(), config.LED_COUNT, auto_write=False,
                    brightness=config.LED_BRIGHTNESS)
            except Exception as exc:                 # noqa: BLE001 — never fatal
                print(f"[led] disabled: {exc}")

    def set_state(self, state: str) -> None:
        self.state = state

    async def run(self) -> None:
        """Render at 30 Hz forever. Cheap; the ring is 16 pixels."""
        while True:
            self._render()
            await asyncio.sleep(1 / 30)

    def _render(self) -> None:
        if not self._pixels:
            return
        r, g, b = COLOURS.get(self.state, COLOURS["awake"])
        t = time.monotonic()
        if self.warn:
            # A warning never hides the state: it dims the ring and slips a
            # short orange blink in once a second. Used for both low battery
            # and low card space, because the response is the same — finish
            # up soon.

            if (t % 1.0) < 0.12:
                r, g, b = COLOURS["error"]
            self._pixels.brightness = config.LED_BRIGHTNESS_LOW_BATT
        else:
            self._pixels.brightness = config.LED_BRIGHTNESS
        if self.state == "recording":
            k = 1.0                                                      # solid, even when lost
        elif self.state == "awake" and self.awake_person:
            k = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(math.pi * t))         # 0.5 Hz breath
        elif self.state == "pairing":
            k = 1.0 if (t % 2.0) < 1.0 else 0.08                         # 0.5 Hz blink
        elif self.lost and self.state == "tracking":
            k = 1.0 if (t % 0.5) < 0.25 else 0.15                        # 2 Hz flash
        else:
            k = 1.0
        colour = (int(r * k), int(g * k), int(b * k))
        if self.state == "sleep":
            # One pixel, dim: shows the camera is on and listening while
            # drawing next to nothing.
            self._pixels.fill((0, 0, 0))
            self._pixels[0] = tuple(int(c * config.SLEEP_LED_LEVEL) for c in colour)
        elif self.state == "connecting" or (
                self.state == "tracking" and self.searching and not self.lost):
            for i, c in enumerate(chase(colour, t, config.LED_COUNT)):
                self._pixels[i] = c
        elif self.state == "tracking" and self.found is not None:
            for i, c in enumerate(fill(colour, self.found, config.LED_COUNT)):
                self._pixels[i] = c
        else:
            self._pixels.fill(colour)
        self._pixels.show()

    def park(self) -> None:
        if self._pixels:
            self._pixels.fill((0, 0, 0))
            self._pixels.show()


def chase(colour: tuple[int, int, int], t: float, n: int) -> list[tuple[int, int, int]]:
    """Search: a bright head with a fading tail, once round per second.

    Clearly different from the filling ring (found) and from the 2 Hz flash
    (lost), so you can tell from the far side of the room whether the camera
    has found you yet.
    """
    head = (t % 1.0) * n
    out = []
    for i in range(n):
        behind = (head - i) % n            # pixels behind the head, 0 … n
        k = max(0.08, 1.0 - behind / 5.0)  # 5-pixel tail over a dim base
        out.append((int(colour[0] * k), int(colour[1] * k), int(colour[2] * k)))
    return out


def fill(colour: tuple[int, int, int], progress: float, n: int) -> list[tuple[int, int, int]]:
    """Found: the ring fills round, bright over a dim base, as FOUND_CONFIRM_S
    runs down — full when recording starts."""
    lit = max(1, math.ceil(min(1.0, progress) * n))
    k = [1.0 if i < lit else 0.1 for i in range(n)]
    return [(int(colour[0] * a), int(colour[1] * a), int(colour[2] * a)) for a in k]
