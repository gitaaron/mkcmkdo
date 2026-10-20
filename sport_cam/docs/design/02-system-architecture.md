# 02 — System architecture

How the requirements in [01 — Product requirements](../product/01-requirements.md)
are split across hardware and software. The parts both builds share come first,
then each build in its own section:

- **[With UWB](#with-uwb)**: a wearable tag and three anchors on the head.
- **[Without UWB](#without-uwb)**: the camera is the only sensor.

The docs that follow take one subsystem each:
[03 — Mechanical design](03-mechanical-design.md),
[04 — Electronics](04-electronics.md),
05 — Tracking system ([with UWB](../../with_uwb/docs/design/05-tracking-system.md) ·
[without UWB](../../without_uwb/docs/design/05-tracking-system.md)),
[06 — Device software](06-device-software.md),
[07 — Backend & app](07-backend-and-app.md),
[08 — Recordings & cloud](08-recordings-and-cloud.md) and
[09 — Direct connection & native app](09-direct-connection-and-app.md).

## Subsystems

Every build has a camera unit, a cloud backend and a companion app:

| Subsystem | Compute | Role |
| --- | --- | --- |
| **Camera unit** | Raspberry Pi 4 | Camera + zoom lens, pan/tilt servos, LED ring, battery gauge, video encode/stream, person detection, tracking control loop — plus, with UWB, three anchors |
| **Backend** | Firebase: one Cloud Function (TypeScript), Firestore, Cloud Storage, Hosting | The API, each camera's live state and preview, the recording library, serves the web app. Nothing runs at home. One backend for both builds |
| **Companion app** | Vue 3 web app (Firebase Hosting) / Flutter | Live view + control, from anywhere or directly on the camera's Wi-Fi. One app for both builds |

The UWB build adds a fourth subsystem, the **wearable tag**.

## Key decisions

**The whole control loop closes on one board.**
Pan, tilt, zoom and focus are all register writes to the Arducam PTZ
controller on the Pi's I2C bus, so a tracking correction never leaves the
device. The old revision put the pan stepper in a separate static base and
relayed velocity commands Pi → server → ESP32 over the LAN, because the head
rotated continuously and a stepper cannot ride on a slip ring. Giving up
continuous rotation deleted the slip ring, the second microcontroller, its
firmware and that entire network hop.

**The backend and the network are optional** in the strict sense: unplug the
Wi-Fi and the camera still tracks, films, and shows its state on the ring,
and a phone on the camera's own hotspot still drives it directly
([09](09-direct-connection-and-app.md)).

**Nothing runs at home.** The backend is Firebase and only Firebase
([07](07-backend-and-app.md)): the camera keeps its own Firestore document
current and listens on it for the app's requests, so no server has to hold a
connection to it. The price is that live video from outside the camera's
Wi-Fi is a once-a-second preview — a Cloud Function can't stream.

---

## With UWB

![System architecture, with UWB](../../with_uwb/docs/images/system-architecture.png)

The fourth subsystem:

| Subsystem | Compute | Role |
| --- | --- | --- |
| **Wearable tag** | ULA1 (ESP32 + DWM1000) | polls all three anchors and broadcasts the ranges; worn by the subject, powered by a small USB bank |

On the camera unit, the three UWB anchors sit two on arms and one on a mast
for elevation.

---

## Without UWB

![System architecture, without UWB](../../without_uwb/docs/images/system-architecture.png)

There is no wearable and no radio: the camera is the only sensor. Dropping
the UWB radios deleted the only other thing the camera had to talk to, and
the Pi's USB ports are left free.
