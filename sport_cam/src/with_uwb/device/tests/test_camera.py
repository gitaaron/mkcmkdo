"""Frames and the detector thread, with no camera attached.

Frames are fetched on demand and shared: whoever asks while one is being
fetched gets that same frame, stamped with when it was exposed, and converts
only what it needs of it.

A detection takes a few hundred milliseconds on a Pi 4. Run inside the 20 Hz
control tick, it froze the servos that long every detection, so it runs on
its own thread. What is checked is what threads get wrong: each result is
handed over exactly once, the caller never waits on a detection, and a result
in flight when the camera sleeps is dropped rather than acted on after waking.

    python3 device/tests/test_camera.py
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import camera, config
from sportcam.camera import Camera, Frame, sensor_clock_offset

camera.Picamera2 = None      # never the real camera, even on the Pi

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


class FakeSensor:
    def start(self):
        pass

    def stop(self):
        pass


DETECT_S = 0.25          # about what a detection takes on a Pi 4
BOX = (100, 50, 80, 200)


def slow_camera() -> Camera:
    """A Camera whose detection takes DETECT_S and finds one person."""
    cam = Camera()
    cam._cam, cam._detector = FakeSensor(), object()
    cam.starts = 0

    def detect(strip_cx):
        cam.starts += 1
        taken = time.monotonic()
        time.sleep(DETECT_S)
        return [BOX], taken

    cam._detect = detect
    cam.set_detect_fps(config.DETECT_FPS_TRACKING)
    cam._start_detector()
    return cam


def strip_and_full_frame() -> None:
    """The strip around the followed person, with a whole frame now and then."""
    import numpy as np
    from sportcam.detector import score_of
    from sportcam.detector import Person
    cam = Camera()
    cam._detector = object()
    cam.frame = lambda newer_than=None: Frame.from_rgb(np.zeros((720, 1280, 3), np.uint8), 12.5)
    seen = []

    passes = []

    def found(rgb, tiles=True):
        seen.append(rgb.shape[1])
        passes.append(tiles)
        return [Person((10, 10, 200, 400), 0.7)]
    cam.detect_frame = found
    took = [cam._detect(640.0) for _ in range(config.DETECT_FULL_EVERY)]
    out = [boxes for boxes, _at in took]
    check("a detection comes with when its frame was exposed", {at for _b, at in took} == {12.5})
    check("the strip is searched…", seen[0] < 1280 and out[0][0][0] > 10, f"{seen}")
    check("…with every DETECT_FULL_EVERY'th the whole frame",
          seen[:-1] == [seen[0]] * (config.DETECT_FULL_EVERY - 1) and seen[-1] == 1280, f"{seen}")
    check("…in one pass, so it leaves no gap in the head's guidance", passes[-1] is False)
    check("a box keeps its score through the crop, and gets its colours",
          score_of(out[0][0]) == 0.7 and out[0][0].look is not None)

    # how detection is doing: one line every DETECT_LOG_EVERY
    saved, config.DETECT_LOG_EVERY = config.DETECT_LOG_EVERY, config.DETECT_FULL_EVERY
    cam._seq += 1                                   # as the detector thread publishing a result…
    cam.captured_at = time.monotonic() - 0.2
    cam._cam = object()
    cam.person_boxes()                              # …and the tracker taking it 200 ms on
    said = io.StringIO()
    with contextlib.redirect_stdout(said), cam._lock:
        cam._log_detection()
    line = said.getvalue()
    check("the [detect] line: how many, how long the detector took, how old a result was "
          "when the tracker took it, how many were whole-frame",
          line.startswith(f"[detect] {config.DETECT_FULL_EVERY} detections: detector ")
          and "exposure to tracker 2" in line and "1 whole-frame" in line, line)
    said = io.StringIO()
    with contextlib.redirect_stdout(said), cam._lock:
        cam._log_detection()
    check("…and it starts counting afresh", said.getvalue() == "")
    config.DETECT_LOG_EVERY = saved


class Request:
    def __init__(self, yuv, meta) -> None:
        self.yuv, self.meta, self.released = yuv, meta, False

    def make_array(self, _stream):
        return self.yuv

    def get_metadata(self):
        return self.meta

    def release(self) -> None:
        self.released = True


class Sensor(FakeSensor):
    """Picamera2's part in a capture: a frame takes FRAME_S to arrive, and
    carries the time it was exposed on the clock `stamp` reads."""
    FRAME_S = 0.05

    def __init__(self, stamp=None) -> None:
        self.captures = 0
        self.stamp = stamp
        self.requests: list[Request] = []

    def capture_request(self):
        import cv2
        import numpy as np
        self.captures += 1
        exposed = None if self.stamp is None else self.stamp()
        time.sleep(self.FRAME_S)
        rgb = np.zeros((720, 1280, 3), np.uint8)
        rgb[:, :, 0] = 200                           # a red room
        rgb[:8, :8] = self.captures                  # each frame its own
        meta = {} if exposed is None else {"SensorTimestamp": int(exposed * 1e9),
                                           "ExposureTime": 10_000}
        self.requests.append(Request(cv2.cvtColor(rgb, cv2.COLOR_RGB2YUV_I420), meta))
        return self.requests[-1]


def frames() -> None:
    """Shared, timestamped frames."""
    import cv2
    import numpy as np
    print("frames\n")
    cam = Camera()
    sensor = cam._cam = Sensor(stamp=time.monotonic)
    got: list = []
    threads = [threading.Thread(target=lambda: got.append(cam.frame())) for _ in range(3)]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    took = time.monotonic() - t0
    check("three asking at once share one frame: one capture, not a queue of three",
          sensor.captures == 1 and len(got) == 3 and got[0] is got[1] is got[2]
          and took < 2 * Sensor.FRAME_S, f"{sensor.captures} captures in {took * 1000:.0f} ms")
    first = got[0]
    check("the sensor's buffer is given back", all(r.released for r in sensor.requests))
    again = cam.frame()
    check("asking again fetches a new frame", again is not first and again.seq > first.seq
          and sensor.captures == 2)
    newer = cam.frame(newer_than=first)
    check("newer than one already seen: the latest will do, nothing fetched",
          newer is again and sensor.captures == 2)
    check("…and newer than the latest fetches",
          cam.frame(newer_than=again) is not again and sensor.captures == 3)
    n = sensor.captures
    time.sleep(0.2)
    check("nobody asking: nothing is captured", sensor.captures == n)

    now = time.monotonic()
    f = cam.frame()
    exposed = now + 0.005                            # its stamp, and half its 10 ms exposure
    check("a frame's time is when it was exposed (the camera's own stamp), not when it arrived",
          abs(f.at - exposed) < 0.02 and time.monotonic() - f.at >= Sensor.FRAME_S - 0.01,
          f"{f.at - now:+.3f} s")
    check("the camera's stamps on our clock already: nothing to add",
          sensor_clock_offset(now - 0.03, now) == 0.0)
    check("…from another clock altogether: not used",
          sensor_clock_offset(now + 5000.0, now) in (None, time.monotonic()
                                                    - time.clock_gettime(time.CLOCK_BOOTTIME)))
    cam2 = Camera()
    cam2._cam = Sensor(stamp=lambda: time.monotonic() + 5000.0)
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        a = cam2.frame()
        arrived = time.monotonic()
        cam2.frame()
    check("stamps that can't be placed: said once, and the time guessed from the arrival",
          said.getvalue().count("unknown clock") == 1
          and abs(a.at - (arrived - config.AF_FRAME_LAG_S)) < 0.02, said.getvalue())
    cam3 = Camera()
    cam3._cam = Sensor()                             # no stamp at all
    b = cam3.frame()
    check("no stamp: guessed too", abs(b.at - (time.monotonic() - config.AF_FRAME_LAG_S)) < 0.02)

    check("luma is the frame's own grey plane: a view, nothing converted",
          f.luma.shape == (720, 1280) and np.shares_memory(f.luma, f.yuv))
    rgb = f.rgb
    check("rgb is converted once and kept", f.rgb is rgb and rgb.shape == (720, 1280, 3)
          and rgb[400, 600, 0] > 150 and rgb[400, 600, 2] < 60, f"{rgb[400, 600]}")
    check("bgr is the same picture, blue first, for the JPEG encoder",
          f.bgr()[400, 600, 2] > 150 and f.bgr()[400, 600, 0] < 60)
    back = cv2.imdecode(np.frombuffer(cam.preview_jpeg(), np.uint8), cv2.IMREAD_COLOR)
    check("the live view's JPEG keeps its colours (a red room is red)",
          back.shape == (720, 1280, 3) and back[400, 600, 2] > 150 and back[400, 600, 0] < 80,
          f"{back[400, 600]}")
    plain = Frame.from_rgb(rgb, 3.0)
    check("a frame made from an RGB picture gives the same grey and colours",
          plain.luma.shape == (720, 1280) and plain.rgb is rgb and plain.at == 3.0
          and abs(int(plain.luma[400, 600]) - int(f.luma[400, 600])) < 12)
    check("_capture, for the tools: the frame as RGB", cam._capture().shape == (720, 1280, 3))

    cam.awake = False
    check("asleep: no frame, no capture", cam.frame() is None and cam.preview_jpeg() is None
          and cam._capture() is None)
    print()


def main() -> None:
    frames()
    strip_and_full_frame()
    print("camera detector thread\n")
    cam = slow_camera()
    worst, fresh_n = 0.0, 0
    check_box, took_at = False, None
    t0 = time.monotonic()
    while time.monotonic() - t0 < 2.0:              # a 20 Hz control loop, for 2 s
        t = time.monotonic()
        boxes, fresh = cam.person_boxes()
        worst = max(worst, time.monotonic() - t)
        if fresh:
            fresh_n += 1
            check_box = boxes == [BOX]
            took_at = cam.captured_at
        time.sleep(0.05)
    check("the control loop never waits on a detection", worst < 0.02, f"{worst * 1000:.0f} ms")
    expect = 2.0 * config.DETECT_FPS_TRACKING
    check("detections arrive at DETECT_FPS_TRACKING", expect - 2 <= fresh_n <= expect + 1,
          f"{fresh_n} in 2 s")
    check("each result is handed over once, with its boxes", fresh_n == cam.starts or
          fresh_n == cam.starts - 1, f"{fresh_n} handed, {cam.starts} run")
    check("…and its boxes", check_box)
    check("captured_at is when the frame was exposed, before the detection finished",
          took_at is not None and time.monotonic() - took_at >= DETECT_S - 0.01)

    # sleep while a detection is in flight: its result must not survive the wake
    cam = slow_camera()
    while cam.starts == 0:
        time.sleep(0.01)
    cam.set_awake(False)
    time.sleep(DETECT_S + 0.1)                      # the in-flight detection finishes
    cam.set_awake(True)
    boxes, fresh = cam.person_boxes()
    check("a detection in flight at sleep is dropped, not handed over after waking",
          not fresh and boxes == [], f"{boxes} fresh={fresh}")
    time.sleep(config.CAMERA_WARMUP_S + DETECT_S + 0.2)
    boxes, fresh = cam.person_boxes()
    check("…and detection resumes after the warm-up", fresh and boxes == [BOX])

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all camera checks passed")


if __name__ == "__main__":
    main()
