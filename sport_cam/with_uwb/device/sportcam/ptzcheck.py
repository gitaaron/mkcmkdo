"""Bench check for the PTZ base — run this before the first tracking session.

    python -m sportcam.ptzcheck

Walks the two servos to their configured soft limits one axis at a time so you
can watch for the lens or the camera ribbon binding, then centres both. Use it
to confirm three things in `config.py`:

  * ``PAN_CENTER_RAW`` / ``TILT_CENTER_RAW`` really do centre the axes,
  * ``PAN_SIGN`` / ``TILT_SIGN`` match the direction you expect,
  * the soft limits stop short of anything mechanical.

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


def main() -> None:
    ptz = Ptz()
    if not ptz.focuser.available:
        print("No I2C bus — is this running on the Pi, with I2C enabled?")
        return
    print("Centring both axes.")
    ptz.park()
    time.sleep(1.0)
    try:
        sweep("pan", ptz.set_pan, config.PAN_MIN_DEG, config.PAN_MAX_DEG)
        sweep("tilt", ptz.set_tilt, config.TILT_MIN_DEG, config.TILT_MAX_DEG)
        print("\nHoming zoom and focus.")
        ptz.home()
        for mm in (config.ZOOM_MIN_MM, config.ZOOM_MAX_MM, config.ZOOM_MIN_MM):
            ptz.set_zoom_mm(mm)
            print(f"  zoom → {mm:.1f} mm")
            time.sleep(2.5)
    except KeyboardInterrupt:
        pass
    finally:
        ptz.park()
        print("\nParked.")


if __name__ == "__main__":
    main()
