# Bench test — start here (with UWB)

The camera on a bench, off a mains power supply, wired with lever nuts and a
breadboard, with two UWB anchors taped to a stick and a tag, to test the phone
app end to end before building the real thing: live view, control, pairing a
tag, a tag-started recording that belongs to its wearer, upload, sign-in, and
each person seeing only their own clips. No enclosure, nothing printed, no
battery.

It runs the [UWB build](../setup/README.md)'s software, with a few settings
for what the bench leaves out. Everything bought for it except the bench
supply, cord, fuse, lever nuts and breadboard is a part of the full build.
The same rig without the radios is the
[bench test without UWB](../../without_uwb/bench/README.md).

| # | Doc | Covers | Time |
| --- | --- | --- | --- |
| 10 | [**Bill of materials**](10-bill-of-materials.md) | the parts you need, and what is left out and why | ≈ C$52 of new parts |
| 12 | [**Wiring guide**](12-wiring.md) | mains, 12 V, 5 V, I2C, the camera ribbon and the two anchors, with a check after each step | ≈ 1 h |
| 14 | [**Software setup**](14-software-setup.md) | the radios, the Pi, the camera software, the app, and the backend on your computer | ≈ 1.5 h |
| 15 | [**End-to-end test checklist**](15-verification.md) | the camera with a phone and the tag; then with the backend and two people | ≈ 40 min |

**Working directory.** Pi software: `src/with_uwb/device/`. The backend
and the app: `src/backend/`, `src/app_flutter/`, run from the repo root.
