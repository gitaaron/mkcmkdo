# SportCam — subject-tracking robotic camera tripod

A camera on a robotic tripod head that pans **360° continuously**, tilts through
**270°** (> 180° vertical coverage), zooms optically, and automatically follows a
person wearing a UWB tracking tag. An LED ring on the base and a companion web
app both show the three system states (idle / tracking / recording).

![System architecture](docs/images/system-architecture.png)

## Documentation

| Doc | Contents |
| --- | --- |
| [01 — System overview](docs/01-system-overview.md) | Goals, concept of operations, state machine |
| [02 — Mechanical design](docs/02-hardware-mechanical.md) | Pan/tilt mechanism, slip ring, mounts, 3D-printed parts |
| [03 — Electronics](docs/03-electronics.md) | Schematics, wiring, power budget |
| [04 — Tracking system](docs/04-tracking-system.md) | UWB geometry, control loops, CV assist |
| [05 — Device software](docs/05-device-software.md) | Pi head service, base firmware, wearable firmware, video streaming |
| [06 — Server & app](docs/06-server-and-app.md) | Protocol, function-style API, Vue app, Firebase migration path |
| [07 — Bill of materials](docs/07-bill-of-materials.md) | Every part, price, and where to buy it |

## Repository layout

```
docs/               design docs + rendered PNG diagrams
schematics/         diagram/schematic sources
  render_diagrams.py      matplotlib → docs/images/*.png
  render_schematics.py    schemdraw   → docs/images/schematic-*.png
  interactive/index.html  d3-hwschematic interactive wiring viewer
  tscircuit/              tscircuit source for the base carrier PCB
server/             Node.js + TypeScript API (function-style, Firebase-ready)
web/                Vue 3 companion app (Vite)
device/             Raspberry Pi head-unit service (Python)
firmware/           ESP32 base-controller firmware (Arduino)
wearable/           ESP32-UWB tag firmware (Arduino)
```

## Quick start (server + app)

```bash
npm install
npm run dev        # starts API on :8787 and web app on :5173, both with watch
```

Open http://localhost:5173. With no hardware attached the server runs a built-in
**device simulator** (`SIM=1`, on by default in dev) so the full app — stream
placeholder, state machine, buttons, status ring — works end to end.

## Regenerating the diagrams

```bash
pip install schemdraw matplotlib pillow
python3 schematics/render_diagrams.py
python3 schematics/render_schematics.py
```

## Hardware quick facts

- **Pan**: NEMA17 + TMC2209, GT2 belt 3:1, continuous 360° (power via slip ring, data via Wi-Fi)
- **Tilt**: DS3225 270° servo → −45°…+225°
- **Zoom**: Arducam IMX219 8 MP with I2C-controlled motorized zoom lens
- **Tracking**: two-anchor UWB (DW1000) ranging → bearing + distance; optional CV refinement
- **Brains**: Raspberry Pi 5 on the rotating head, ESP32 in the static base
- **Budget**: ≈ $485 full build (own tripod), ≈ $360 budget variant — see the [BOM](docs/07-bill-of-materials.md)
