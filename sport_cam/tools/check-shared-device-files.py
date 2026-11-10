#!/usr/bin/env python3
"""Check that the device files both builds share are still the same file.

The two builds (src/with_uwb/device, src/without_uwb/device) each carry their
own copy of the code that doesn't depend on ranging: the lens, autofocus,
framing, the calibration tools, and their tests. A fix made in one copy and
not the other is a bug waiting in the second build, so a change to any file
listed here must be made in both.

    python3 tools/check-shared-device-files.py           check
    python3 tools/check-shared-device-files.py --list    print the shared files

A file that has to differ between the builds comes off the list, with the
reason in the commit.
"""
from __future__ import annotations

import os
import sys

BUILDS = ("with_uwb", "without_uwb")
SHARED = (
    "sportcam/autofocus.py",
    "sportcam/focuscal.py",
    "sportcam/framing.py",
    "sportcam/lenscheck.py",
    "sportcam/motion.py",
    "sportcam/ptz.py",
    "sportcam/ptzcheck.py",
    "sportcam/samples.py",
    "tests/test_autofocus.py",
    "tests/test_camera.py",
    "tests/test_detector.py",
    "tests/test_lens_together.py",
    "tests/test_lenstools.py",
    "tests/test_ptz.py",
    "tests/test_samples.py",
)


def differing(root: str) -> list[str]:
    """The shared files that are missing from a build or differ between them."""
    out = []
    for rel in SHARED:
        paths = [os.path.join(root, "src", b, "device", rel) for b in BUILDS]
        missing = [p for p in paths if not os.path.isfile(p)]
        if missing:
            out.append(f"{rel}: missing {', '.join(os.path.relpath(p, root) for p in missing)}")
            continue
        first, second = (open(p, "rb").read() for p in paths)
        if first != second:
            out.append(f"{rel}: differs between {BUILDS[0]} and {BUILDS[1]}")
    return out


def main() -> int:
    if "--list" in sys.argv[1:]:
        print("\n".join(SHARED))
        return 0
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    bad = differing(root)
    if bad:
        print("shared device files: the two builds' copies must be identical")
        for line in bad:
            print(f"  {line}")
        print("Make the same change in both builds (or take the file off SHARED in "
              "tools/check-shared-device-files.py, saying why).")
        return 1
    print(f"shared device files: OK ({len(SHARED)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
