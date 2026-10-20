# Appendix D — Glossary

The terms the docs use without stopping to explain, in alphabetical order.<!--with_uwb-->
Terms that only the UWB build uses are in [their own section](#with-uwb).<!--/-->

## Both builds

| Term | Meaning |
| --- | --- |
| **Acquiring** | the first phase of tracking: the camera is turning to the subject (or searching for one) and hasn't locked on yet. The ring shows a green light chasing round |
| **Buck converter** | the board that steps the bank's 12 V down to the single 5 V supply everything runs on |
| **Camera key** | a long random string that names one camera in Firebase and works as its password. It's in the camera's `config.py` and in your app link ([07](../design/07-backend-and-app.md#the-camera-key)) |
| **CSI** | the Raspberry Pi's camera connector, where the camera's ribbon cable plugs in |
| **Emulators** | Firebase's local copies of its services, so the backend runs on your computer for testing (`npm run dev`) |
| **Firestore** | Firebase's database. Each camera keeps one document there with its state, telemetry and heartbeat |
| **Focal length (EFL)** | how far the zoom lens is zoomed in, in mm: about 2.8 mm at the wide end, 10.6 mm at full zoom |
| **FOV** | field of view: how wide an angle the camera sees, 96° across at the wide end |
| **Gauge** | the INA260 current sensor between the bank and the buck, which works out how much battery is left |
| **HOG** | OpenCV's person detector ("histogram of oriented gradients"). It runs about 3 times a second on the Pi |
| **I2C** | the two-wire bus the Pi uses to talk to the PTZ controller and the gauge |
| **Kalman filter** | a smoothing filter that averages noisy measurements while still following real movement |
| **Level shifter** | the 74AHCT125 chip that lifts the Pi's 3.3 V data signal to the 5 V the LED ring needs |
| **Locked on** | tracking has settled on the subject. The ring turns solid green, and a session that started automatically begins recording |
| **mDNS / Bonjour** | how a phone finds the camera on the local Wi-Fi by name (`sportcam.local`) without knowing its IP address |
| **MJPEG** | video sent as a stream of JPEG pictures; the camera's direct live view to phones on its Wi-Fi |
| **PD (USB Power Delivery)** | the part of USB-C that lets a bank supply more than 5 V. The **PD trigger** board asks the bank for 12 V |
| **PETG** | the filament every structural part is printed in |
| **PTZ** | pan, tilt and zoom. The **PTZ base** is the bought Arducam camera assembly; the **PTZ controller** is its board that drives the servos and lens motors |
| **Slew limit** | a cap on how fast the camera may turn, so it glides between measurements instead of snapping |
| **Soft limits** | the pan and tilt angles the software won't go past, set short of where the bracket hits anything |
| **SPI** | the Pi's serial bus used to send colour data to the LED ring |
| **State** | what the camera is doing: `off`, `idle`, `tracking` or `recording` ([01](../product/01-requirements.md#state-machine)) |
| **`TRACKING_MODE`** | the setting in the camera's `config.py` that names its build, `with_uwb` or `without_uwb`. The apps word their buttons from it |
| **WebRTC / WHEP** | an optional low-latency video path from the camera to a phone on its Wi-Fi, through MediaMTX on the Pi |
| **WS2812B** | the individually addressable LEDs in the status ring |

---

## With UWB

| Term | Meaning |
| --- | --- |
| **A1, A2, A3** | the three anchors: A1 and A2 on the arms either side, A3 on the mast above and behind the lens. The vendor's names for them are A0–A2 |
| **Anchor** | a UWB radio fixed to the camera head. The tag measures its distance to each one |
| **Baseline** | the distance between two anchors: 250 mm side to side, and 250 mm up to A3. A longer baseline gives steadier angles |
| **Bearing (θ)** | the subject's angle left or right of straight ahead, worked out from the A1 and A2 distances |
| **Boresight** | the line straight out of the lens with pan and tilt centred; calibration tapes the tag on it |
| **DS-TWR** | double-sided two-way ranging: how two UWB radios measure the distance between them by timing messages back and forth |
| **DW1000 / DWM1000** | the UWB radio chip, and the module built around it, inside each ULA1 |
| **Elevation (φ)** | the subject's angle above or below level, worked out using A3 |
| **Range** | one measured distance from the tag to an anchor (r₁, r₂, r₃) |
| **Range bias** | how far an anchor's ranges read long or short; measured once with `rangecal` and subtracted |
| **RTLS firmware** | the vendor's `RTLS_Anchor` / `RTLS_Tag` sketches, which range to every anchor and send all the distances in one frame. The other pair, `RangingAnchor` / `RangingTag`, doesn't work with SportCam |
| **Tag** | the UWB radio the subject wears, plugged into a small USB bank. Switching it on starts a session |
| **ULA1** | Haorutech's UWB module (an ESP32 plus a DWM1000), used for the three anchors and the tag |
| **UWB** | ultra-wideband radio. It measures distance to about 10 cm, through clothing and bodies |
