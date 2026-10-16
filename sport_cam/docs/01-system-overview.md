# 01 — System overview

## Introduction

One picture of what this project builds — an indoor climbing session, filmed
by nobody:

![SportCam tracking a climber](images/intro-scene.png)

The climber wears a matchbox-sized UWB tag on the rear of their harness
(off-spine — see [wearing the tag](04-tracking-system.md#wearing-the-tag)).
On the mats 6–12 m back — see the
[placement envelope](04-tracking-system.md#camera-placement-envelope) —
SportCam sits on an ordinary photo tripod, running off a power bank with
nothing plugged in: the camera ranges the tag 20 times a second through the
climber's body and clothing, pans and tilts to keep them centred, and the
motorized lens zooms to hold framing as they move up the wall. The LED ring on the base
glows green (tracking) or pulses red (recording), and the same status shows
in the companion app streaming the live view to a phone. Climb, tap
**Start recording**, and the session films itself.

## Goals

1. Camera on a motorized tripod head: **160° of pan** (±80°), **130° of tilt**
   (−45° to +85°), motorized **optical zoom**. Both axes and the lens come
   from the Arducam PTZ base, which is what keeps the build to a weekend —
   see [02](02-hardware-mechanical.md) for what that trades away.
2. Camera **follows a human subject** wearing a small tracking wearable.
3. **Runs on a battery** for a full session: ≥ 4 h tracking and recording from
   a USB-C power bank, with a gauge that says how long is left.
4. **LED status ring** on the unit showing the states: on-but-not-tracking, acquiring,
   tracking, recording.
5. **Companion web app**: opens straight into the live stream, state-dependent
   bottom buttons, circular status indicator (top-right) matching the LED
   colours.
6. Both camera and app talk to a **home server** (Node.js + TypeScript,
   Vue 3 web app) started with a single `npm run dev` that watches `src` and
   reloads.
7. Server code written as **portable typed functions** so the API can later be
   lifted onto Firebase Cloud Functions with minimal change.

## Constraints

Hard limits the design has to stay inside. A change that breaks one of these
needs a reason in the doc that makes it.

| # | Constraint | Value | Why | Where it is set |
| --- | --- | --- | --- | --- |
| C1 | **Compact head** for use in a cramped room | ≤ 30 cm across, ≤ 30 cm tall to the top of the A3 mast (enclosure floor up), excluding the tripod | the camera has to stand in small rooms without being in the way | `uwb_half_base`, `uwb_v_base` in `cad/config.scad` |
| C2 | **UWB anchor spacing** | A1–A2 **250 mm** apart (horizontal); A3 **250 mm** above them (vertical), 86 mm behind the pan axis | the spacing sets angle accuracy (noise ∝ 1/spacing): 250 mm gives ≈ 9° RMS filtered against ≈ 7° at 400 mm, and the vision trim absorbs the difference ([04](04-tracking-system.md#geometry)). Keep both ≥ 250 mm; below that the error and A3's blind corner grow quickly | `cad/config.scad` and, matching, `UWB_BASELINE_M`, `UWB_A3_UP_M`, `UWB_A3_BACK_M` in `device/sportcam/config.py` |
| C3 | **Fits any standard tripod**, with interchangeable threads | 3/8-16 brass insert in the floor; a removable 3/8-16 → 1/4-20 reducer bushing for 1/4-20 screws | photo and phone tripods use 1/4-20, video heads and heavier tripods 3/8-16; one socket with a bushing takes both, with no adapter plate | `tripod_boss_d`, `tripod_hole_d` in `cad/config.scad`; BOM item 23 |

![System architecture](images/system-architecture.png)

## The four subsystems

| Subsystem | Compute | Role |
| --- | --- | --- |
| **Camera unit** | Raspberry Pi 4 | Camera + zoom lens, pan/tilt servos, three UWB anchors (two on arms, one on a mast for elevation), LED ring, battery gauge, video encode/stream, tracking control loop |
| **Wearable tag** | ULA1 (ESP32 + DWM1000) | polls all three anchors and broadcasts the ranges; worn by the subject, powered by a small USB bank |
| **Home server** | Node.js + TS | State authority, command routing, stream relay, serves the app |
| **Companion app** | Vue 3 SPA | Live view + control |

Key architectural decision: **the whole control loop closes on one board.**
Pan, tilt, zoom and focus are all register writes to the Arducam PTZ
controller on the Pi's I2C bus, so a tracking correction never leaves the
device. The old revision put the pan stepper in a separate static base and
relayed velocity commands Pi → server → ESP32 over the LAN, because the head
rotated continuously and a stepper cannot ride on a slip ring. Giving up
continuous rotation deleted the slip ring, the second microcontroller, its
firmware and that entire network hop.

The server and the network are now optional in the strict sense: unplug the
Wi-Fi and the camera still tracks, films, and shows its state on the ring.

## Concept of operations

1. Power on → the Pi boots, joins Wi-Fi, registers with the server.
   State = **IDLE** (LED solid blue). Opening the app immediately shows the
   live stream.
2. **The climber switches the tag on.** That is the start button: the camera
   ranges continuously, even in standby, and notices the tag within about a
   second. State = **TRACKING**, phase **acquiring** (green light chasing
   round the ring). The head turns to where the tag says the subject is.
3. **Locked on.** Once the camera has settled on the subject and the person
   detector has seen a person in the middle of the frame, state =
   **RECORDING** (LED breathing red) and the app chimes. Vision has to verify:
   ranging alone never starts a recording, so a mis-set camera keeps chasing
   rather than filming a wall. If it can't see you after 15 s the app says so;
   **Start recording** in the app always works as an override. While
   recording, vision zooms so you fill about 65 % of the frame, with margin
   all round for sudden moves. Tracking continues; H.264 video is written on
   the Pi and uploaded afterwards.
4. **The climber switches the tag off.** 5 s later the camera saves the clip,
   the app chimes, and the camera returns to **IDLE**. The short wait rides
   over brief dropouts; a tag switched off looks exactly like one hidden
   behind a body, so a dropout longer than 5 s ends the session too, and the
   tag coming back starts a new one (two clips rather than one). Raise
   `LOST_IDLE_S` if that happens.

   The app can do all of this by hand instead (**Start tracking**, **Start
   recording**), and anything it does stands: stop a tag-started session from
   the phone and the camera stays stopped until the tag has been off for 5 s
   and comes back on. Set `AUTO_SESSION = False` to make the tag a plain
   ranging beacon again. Details: [`device/sportcam/session.py`](../device/sportcam/session.py).
5. **Turn off** from any state centres both axes, stops recording safely, and
   powers down cleanly. The same thing happens on its own at 7 % battery, so
   a session that outlasts the pack still ends with a saved clip.

## State machine

![State machine](images/state-machine.png)

| State | LED | App status ring | Bottom buttons |
| --- | --- | --- | --- |
| `off` | off | grey | *(app shows reconnect screen)* |
| `idle` | solid blue | blue | **Turn off** · **Start tracking** |
| `tracking`, acquiring | green, chasing round the ring | green (fast blink), "Acquiring subject…" | **Turn off** · **Start recording** |
| `tracking`, locked on | solid green | green | **Turn off** · **Start recording** |
| `recording` | pulsing red | red (pulsing) | **Stop recording** · **Stop tracking** |

Rules:

- `recording` implies `tracking`. **Stop recording** returns to `tracking`;
  **Stop tracking** while recording stops both (with a confirm in the app).
- Losing the UWB tag for > 2 s in `tracking` holds position, flashes the LED,
  and falls back to `idle` after 5 s (recording is stopped and saved first if
  active). A subject crossing a pan soft limit looks exactly like this.
- Below 20 % battery the ring dims and blinks orange once a second over
  whatever colour the state is; below 7 % the camera saves and drops to idle.
- The server is the single source of truth for state; devices and app render
  whatever the server last broadcast.

## Companion app

![App UI](images/app-ui.png)

Single screen: full-bleed live video, circular status indicator top-right
(same colours as the LED ring), two bottom buttons that change with state.
See [06 — Server & app](06-server-and-app.md).
