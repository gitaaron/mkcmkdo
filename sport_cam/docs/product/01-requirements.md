# 01 — Product requirements

What SportCam has to do (functional requirements), the limits it has to stay
inside (non-functional requirements), and how a session plays out. How the
design meets them is in [02 — System architecture](../design/02-system-architecture.md)
and the design docs after it.

SportCam comes in two builds that share everything except how the camera
finds the subject. This doc covers what they share first, then each build in
its own section:

- **[With UWB](#with-uwb)** — the subject wears a tag; anchors on the head
  range it and the camera points where the ranges say.
- **[Without UWB](#without-uwb)** — nothing worn; the camera sweeps the room by
  vision and locks on to the first person it sees.

## Introduction

One scene describes the project: an indoor climbing session, filmed
by nobody. SportCam sits on an ordinary photo tripod on the mats 6–12 m back,
running off a power bank with nothing plugged in. It pans and tilts to keep
the climber centred, and the motorized lens zooms to hold framing as they move
up the wall. The LED ring on the base glows green (tracking) or pulses red
(recording), and the same status shows in the companion app streaming the
live view to a phone. The session films itself.

How the camera knows where the climber is depends on the build —
see <!--both-->[With UWB](#with-uwb) and [Without UWB](#without-uwb) below, each with its own
picture of the scene.<!--/--><!--with_uwb: [With UWB](#with-uwb) below, with its picture of the scene.--><!--without_uwb: [Without UWB](#without-uwb) below, with its picture of the scene.-->

## The two builds

<!--compare-->

| | [**With UWB**](../../README.md#with-uwb) | [**Without UWB**](../../README.md#without-uwb) |
| --- | --- | --- |
| How it finds the subject | the subject wears a UWB tag; three anchors on the head range it 20×/s | vision only: the camera sweeps the room and locks on to the first person it sees |
| Starting a session | switch the tag on | tap **Track & record** in the app |
| Tells your subject from a bystander | yes — the tag does | no — it follows whoever it found first |
| Extra hardware | 3 × ULA1 anchors, 2 anchor arms, an A3 mast, a wearable pod | none |
| Head size | ≈ 30 cm across the arms, 28 cm tall to the mast; Ø 141 mm enclosure | Ø 135 mm enclosure, nothing sticking out |
| Runtime (92 Wh bank) | ≈ 6.2 h tracking + recording | ≈ 8.4 h (estimated) |
| Budget (own tripod) | ≈ C$1079 | ≈ C$716 |
| Camera setting | `TRACKING_MODE = "with_uwb"` | `TRACKING_MODE = "without_uwb"` |

Pick the UWB build to film one person in a room with other people in it: the
tag is how the camera tells your subject from a bystander. Pick the
camera-only build for simplicity, size and cost.

## Functional requirements

1. **F1 — Pan, tilt and zoom.** Camera on a motorized tripod head:
   **160° of pan** (±80°), **130° of tilt** (−45° to +85°), motorized
   **optical zoom** (96° → 33°, ≈ 3.5×). Both axes and the lens come from the
   Arducam PTZ base, which is what keeps the build to a weekend — see
   [03](../design/03-mechanical-design.md) for what that trades away.
2. **F2 — Follows a person.** The camera **follows a human subject** — by <!--both-->UWB
   tag or by vision alone, depending on the build<!--/--><!--with_uwb: the UWB tag they wear--><!--without_uwb: vision alone--> — and zooms to keep them
   framed.
3. **F3 — Records a session on its own.** Recording starts once the camera
   has locked on to the subject and stops at the end of the session, with a
   saved clip even if the battery runs out ([concept of operations](#concept-of-operations)).
4. **F4 — LED status ring** on the unit showing the states: on-but-not-tracking,
   acquiring (<!--with_uwb-->turning to the tag<!--/--><!--both-->, or <!--/--><!--without_uwb-->searching<!--/-->), tracking, recording, and low
   battery ([state machine](#state-machine)).
5. **F5 — Companion app**: opens straight into the live stream, state-dependent
   bottom buttons, circular status indicator (top-right) matching the LED
   colours ([07 — Web app](../design/07-backend-and-app.md#web-app-srcweb)).
6. **F6 — Use it from anywhere.** The app reaches the camera, shows its
   state and a live preview, and drives it from any phone or computer with
   internet, not only on the camera's Wi-Fi. **One backend and one app serve
   both builds**; the camera says which build it is
   ([07](../design/07-backend-and-app.md#tracking-mode)).
7. **F7 — Recordings library.** A stopped recording uploads to the backend
   and shows up in the app's library
   ([08](../design/08-recordings-and-cloud.md)).
8. **F8 — Direct connection.** On the same Wi-Fi as the camera, a phone
   finds it and connects with no server and no internet
   ([09](../design/09-direct-connection-and-app.md)).

## Non-functional requirements

Hard limits the design has to stay inside. A change that breaks one of these
needs a reason in the doc that makes it. C1 and C2 differ by build and are
in <!--both-->each build's section ([with UWB](#non-functional-requirements-with-uwb),
[without UWB](#non-functional-requirements-without-uwb))<!--/--><!--with_uwb: [the build's section](#non-functional-requirements-with-uwb)--><!--without_uwb: [the build's section](#non-functional-requirements-without-uwb)-->; the rest are shared.

| # | Requirement | Value | Why | Where it is set |
| --- | --- | --- | --- | --- |
| C3 | **Fits any standard tripod**, with interchangeable threads | 3/8-16 brass insert in the floor; a removable 3/8-16 → 1/4-20 reducer bushing for 1/4-20 screws | photo and phone tripods use 1/4-20, video heads and heavier tripods 3/8-16; one socket with a bushing takes both, with no adapter plate | `tripod_boss_d`, `tripod_hole_d` in `<build>/cad/config.scad`; see the build's BOM |
| C4 | **Runs on a battery** for a full session | ≥ 4 h tracking and recording from a USB-C PD power bank, with a gauge that says how long is left; saves and stops cleanly at 7 % | a session must not depend on a wall socket, and must not lose the clip when the pack runs out | [04 — Electronics](../design/04-electronics.md#runtime) |
| C5 | **Every printed part prints on a Bambu Lab A1 Mini** | ≤ 170 mm along every axis, as oriented for printing | it's the printer already bought | [11 — 3D printing](../setup/11-3d-printing.md#design-rule-every-part-prints-on-a-bambu-lab-a1-mini); checked by `cad/fit.py` |
| C6 | **Everything bought fits inside what's printed** | every part in `cad/ordered_parts.toml` fits, with clearance, in the printed parts | parts are bought before they can be measured | `cad/fit.py`, run on every render, commit and CI build ([Appendix A](../appendix/appendix-a-cad-parts.md#fit-the-layout-to-your-parts)) |
| C7 | **Works with no network** | tracks, records and shows its state on the ring with no server and no Wi-Fi | a gym's Wi-Fi can't be relied on | [02 — System architecture](../design/02-system-architecture.md#key-decisions) |
| C8 | **Nothing to run at home** | once deployed, the whole backend is Firebase (Functions, Firestore, Storage, Hosting); no home server or PC stays on | a home server is one more thing to keep running, and can't be reached from the gym | [07 — Backend & app](../design/07-backend-and-app.md) |
| C9 | **Testable without the cloud or the camera** | the whole backend runs on the Firebase emulators with a simulated camera (`npm run dev`); the API's tests run against them (`npm test`) | changes get tried before they're deployed, and without the hardware | [Appendix C](../appendix/appendix-c-development.md) |
| C10 | **Only the camera's owner can see or drive it** | every call and every read needs the camera key; cameras can't be listed; clients can't write | the backend is on the public internet | [07 — The camera key](../design/07-backend-and-app.md#the-camera-key) |

## Concept of operations

The beginning and end of a session are the same in both builds:

1. **Power on** → the Pi boots, joins Wi-Fi, checks in with Firebase.
   State = **IDLE** (LED solid blue). Opening the app immediately shows the
   live stream.
2. **Start, lock on, follow** — this is where the builds
   differ: <!--with_uwb-->[with UWB](#a-session-with-uwb) the tag starts and ends the session<!--/--><!--both-->; <!--/--><!--without_uwb-->[without UWB](#a-session-without-uwb)
   the app starts it and the camera searches<!--/-->. In both, the camera enters **TRACKING** in phase **acquiring**
   (green light chasing round the ring), and once the person detector has
   confirmed a person it records (LED breathing red, the app chimes). While
   recording, vision zooms so the subject fills about 65 % of the frame, with
   margin all round for sudden moves. H.264 video is written on the Pi and
   uploaded afterwards.
3. **Turn off** from any state centres both axes, stops recording safely, and
   powers down cleanly. The same thing happens on its own at 7 % battery, so
   a session that outlasts the pack still ends with a saved clip.

## State machine

The states, colours and transitions are the same in both builds<!--both-->; only the
wording of two buttons and the acquiring label changes<!--/-->.

| State | LED | App status ring | Bottom buttons |
| --- | --- | --- | --- |
| `off` | off | grey | *(app shows reconnect screen)* |
| `idle` | solid blue | blue | **Turn off** · <!--with_uwb-->**Start tracking**<!--/--><!--both--> / <!--/--><!--without_uwb-->**Track & record**<!--/--> |
| `tracking`, acquiring | green, chasing round the ring | green (fast blink), <!--with_uwb-->"Acquiring subject…"<!--/--><!--both--> / <!--/--><!--without_uwb-->"Looking for a person…"<!--/--> | **Turn off** · <!--with_uwb-->**Start recording**<!--/--><!--both--> / <!--/--><!--without_uwb-->**Record now**<!--/--> |
| `tracking`, locked on | solid green | green | **Turn off** · <!--with_uwb-->**Start recording**<!--/--><!--both--> / <!--/--><!--without_uwb-->**Record now**<!--/--> |
| `recording` | pulsing red | red (pulsing) | **Stop recording** · **Stop tracking** |

<!--both-->

Where two labels are given, the first is with UWB and the second without.

<!--/-->

Rules common to both:

- `recording` implies `tracking`. **Stop recording** returns to `tracking`;
  **Stop tracking** while recording stops both (with a confirm in the app).
- Losing the subject for > 2 s in `tracking` holds position and flashes the
  LED (2 Hz). What happens next depends on the build.
- Below 20 % battery the ring dims and blinks orange once a second over
  whatever colour the state is; below 7 % the camera saves and drops to idle.
- The camera is the single source of truth for state; the apps render
  whatever it last reported. An app's command is a request the camera acts
  on and then reports; the camera may also change state itself (and reports
  that the same way).

---

## With UWB

![SportCam tracking a climber with a UWB tag](../../with_uwb/docs/images/intro-scene.png)

The climber wears a matchbox-sized UWB tag on the rear of their harness
(off-spine — see [wearing the tag](../../with_uwb/docs/design/05-tracking-system.md#wearing-the-tag)).
On the mats 6–12 m back — see the
[placement envelope](../../with_uwb/docs/design/05-tracking-system.md#camera-placement-envelope) —
the camera ranges the tag 20 times a second through the climber's body and
clothing, and points where the ranges say. Climb, tap **Start recording**, and
the session films itself.

### Non-functional requirements, with UWB

| # | Requirement | Value | Why | Where it is set |
| --- | --- | --- | --- | --- |
| C1 | **Compact head** for use in a cramped room | ≤ 30 cm across, ≤ 30 cm tall to the top of the A3 mast (enclosure floor up), excluding the tripod | the camera has to stand in small rooms without being in the way | `uwb_half_base`, `uwb_v_base` in `with_uwb/cad/config.scad` |
| C2 | **UWB anchor spacing** | A1–A2 **250 mm** apart (horizontal); A3 **250 mm** above them (vertical), ≈ 89 mm behind the pan axis | the spacing sets angle accuracy (noise ∝ 1/spacing): 250 mm gives ≈ 9° RMS filtered against ≈ 7° at 400 mm, and the vision trim absorbs the difference ([05](../../with_uwb/docs/design/05-tracking-system.md#geometry)). Keep both ≥ 250 mm; below that the error and A3's blind corner grow quickly | `with_uwb/cad/config.scad` and, matching, `UWB_BASELINE_M`, `UWB_A3_UP_M`, `UWB_A3_BACK_M` in `src/with_uwb/device/sportcam/config.py` |

### A session, with UWB

1. **The climber switches the tag on.** That is the start button: the camera
   ranges continuously, even in standby, and notices the tag within about a
   second. State = **TRACKING**, phase **acquiring**. The head turns to where
   the tag says the subject is.
2. **Locked on.** Once the camera has settled on the subject and the person
   detector has seen a person in the middle of the frame, state =
   **RECORDING** and the app chimes. Vision has to verify: ranging alone never
   starts a recording, so a mis-set camera keeps chasing rather than filming a
   wall. If it can't see you after 15 s the app says so; **Start recording**
   in the app always works as an override.
3. **The climber switches the tag off.** 5 s later the camera saves the clip,
   the app chimes, and the camera returns to **IDLE**. The short wait rides
   over brief dropouts; a tag switched off looks exactly like one hidden
   behind a body, so a dropout longer than 5 s ends the session too, and the
   tag coming back starts a new one (two clips rather than one). Raise
   `LOST_IDLE_S` if that happens.

   The app can do all of this by hand instead (**Start tracking**, **Start
   recording**), and anything it does stands: stop a tag-started session from
   the phone and the camera stays stopped until the tag has been off for 5 s
   and comes back on. Set `AUTO_SESSION = False` to make the tag a plain
   ranging beacon again. Details: [`src/with_uwb/device/sportcam/session.py`](../../src/with_uwb/device/sportcam/session.py).

### State machine, with UWB

![State machine, with UWB](../../with_uwb/docs/images/state-machine.png)

- Losing the UWB tag for > 2 s in `tracking` holds position, flashes the LED,
  and falls back to `idle` after 5 s (recording is stopped and saved first if
  active). A subject crossing a pan soft limit looks exactly like this.

![App UI, with UWB](../../with_uwb/docs/images/app-ui.png)

---

## Without UWB

![SportCam finding and tracking a climber by vision](../../without_uwb/docs/images/intro-scene.png)

Nobody wears anything. The climber taps **Track & record** in the app; the
camera zooms wide and sweeps the room until its person detector sees someone,
turns to centre them, locks on and starts recording. Tap, climb, and the
session films itself.

### Non-functional requirements, without UWB

| # | Requirement | Value | Why | Where it is set |
| --- | --- | --- | --- | --- |
| C1 | **Compact head** for use in a cramped room | Ø 135 mm enclosure (with the assumed part sizes) with the camera on top and nothing sticking out sideways, excluding the tripod | the camera has to stand in small rooms without being in the way | `base_d_min` in `without_uwb/cad/config.scad`; `cad/fit.py` widens it only if your parts need it |
| C2 | **Pan range ±80°** | soft limits `PAN_MIN_DEG` / `PAN_MAX_DEG` = ∓80°, no continuous rotation | the metal base fouls before 180°, and it cannot turn 360°; the search sweeps this range and the camera cannot look behind itself | `src/without_uwb/device/sportcam/config.py` |

### A session, without UWB

1. **The climber taps Track & record** in the app (or on the camera's local
   page). State = **TRACKING**, phase **acquiring** ("Looking for a person…"
   in the app). The camera zooms wide and **sweeps** pan ±80° at 25°/s,
   stepping between two tilt rows at each turn-around, until the person
   detector sees someone.
2. **Centre, then lock.** The sweep stops and the head turns to put that
   person in the middle of the frame. After two consecutive centred
   detections it is **locked** (solid green) and, because the session began
   in idle, recording starts straight away: the clip is of the person, not of
   an empty room. The first person found wins; afterwards the camera follows
   the detection nearest the last position, so a bystander walking past does
   not steal the lock. If nobody turns up for 15 s the app says so.
3. **Losing and finding again.** If the person is missing for 2 s the ring
   flashes and the camera holds still; after 6 s it sweeps again, starting
   toward the side they were last heading, while the recording carries on.
   If the camera is tracking (not recording), has never found anyone and 180 s
   pass, it gives up and returns to **IDLE**. A recording is never abandoned
   automatically — stopping it is the user's call.

   The app can drive everything by hand: **Record now** while tracking,
   **Stop recording** (tracking continues, and the camera does not start a
   second recording in the same session), **Stop tracking** to go back to
   idle. Set `AUTO_RECORD_ON_LOCK = False` to make recording a separate tap.
   Details: [`src/without_uwb/device/sportcam/session.py`](../../src/without_uwb/device/sportcam/session.py).

### State machine, without UWB

![State machine, without UWB](../../without_uwb/docs/images/state-machine.png)

- Losing the person for > 2 s in `tracking` holds position and flashes the
  LED (2 Hz); after 6 s the camera sweeps again. Nothing drops to `idle` on
  its own except a tracking-only session that never found anyone in 180 s.

![App UI, without UWB](../../without_uwb/docs/images/app-ui.png)
