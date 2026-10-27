"""Person detectors: HOG, or MobileNet-SSD on OpenCV's DNN module.

`DETECTOR` in config picks one; if it cannot load, `make_detector()` falls
back to the other, and only with neither does the camera refuse sessions.

    hog  OpenCV's HOG + linear SVM. No model file. Trained on upright
         pedestrians: weak on climbing poses, back views, bulky clothing.
         Gone from OpenCV 5's main module.
    ssd  SSDLite-MobileNetV2 trained on COCO, run by cv2.dnn (OpenCV 4 and 5
         alike). Far better on unusual poses and partly hidden bodies; the
         whole input is squeezed to 300×300, so a small, far person is its
         weak spot. Weights: `python3 -m sportcam.getmodel`.

Both return boxes in the **HOG convention** the rest of the code is tuned
for: a padded box whose body is PERSON_IN_BOX_H of its height and
PERSON_IN_BOX_W of its width. SSD's boxes hug the body, so they are padded
about their centre to match, and zoom, focus, the bystander gate and the
overlays need no second set of constants.
"""
from __future__ import annotations

import os

try:
    import cv2
except ImportError:
    cv2 = None

from . import config

Box = tuple[int, int, int, int]      # x, y, w, h in the image's pixels

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
SSD_WEIGHTS = os.path.join(MODEL_DIR, "ssdlite_mobilenet_v2_coco.pb")
SSD_GRAPH = os.path.join(MODEL_DIR, "ssdlite_mobilenet_v2_coco.pbtxt")
_COCO_PERSON = 1


class HogDetector:
    name = "hog"

    def __init__(self) -> None:
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, img) -> list[Box]:
        h, w = img.shape[:2]
        sw = config.DETECT_DOWNSCALE_W
        sh = max(1, int(round(h * sw / w)))
        rects, _ = self._hog.detectMultiScale(cv2.resize(img, (sw, sh)), winStride=(8, 8))
        sx, sy = w / sw, h / sh
        return [(int(x * sx), int(y * sy), int(bw * sx), int(bh * sy)) for x, y, bw, bh in rects]


class SsdDetector:
    name = "ssd"

    def __init__(self, net=None) -> None:
        self._net = net if net is not None else cv2.dnn.readNetFromTensorflow(SSD_WEIGHTS, SSD_GRAPH)

    def detect(self, img) -> list[Box]:
        tiles = _tiles(img)
        found: list[tuple[Box, bool]] = []          # (box in the image, cut by a seam)
        for x0, tile in tiles:
            tw = tile.shape[1]
            edge = 0.03 * tw
            inner_left, inner_right = x0 > 0, x0 + tw < img.shape[1]
            for _score, (x, y, w, h) in self._people(tile):
                cut = (inner_left and x <= edge) or (inner_right and x + w >= tw - edge)
                found.append(((x + x0, y, w, h), cut))
        return [_pad(b) for b in _merge(found)]

    def _people(self, img) -> list[tuple[float, Box]]:
        h, w = img.shape[:2]
        self._net.setInput(cv2.dnn.blobFromImage(img, size=(config.SSD_INPUT, config.SSD_INPUT),
                                                 swapRB=config.SSD_SWAP_RB))
        out = []
        for d in self._net.forward().reshape(-1, 7):
            if int(d[1]) == _COCO_PERSON and d[2] >= config.SSD_CONFIDENCE:
                x1, y1 = max(0.0, d[3]) * w, max(0.0, d[4]) * h
                x2, y2 = min(1.0, d[5]) * w, min(1.0, d[6]) * h
                if x2 > x1 and y2 > y1:
                    out.append((float(d[2]), (int(x1), int(y1), int(x2 - x1), int(y2 - y1))))
        return out


def _tiles(img):
    """The whole image, or — when it is much wider than tall (searching the
    whole frame) — two overlapping halves, so a far person is not squeezed
    to a few pixels at the network's 300×300 input."""
    h, w = img.shape[:2]
    if not config.SSD_WIDE_TILES or w < 1.4 * h:
        return [(0, img)]
    tw = max(h, int(w * 0.55))
    return [(0, img[:, :tw]), (w - tw, img[:, w - tw:])]


def _merge(found: list[tuple[Box, bool]]) -> list[Box]:
    """One box per person across the two tiles.

    Someone standing across the seam is cut off at the inner edge of one tile
    or both. Two cut boxes from either side that overlap and share most of
    their height are the two halves of one person: joined. Then, biggest
    first, a box lying mostly (CONTAINED) inside one already kept — the
    cut-off view of someone the other tile saw whole — is dropped.
    """
    CONTAINED = 0.6
    cut = [b for b, c in found if c]
    whole = [b for b, c in found if not c]
    joined: list[Box] = []
    while cut:
        b = cut.pop()
        for i, o in enumerate(cut):
            if _overlap(b, o) > 0 and _shared_height(b, o) > 0.5:
                b = _union(b, cut.pop(i))
                break
        joined.append(b)
    kept: list[Box] = []
    for b in sorted(whole + joined, key=lambda b: b[2] * b[3], reverse=True):
        if not any(_overlap(b, k) > CONTAINED * b[2] * b[3] for k in kept):
            kept.append(b)
    return kept


def _shared_height(a: Box, b: Box) -> float:
    """Vertical overlap as a share of the shorter box."""
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0, h) / max(1, min(a[3], b[3]))


def _union(a: Box, b: Box) -> Box:
    x1, y1 = min(a[0], b[0]), min(a[1], b[1])
    return (x1, y1, max(a[0] + a[2], b[0] + b[2]) - x1, max(a[1] + a[3], b[1] + b[3]) - y1)


def _overlap(a: Box, b: Box) -> float:
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0, w) * max(0, h)


def _pad(box: Box) -> Box:
    """A body-tight box → the padded HOG-convention box around it."""
    x, y, w, h = box
    pw, ph = w / config.PERSON_IN_BOX_W, h / config.PERSON_IN_BOX_H
    return (int(round(x + w / 2 - pw / 2)), int(round(y + h / 2 - ph / 2)),
            int(round(pw)), int(round(ph)))


def make_detector():
    """(detector, None), or (None, why not): `DETECTOR` first, the other as fallback."""
    if cv2 is None:
        return None, "OpenCV is not installed"
    makers = {"hog": _hog, "ssd": _ssd}
    order = [config.DETECTOR] + [n for n in makers if n != config.DETECTOR]
    why = []
    for name in order:
        det, reason = makers[name]()
        if det is not None:
            if name != config.DETECTOR:
                print(f"[camera] {why[0]} — using the {name} detector instead")
            return det, None
        why.append(reason)
    return None, "; ".join(why)


def _hog():
    if not hasattr(cv2, "HOGDescriptor"):
        return None, f"OpenCV {cv2.__version__} has no HOG person detector"
    return HogDetector(), None


def _ssd():
    if not (os.path.exists(SSD_WEIGHTS) and os.path.exists(SSD_GRAPH)):
        return None, "no MobileNet-SSD model (python3 -m sportcam.getmodel)"
    try:
        return SsdDetector(), None
    except cv2.error as err:
        return None, f"MobileNet-SSD would not load: {err}"
