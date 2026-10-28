# Bench test — start here (without UWB)

The camera on a bench, off a mains power supply, wired with lever nuts and a
breadboard, to test the phone app end to end before building the real thing:
live view, control, recording, upload, sign-in, and each person seeing only
their own clips. No enclosure, nothing printed, no battery.

It runs the [camera-only build](../setup/README.md)'s software,
with two settings for what the bench leaves out. Everything bought for it
except the bench supply, cord, fuse, lever nuts and breadboard is a part of
the full build. The same rig with two UWB anchors and a tag is the
[bench test with UWB](../../with_uwb/bench/README.md).

| # | Doc | Covers | Time |
| --- | --- | --- | --- |
| 10 | [**Bill of materials**](10-bill-of-materials.md) | the parts you need, and what is left out and why | ≈ C$52 of new parts |
| 12 | [**Wiring guide**](12-wiring.md) | mains, 12 V, 5 V, I2C and the camera ribbon, with a check after each step | ≈ 1 h |
| 14 | [**Software setup**](14-software-setup.md) | the Pi, the camera software, the app, and the backend on your computer | ≈ 1 h |
| 15 | [**End-to-end test checklist**](15-verification.md) | the camera with a phone; then with the backend and two people | ≈ 30 min |

**Working directory.** Pi software: `src/without_uwb/device/`. The backend
and the app: `src/backend/`, `src/app_flutter/`, run from the repo root.
