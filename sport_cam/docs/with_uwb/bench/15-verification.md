# 15 — End-to-end test checklist (bench test, with UWB)

What to check, with the bench rig running ([14](14-software-setup.md)), to know
the camera, the backend and the app work together. Part A needs only the
camera and a phone; part B adds the backend on your computer. Each row says
what to do and what you should see.

## A. The camera alone

App built with plain `flutter run`, and the tag paired to phone 1
(14, step 6). A second phone for rows A8–A10.

| # | Check | Do | Expect |
| --- | --- | --- | --- |
| A1 | **Discovery** | open the app | the badge goes from **Searching…** to **SportCam · Direct · <address>** within a few seconds |
| A2 | **Live view** | look at the screen | the camera's picture, smooth (15 fps). A box round you when you stand in front of it |
| A3 | **Aim by hand** | camera awake: drag the joystick left, then up, then let go | it pans left, tilts up, and stops when you let go |
| A4 | **Pairing needs one tag on** | tag off: account menu → **Pair my tag** | *"switch on your tag, and only yours"*; nothing changes. Tag on again, pair again: *"Tag T0 is yours"* |
| A5 | **The tag starts a session** | tag off for 5 s. Stand 3–5 m out in front of the camera, facing it, and switch the tag on | within about a second the camera turns to you and the app pings; once it has seen you, beeps 3, 2, 1, a chime: recording |
| A6 | **The tag ends it** | switch the tag off | 5 s later a falling chime; back to awake, the clip saved |
| A7 | **The library** | the recordings button | the clip, *"on the camera, uploading soon"*; it plays, with the boxes drawn on it. No backend, so it stays on the card |
| A8 | **Someone else's recording** | start one with the tag (A5); on phone 2, watch | phone 2 shows *"Someone else is recording — only their phone can stop it"*, and its **Stop** and **Sleep** do nothing. Phone 1's **Stop recording** stops it. Then tag off |
| A9 | **Someone else's clip** | phone 2's recordings button | phone 1's clip isn't there |
| A10 | **Pairing moves the tag** | phone 2 pairs the tag; then tag off 5 s, on again | the recording is phone 2's now: phone 1 gets the *"Someone else is recording"* message. Tag off, and pair it back to phone 1 |
| A11 | **Sleep** | tag off; close the live view (background the app) for 30 s | the camera sleeps: the app says so; **Wake up** brings the picture back |

## B. With the backend

Emulators running, the camera connected to them, and the app built with the
three `--dart-define`s (14, step 5). Phone 1 signs in as
`climber@sportcam.dev`, phone 2 as `admin@sportcam.dev`, password
`sportcam-dev`.

| # | Check | Do | Expect |
| --- | --- | --- | --- |
| B1 | **Sign-in** | open the app | the sign-in page, not the camera. A wrong password says *"Wrong email or password"*. Signed in, the camera |
| B2 | **No sign-up** | look for one | there isn't one: *"No account? Ask an admin to add you."* |
| B3 | **Add a person** | phone 2 (admin): account menu → **People** → **Add person**, any email, an 8-character password | they appear in the list; that email and password sign in on phone 1 (sign out first). Back to the climber after |
| B4 | **Not an admin** | phone 1 (climber): account menu | no **People** |
| B5 | **Record, upload, library** | phone 1 signed in, the tag paired to it again (account menu → **Pair my tag**: the pairing goes with the signed-in person). Tag on, record 10 s, tag off | *"Uploading… n %"*, then *"Recording saved — watch now"*; the clip plays from the library |
| B6 | **Only yours** | phone 2's library | the admin's sample clip, and not the climber's. Phone 1's has the climber's, not the sample |
| B7 | **Owner-only stop** | the tag starts a recording (phone 1's); phone 2 tries to stop it | as A8: only phone 1 can |
| B8 | **Through Firebase** | tag off; wake the camera (**Wake up**, then close the app so nothing else drives it); within 30 s, on the computer: `cd src/app_flutter && dart run tool/verify_against_device.dart http://127.0.0.1:5001/demo-sportcam/us-central1/api bench-camera-key` | `all contract checks passed`: the real camera driven through the backend — sign-in, a session stopped only with its secret, the clip uploaded into the climber's library, the preview |
| B9 | **Sign out** | account menu → **Sign out** | back to the sign-in page; signing in as the other person shows their library, not this one's |

All of B passing is the end-to-end test: the phone app, the camera and the
backend agree. What's left for the full build is the hardware the bench left
out — battery, latch, gauge, ring, Pi-driven servos, the third anchor — and
calibration: the [UWB build's verification checklist](../setup/15-verification.md).
