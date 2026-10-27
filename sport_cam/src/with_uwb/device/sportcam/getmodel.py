"""Fetch the MobileNet-SSD person detector's weights (DETECTOR = "ssd").

    python3 -m sportcam.getmodel

Downloads TensorFlow's SSDLite-MobileNetV2 COCO release (≈ 48 MB), checks
its SHA-256, and keeps only the frozen graph (≈ 19 MB) as
models/ssdlite_mobilenet_v2_coco.pb. The text graph OpenCV needs beside it
(…pbtxt) is in the repo: generated once with OpenCV's
samples/dnn/tf_text_graph_ssd.py from the release's pipeline.config.
"""
from __future__ import annotations

import hashlib
import os
import tarfile
import tempfile
import urllib.request

from .detector import MODEL_DIR, SSD_WEIGHTS

URL = ("http://download.tensorflow.org/models/object_detection/"
       "ssdlite_mobilenet_v2_coco_2018_05_09.tar.gz")
TAR_SHA256 = "542445cce834dbfbb7df1991425d475e85a2d7ec68c60a4f262bb18aac10c8b2"
PB_SHA256 = "69e5b91a3e24b3d424f3c7590ce404598e1a0fa334a2254e57fdb3014ebbb589"
MEMBER = "ssdlite_mobilenet_v2_coco_2018_05_09/frozen_inference_graph.pb"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if os.path.exists(SSD_WEIGHTS) and sha256(SSD_WEIGHTS) == PB_SHA256:
        print(f"already there: {os.path.normpath(SSD_WEIGHTS)}")
        return
    with tempfile.TemporaryDirectory() as tmp:
        tar = os.path.join(tmp, "model.tar.gz")
        print(f"downloading {URL} …")
        urllib.request.urlretrieve(URL, tar)
        if sha256(tar) != TAR_SHA256:
            raise SystemExit("checksum mismatch — not using it")
        with tarfile.open(tar) as t:
            src = t.extractfile(MEMBER)
            os.makedirs(MODEL_DIR, exist_ok=True)
            part = SSD_WEIGHTS + ".part"
            with open(part, "wb") as out:
                out.write(src.read())
        if sha256(part) != PB_SHA256:
            os.remove(part)
            raise SystemExit("checksum mismatch in the graph — not using it")
        os.replace(part, SSD_WEIGHTS)
    print(f"saved {os.path.normpath(SSD_WEIGHTS)}. Set DETECTOR = \"ssd\" in config.py to use it.")


if __name__ == "__main__":
    main()
