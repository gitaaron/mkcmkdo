# 01 — Product requirements

Functional requirements (F), non-functional requirements (C), the ideal
path and the state machine. Design: [02 — System architecture](../design/02-system-architecture.md)
onward.

Structure: shared requirements first, then build-specific requirements in
[With UWB](#with-uwb) and [Without UWB](#without-uwb).

## Use case

Reference scenario: an indoor climbing session with no camera operator.

| Parameter | Value |
| --- | --- |
| Mounting | standard photo tripod on the floor or mats |
| Distance to subject | 6–12 m |
| Power | battery only, no mains |
| Camera behaviour | pans and tilts to keep the climber centred; zooms to hold framing |
| Status | LED ring on the head; same state and a live view in the app |

Subject localisation is build-specific: [With UWB](#with-uwb),
[Without UWB](#without-uwb).

## The two builds

<!--compare-->

| | [**With UWB**](../../README.md#with-uwb) | [**Without UWB**](../../README.md#without-uwb) |
| --- | --- | --- |
| Subject localisation | worn UWB tag, ranged by 3 anchors at 20 Hz | vision only: pan sweep, lock on the first person detected |
| Session start | tag switched on | **Track & record** in the app |
| Distinguishes subject from bystanders | yes (tag identity) | no (first person found) |
| Extra hardware | 3 × ULA1 anchors, 2 anchor arms, A3 mast, wearable pod | none |
| Head size | ≈ 30 cm across the arms, 28 cm to the mast top; Ø 141 mm enclosure | Ø 135 mm enclosure, no protrusions |
| Runtime, 92 Wh bank, tracking + recording | ≈ 6.2 h | ≈ 8.4 h (estimated) |
| Cost, excluding tripod | ≈ C$1079 | ≈ C$716 |
| `TRACKING_MODE` | `"with_uwb"` | `"without_uwb"` |

Selection: UWB when the subject must be distinguished from other people in
view; camera-only for lower cost, size and power.

## Functional requirements

| ID | Requirement | Reference |
| --- | --- | --- |
| F1 | **Pan, tilt, zoom.** Pan 160° (±80°); tilt 130° (−45° to +85°); optical zoom 96° → 33° horizontal (≈ 3.5×). All three from the Arducam PTZ base | [03](../design/03-mechanical-design.md) |
| F2 | **Follow a person** <!--both-->by UWB tag or by vision, per build<!--/--><!--with_uwb: by the UWB tag they wear--><!--without_uwb: by vision alone-->, and zoom to keep them framed | <!--both-->05 tracking ([with UWB](../../with_uwb/docs/design/05-tracking-system.md), [without UWB](../../without_uwb/docs/design/05-tracking-system.md))<!--/--><!--with_uwb:[05](../../with_uwb/docs/design/05-tracking-system.md)--><!--without_uwb:[05](../../without_uwb/docs/design/05-tracking-system.md)--> |
| F3 | **Record unattended.** Recording starts on lock-on and stops at session end. A clip is saved even when the battery runs out | [Ideal path](#ideal-path) |
| F4 | **LED status ring** showing idle, acquiring, tracking, recording and low battery | [State machine](#state-machine) |
| F5 | **Companion app**: opens into the live view; state-dependent bottom buttons; status ring top right in the LED colours | [07](../design/07-backend-and-app.md#web-app-srcweb) |
| F6 | **Remote use.** State, live preview and control from any internet-connected phone or computer. One backend and one app serve both builds; the camera reports its build | [07](../design/07-backend-and-app.md#tracking-mode) |
| F7 | **Recordings library.** Each stopped recording uploads to the backend and appears in the app's library | [08](../design/08-recordings-and-cloud.md) |
| F8 | **Direct connection.** On the camera's Wi-Fi, a phone discovers and controls it with no server or internet | [09](../design/09-direct-connection-and-app.md) |

## Non-functional requirements

Constraints the design must meet. A change that breaks one must state why
in the doc that makes it. C1 and C2 are build-specific
(<!--both-->[with UWB](#non-functional-requirements-with-uwb),
[without UWB](#non-functional-requirements-without-uwb)<!--/--><!--with_uwb: [with UWB](#non-functional-requirements-with-uwb)--><!--without_uwb: [without UWB](#non-functional-requirements-without-uwb)-->).

| # | Requirement | Value | Rationale | Set in |
| --- | --- | --- | --- | --- |
| C3 | **Standard tripod mount** | 3/8-16 brass insert in the floor; removable 3/8-16 → 1/4-20 reducer bushing | photo tripods use 1/4-20, video heads 3/8-16; one socket takes both without an adapter plate | `tripod_boss_d`, `tripod_hole_d` in `<build>/cad/config.scad`; BOM |
| C4 | **Battery operation** | ≥ 4 h tracking + recording from a USB-C PD bank; remaining-time gauge; clean save and stop at 7 % | no wall socket; no lost clip at end of charge | [04 — Runtime](../design/04-electronics.md#runtime) |
| C5 | **Printable on a Bambu Lab A1 Mini** | every part ≤ 170 mm on every axis, as oriented for printing | the printer in use | [11](../setup/11-3d-printing.md#design-rule-every-part-prints-on-a-bambu-lab-a1-mini); `cad/fit.py` |
| C6 | **Bought parts fit the printed parts** | every part in `cad/ordered_parts.toml` fits with clearance | parts are bought before they can be measured | `cad/fit.py`, on render, commit and Claude Code stop ([Appendix A](../appendix/appendix-a-cad-parts.md#fit-the-layout-to-your-parts)) |
| C7 | **Operates offline** | tracks, records and shows state with no server and no Wi-Fi | gym Wi-Fi is unreliable | [02](../design/02-system-architecture.md#key-decisions) |
| C8 | **No home server** | deployed backend is Firebase only (Functions, Firestore, Storage, Hosting) | no machine to keep running; reachable from anywhere | [07](../design/07-backend-and-app.md) |
| C9 | **Testable without cloud or camera** | backend runs on the Firebase emulators with a simulated camera (`npm run dev`); API tests run against them (`npm test`) | test before deploying, without hardware | [Appendix C](../appendix/appendix-c-development.md) |
| C10 | **Owner-only access** | every call and read requires the camera key; cameras can't be listed; no client writes | backend is public | [07 — The camera key](../design/07-backend-and-app.md#the-camera-key) |

## Ideal path

One successful session, end to end: subject found, filmed, clip in the
library. Deviations (dropouts, loss, manual control): <!--both-->[with UWB](#state-machine-with-uwb),
[without UWB](#state-machine-without-uwb)<!--/--><!--with_uwb: [state machine, with UWB](#state-machine-with-uwb)--><!--without_uwb: [state machine, without UWB](#state-machine-without-uwb)-->.

1. **Power on.** Pi boots, joins Wi-Fi, connects to Firebase. State `idle`
   (solid blue): head parked, lens wide. The app opens into the live view;
   the status ring reads "On — no one in frame", then "On — person in frame"
   once the climber walks into view.
2. **Start.** State `tracking`, phase `acquiring` (green light chasing round
   the ring).
   The climber is already in frame, so tracking starts in **centre** and
   skips **search**.
   - **With UWB**: the climber switches the tag on. The camera ranges
     continuously, including in idle, and detects the tag within ≈ 1 s; the
     head turns to the ranged position. App: "Acquiring subject…". (With
     nobody in frame, search is that same turn: the location is known at
     once, so there is no sweep.)
   - **Without UWB**: the user taps **Track & record** (app or the camera's
     local page). App: "Looking for a person…". The head turns straight to
     the climber. (With nobody in frame, search first sweeps ±80° at 25°/s,
     zoomed wide, stepping between two tilt rows at each end, until a
     person is detected.)
3. **Lock on.** Two consecutive detections with the person near frame
   centre; the app beeps once for each. Solid green.
   - **With UWB**: both with the head on the ranged position. Ranging alone
     never starts a recording.
   - **Without UWB**: the first person found is kept; afterwards the tracker
     follows the detection nearest the last position, so a passing
     bystander doesn't take the lock.
4. **Record.** State `recording` (pulsing red; the app chimes after the
   beeps), automatically on the first lock. Pan and tilt keep the climber centred; zoom holds them at
   ≈ 65 % of the frame. H.264 is written on the Pi.
5. **End.** The clip is saved, the app chimes, state `idle`.
   - **With UWB**: the climber switches the tag off; the session ends 5 s
     later.
   - **Without UWB**: the user taps **Stop tracking** (confirmed in the app).
6. **Upload.** The clip uploads to Firebase and appears in the app's library
   ([08](../design/08-recordings-and-cloud.md)).
7. **Turn off.** Both axes centre and the Pi shuts down. **Turn off** works
   from any state and saves any recording first; the same sequence runs
   automatically at 7 % battery.

## State machine

States, colours and transitions are shared; button labels and the acquiring
label differ by build. `idle` and `tracking` each have two sub-states,
reported to the app as telemetry `phase`.

| State | LED | App status ring | App sound | Bottom buttons |
| --- | --- | --- | --- | --- |
| `off` | off | grey | — | *(app shows reconnect screen)* |
| `idle`, no person in frame | solid blue | blue, "On — no one in frame" | — | **Turn off** · <!--with_uwb-->**Start tracking**<!--/--><!--both--> / <!--/--><!--without_uwb-->**Track & record**<!--/--> |
| `idle`, person in frame | solid blue | blue, "On — person in frame" | — | **Turn off** · <!--with_uwb-->**Start tracking**<!--/--><!--both--> / <!--/--><!--without_uwb-->**Track & record**<!--/--> |
| `tracking`, acquiring | green, chasing round the ring | green (fast blink), <!--with_uwb-->"Acquiring subject…"<!--/--><!--both--> / <!--/--><!--without_uwb-->"Looking for a person…"<!--/--> | Search: sonar ping every 3 s. Centre: a beep per centred detection | **Turn off** · <!--with_uwb-->**Start recording**<!--/--><!--both--> / <!--/--><!--without_uwb-->**Record now**<!--/--> |
| `tracking`, locked on | solid green | green | — | **Turn off** · <!--with_uwb-->**Start recording**<!--/--><!--both--> / <!--/--><!--without_uwb-->**Record now**<!--/--> |
| `recording` | pulsing red | red (pulsing) | rising chime on start, falling chime on stop<!--both-->; without UWB, pings again if it loses the person and searches<!--/--><!--without_uwb: ; pings again if it loses the person and searches--> | **Stop recording** · **Stop tracking** |

<!--both-->

Where two labels are given: with UWB / without UWB.

<!--/-->

Rules:

- `idle` sub-state: the head is parked (centred, lens wide) and the person
  detector runs at 0.5 fps (`DETECT_FPS_IDLE`). **Person in frame** from a
  detection until 4 s (`IDLE_PERSON_HOLD_S`) pass without one; otherwise
  **no person in frame**. Telemetry `phase`: `person-in-frame` /
  `no-person-in-frame`.
- `tracking` acquires in three steps, the same in both builds:
  1. **Search** — get the subject into frame. With UWB the location is
     known at once, so the head turns to the ranged position; without UWB
     it sweeps the room. The app plays a sonar ping every 3 s while
     searching.
  2. **Centre** — pan and tilt to put the person at frame centre. Two
     consecutive centred detections (`ACQUIRE_DETECTIONS`) lock on; the app
     beeps once per centred detection.
  3. **Track** — locked on (phase `acquired`).

  From **person in frame**, tracking starts at centre and skips search. If
  nobody is seen there for 2 s (`CENTRE_TIMEOUT_S`), it falls back to
  search.
- `recording` implies `tracking`. **Stop recording** → `tracking`. **Stop
  tracking** while recording stops both (confirmed in the app).
- Subject missing > 2 s in `tracking`: hold position, LED flashes at 2 Hz.
  Next step is build-specific.
- Battery < 20 %: ring dims and blinks orange at 1 Hz over the state colour.
  Battery < 7 %: save, park, drop to `idle`.
- The camera is the single source of truth. App commands are requests; the
  camera applies them and reports the result. The camera may also change
  state on its own and reports that the same way.

---

## With UWB

![SportCam tracking a climber with a UWB tag](../../with_uwb/docs/images/intro-scene.png)

The climber wears a UWB tag on the rear of the harness, off-spine
([wearing the tag](../../with_uwb/docs/design/05-tracking-system.md#wearing-the-tag)).
The camera, 6–12 m back
([placement envelope](../../with_uwb/docs/design/05-tracking-system.md#camera-placement-envelope)),
ranges the tag at 20 Hz through body and clothing and points at the result.

### Non-functional requirements, with UWB

| # | Requirement | Value | Rationale | Set in |
| --- | --- | --- | --- | --- |
| C1 | **Compact head** | ≤ 30 cm across, ≤ 30 cm tall to the top of the A3 mast (enclosure floor up), excluding the tripod | must fit small rooms | `uwb_half_base`, `uwb_v_base` in `with_uwb/cad/config.scad` |
| C2 | **Anchor spacing** | A1–A2 **250 mm** horizontal; A3 **250 mm** above them, ≈ 89 mm behind the pan axis | angle noise ∝ 1/spacing: 250 mm gives ≈ 9° RMS filtered (≈ 7° at 400 mm); the vision trim absorbs the difference ([05](../../with_uwb/docs/design/05-tracking-system.md#geometry)). Below 250 mm, error and A3's blind corner grow quickly | `with_uwb/cad/config.scad`; `UWB_BASELINE_M`, `UWB_A3_UP_M`, `UWB_A3_BACK_M` in `src/with_uwb/device/sportcam/config.py` |

### State machine, with UWB

![State machine, with UWB](../../with_uwb/docs/images/state-machine.png)

Deviations from the [ideal path](#ideal-path):

- Tag lost > 2 s in `tracking`: hold, LED flashes. Lost > 5 s: `idle`
  (any recording saved first). A subject crossing a pan soft limit behaves
  the same way.
- The 5 s delay rides over short dropouts. A switched-off tag and a
  body-shadowed tag are indistinguishable, so a dropout > 5 s also ends the
  session; the tag returning starts a new one (two clips). Raise
  `LOST_IDLE_S` if this happens.
- Tracking but not verified by vision after 15 s: the app reports it;
  **Start recording** overrides.
- Manual control (**Start tracking**, **Start recording**) is always
  available. A session stopped from the app stays stopped until the tag has
  been off for 5 s and comes back on.
- `AUTO_SESSION = False` disables tag-driven sessions.

Implementation: [`src/with_uwb/device/sportcam/session.py`](../../src/with_uwb/device/sportcam/session.py).

![App UI, with UWB](../../with_uwb/docs/images/app-ui.png)

---

## Without UWB

![SportCam finding and tracking a climber by vision](../../without_uwb/docs/images/intro-scene.png)

Nothing is worn. **Track & record** in the app starts a wide-angle pan
sweep; the first person detected is centred, locked and recorded. If idle
already has a person in frame, the sweep is skipped and that person is
centred directly.

### Non-functional requirements, without UWB

| # | Requirement | Value | Rationale | Set in |
| --- | --- | --- | --- | --- |
| C1 | **Compact head** | Ø 135 mm enclosure (assumed part sizes), camera on top, no side protrusions, excluding the tripod | must fit small rooms | `base_d_min` in `without_uwb/cad/config.scad`; `cad/fit.py` widens it only if parts require |
| C2 | **Pan range ±80°** | soft limits `PAN_MIN_DEG` / `PAN_MAX_DEG` = ∓80°; no continuous rotation | the base fouls before 180° and can't turn 360°; the search covers this range only | `src/without_uwb/device/sportcam/config.py` |

### State machine, without UWB

![State machine, without UWB](../../without_uwb/docs/images/state-machine.png)

Deviations from the [ideal path](#ideal-path):

- Nobody found in 15 s: the app reports it.
- Person missing 2 s in `tracking`: hold, LED flashes at 2 Hz. Missing 6 s:
  sweep again, toward the last direction of travel; recording continues.
- Tracking-only session with nobody ever found for 180 s: `idle`. This is
  the only automatic return to `idle`; a recording is never stopped
  automatically.
- Manual control: **Record now** while tracking; **Stop recording**
  (tracking continues; no second auto-recording in the same session);
  **Stop tracking** returns to idle.
- `AUTO_RECORD_ON_LOCK = False` makes recording a separate action.

Implementation: [`src/without_uwb/device/sportcam/session.py`](../../src/without_uwb/device/sportcam/session.py).

![App UI, without UWB](../../without_uwb/docs/images/app-ui.png)
