"""Tracking control loops (docs/04): pan from UWB, tilt from CV, zoom from
distance. Produces pan-velocity commands; applies tilt/zoom directly."""
from __future__ import annotations

import math
import time

from simple_pid import PID

from . import config
from .camera import Camera
from .lens import Lens
from .tilt import Tilt
from .uwb import UwbArray


class Tracker:
    def __init__(self, uwb: UwbArray, camera: Camera, lens: Lens, tilt: Tilt) -> None:
        self.uwb = uwb
        self.camera = camera
        self.lens = lens
        self.tilt = tilt
        self._pan_pid = PID(**config.PAN_PID, setpoint=0.0,
                            output_limits=(-config.PAN_MAX_DPS, config.PAN_MAX_DPS))
        self._tilt_pid = PID(**config.TILT_PID, setpoint=0.0, output_limits=(-30, 30))
        self._last_zoom = 0.0
        self.last_fix_at = time.monotonic()
        self.dist_m: float | None = None

    def lost_for(self) -> float:
        return time.monotonic() - self.last_fix_at

    def step(self) -> float:
        """One 20 Hz iteration. Returns pan velocity (deg/s) to send to base."""
        pan_dps = 0.0

        fix = self.uwb.fix()
        if fix and fix.age_s < 0.5:
            self.last_fix_at = time.monotonic()
            self.dist_m = fix.dist_m
            # PID works in degrees of bearing error
            pan_dps = -self._pan_pid(math.degrees(fix.theta_rad))
            self._update_zoom(fix.dist_m)

        bbox = self.camera.person_bbox()
        if bbox:
            x, y, w, h = bbox
            cx_err = (x + w / 2) - config.PREVIEW_SIZE[0] / 2
            cy_err = (y + h / 2) - config.PREVIEW_SIZE[1] / 2
            pan_dps += -0.02 * cx_err                      # fine pan trim
            self.tilt.nudge(-self._tilt_pid(cy_err) * 0.05)  # tilt is CV-only

        return max(-config.PAN_MAX_DPS, min(config.PAN_MAX_DPS, pan_dps))

    def _update_zoom(self, dist_m: float) -> None:
        if abs(dist_m - self._last_zoom) < config.ZOOM_DEADBAND_M:
            return
        self._last_zoom = dist_m
        # Thin-lens: image height = f·H/d. For a ~1.8 m subject to fill
        # TARGET_FRAME_FRACTION of the IMX219's 2.76 mm sensor height:
        # f = fraction · 2.76 · d / 1.8  ≈ 0.61 mm per metre of distance.
        efl_mm = config.TARGET_FRAME_FRACTION * 2.76 * dist_m / 1.8
        self.lens.set_zoom_mm(efl_mm)
