# 02 — System architecture

Allocation of the requirements in [01 — Product requirements](../product/01-requirements.md)
to hardware and software. Shared architecture first, then <!--both-->each build's additions<!--/--><!--with_uwb: the build's additions--><!--without_uwb: the build's additions-->:

- **[With UWB](#with-uwb)**: wearable tag, three anchors on the head.
- **[Without UWB](#without-uwb)**: camera is the only sensor.

Subsystem docs:
[03 — Mechanical design](03-mechanical-design.md),
[04 — Electronics](04-electronics.md),
05 — Tracking system ([with UWB](../../with_uwb/docs/design/05-tracking-system.md) ·
[without UWB](../../without_uwb/docs/design/05-tracking-system.md)),
[06 — Device software](06-device-software.md),
[07 — Backend & app](07-backend-and-app.md),
[08 — Recordings & cloud](08-recordings-and-cloud.md),
[09 — Direct connection & native app](09-direct-connection-and-app.md).

## Subsystems

| Subsystem | Compute | Role |
| --- | --- | --- |
| **Camera unit** | Raspberry Pi 4 | camera and zoom lens, pan/tilt servos, LED ring, battery gauge, video encode and stream, person detection, tracking control loop<!--with_uwb-->; with UWB, three anchors<!--/--> |
| **Backend** | Firebase: one Cloud Function (TypeScript), Firestore, Cloud Storage, Hosting | API, per-camera live state and preview, recording library, web app hosting. Shared by both builds |
| **Companion app** | Vue 3 web app (Firebase Hosting); Flutter app | live view and control, remotely or direct on the camera's Wi-Fi. Shared by both builds |

<!--with_uwb-->

The UWB build adds a fourth subsystem, the **wearable tag**.

<!--/-->

## Key decisions

| Decision | Rationale | Cost |
| --- | --- | --- |
| **Control loop closes on one board.** Pan, tilt, zoom and focus are register writes to the Arducam PTZ controller on the Pi's I2C bus | no network hop or second microcontroller in the loop | pan limited to ±80°, no continuous rotation ([03](03-mechanical-design.md#ranges-of-motion)) |
| **Backend and network are optional.** Without Wi-Fi the camera tracks, records and shows state; a phone on the same Wi-Fi controls it directly ([09](09-direct-connection-and-app.md)) | gym Wi-Fi is unreliable (C7) | the camera hosts its own copy of the API |
| **Firebase only** ([07](07-backend-and-app.md)). The camera writes its own Firestore document and listens on it for app requests | no server to run or hold connections (C8) | remote live view is a ≈ 1 frame/s preview; Cloud Functions can't stream |

---

## With UWB

![System architecture, with UWB](../../with_uwb/docs/images/system-architecture.png)

| Subsystem | Compute | Role |
| --- | --- | --- |
| **Wearable tag** | ULA1 (ESP32 + DWM1000) | ranges all three anchors and broadcasts the results; worn by the subject; powered by a small USB bank |

Anchors on the camera unit: A1 and A2 on arms, A3 on a mast (elevation).

---

## Without UWB

![System architecture, without UWB](../../without_uwb/docs/images/system-architecture.png)

No wearable and no radio; the camera is the only sensor. The Pi's USB ports
are unused.
