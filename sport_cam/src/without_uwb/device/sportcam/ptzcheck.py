"""Bench check for the PTZ base — run this before the first tracking session.

    python -m sportcam.ptzcheck

Walks the two servos to their configured soft limits one axis at a time so you
can watch for the lens or the camera ribbon binding, then centres both. Use it
to confirm three things in `config.py`:

  * ``PAN_CENTER_RAW`` / ``TILT_CENTER_RAW`` really do centre the axes,
  * ``PAN_SIGN`` / ``TILT_SIGN`` match the direction you expect,
  * the soft limits stop short of anything mechanical,
  * with ``SERVO_DRIVER = "pigpio"``, the pan creeps in tenths of a degree
    (the last step): smooth, not in visible one-degree ticks.

Nothing here is destructive; it moves slowly and stops on Ctrl-C.
"""
from __future__ import annotations

import time

from . import config
from .ptz import Ptz


def sweep(name: str, setter, lo: float, hi: float) -> None:
    print(f"\n{name}: {lo:+.0f}° → {hi:+.0f}°  (watch for binding, Ctrl-C to stop)")
    for deg in list(range(int(lo), int(hi) + 1, 5)) + list(range(int(hi), int(lo) - 1, -5)):
        setter(float(deg))
        print(f"  {deg:+4d}°", end="\r", flush=True)
        time.sleep(0.12)
    setter(0.0)
    print(f"  {name} centred      ")


def creep(ptz: Ptz) -> None:
    """Pan 0° → 3° in 0.1° steps over 6 s: what a slow pan zoomed in asks for."""
    print(f"\nfine steps ({config.SERVO_DRIVER}): pan 0° → 3° in 0.1° steps, slowly")
    for i in range(31):
        ptz.set_pan(i / 10)
        time.sleep(0.2)
    if config.SERVO_DRIVER == "pigpio":
        print("  it should creep smoothly. Ticks of about a degree: the servo is still on"
              " the PTZ controller, not GPIO12/13")
    else:
        print("  the registers take whole degrees, so expect three ticks")
    ptz.set_pan(0.0)


def main() -> None:
    ptz = Ptz()
    if not ptz.focuser.available:
        print("No I2C bus — is this running on the Pi, with I2C enabled?")
        return
    if not ptz.servos.available:
        print("pigpiod is not running: sudo systemctl enable --now pigpiod")
        return
    if ptz.focuser.firmware is None:
        print("The PTZ controller doesn't answer at 0x0c: its cable (bench wiring guide)")
        return
    print(f"Waking the controller (firmware 0x{ptz.focuser.firmware:04x}); "
          "the lens resets, up to half a minute.")
    ptz.start()
    time.sleep(1.0)
    try:
        sweep("pan", ptz.set_pan, config.PAN_MIN_DEG, config.PAN_MAX_DEG)
        sweep("tilt", ptz.set_tilt, config.TILT_MIN_DEG, config.TILT_MAX_DEG)
        creep(ptz)
        print("\nHoming zoom and focus.")
        ptz.home()
        print("Zoom: the framing should close in and open out again "
              "(the sharpness may drift; that is fine).")
        for mm in (config.ZOOM_MIN_MM, config.ZOOM_MAX_MM, config.ZOOM_MIN_MM):
            ptz.set_zoom_mm(mm, urgent=True)
            print(f"  zoom → {mm:.1f} mm")
            time.sleep(2.5)
        print("Focus: the framing should stay put while the picture goes soft and sharp.")
        for pos in (0.0, 0.5, 1.0, 0.5):
            ptz.set_focus_pos(pos)
            print(f"  focus motor → {pos:.0%} of its travel")
            time.sleep(2.0)
        print(f"  (LENS_SWAP_ZOOM_FOCUS = {config.LENS_SWAP_ZOOM_FOCUS}: if zoom and focus "
              "did each other's job, flip it in config.py)")
    except KeyboardInterrupt:
        pass
    finally:
        ptz.park()
        print("\nParked.")


if __name__ == "__main__":
    main()
