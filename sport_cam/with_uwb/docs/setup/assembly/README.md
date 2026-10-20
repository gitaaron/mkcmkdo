# 13 — Assembly guide (interactive 3D)

**Open [`index.html`](index.html)** — straight from disk, or via `npm run docs`
at http://localhost:8090/with_uwb/docs/setup/assembly/index.html (it is also linked from the
docs viewer's sidebar).

| Feature | Detail |
| --- | --- |
| Structure | fourteen steps in five phases (prepare → enclosure → camera → tracking → finish) |
| Per-step view | live 3D render: fitted parts grey; current part blue, animated along its insertion path; green arrows and callouts for direction and wiring; parts, tools and checks lists |
| Catalogue | click a part or tool for a picture and description |
| Navigation | drag to orbit, scroll to zoom, right-drag to pan |
| Viewer bar | *exploded ↔ assembled* slider; views Iso / Front / Side / Top / Under; **X-ray**; **Labels**; **Motion demo** (last steps: sweeps pan and tilt between soft limits) |
| State | progress in `localStorage`; deep links per step (`index.html#lid-ptz`) |
| Keyboard | ← → move, D done, R replay, X x-ray, L labels |

## Files

| File | Role |
| --- | --- |
| `index.html` | the app: step content + three.js viewer (three.js loads from jsDelivr) |
| `guide.css` | styling |
| `models.js` | the printed-part meshes from `cad/stl/`, packed for the browser (generated) |
| `layout.js` | where `cad/fit.py` put every part (generated) |
| `build_models.py` | regenerates `models.js` — run after `./cad/render_all.sh` |
| `render_steps.py` | renders the offline fallback turntables into `renders/` |
| `renders/` | fallback PNGs, used only when three.js can't load (no internet / no WebGL) |
| `../../../../docs/setup/assembly/catalog.js`, `catalog.css` | shared by both builds: the parts-and-tools catalogue. Names in a step's Parts and Tools lists become links that open a picture and a description ("what is an M2.5 × 6?"). Add an entry there when a step names something new |

## Regenerating after a CAD change

```bash
python3 cad/fit.py        # from sport_cam/: solve the layout, render the STLs,
                          # refresh models.js, layout.js and renders/, audit the fit
```

Run after any change to `cad/ordered_parts.toml` or `<build>/cad/`. Also
re-runs `build_models.py` (cad/stl → `models.js`) and `render_steps.py`
(fallback PNGs) when `numpy-stl` and `matplotlib` are installed.

Geometry sources:

- Printed parts: the real STL meshes.
- Bought parts (the Raspberry Pi, the power boards, the Arducam PTZ base and camera, the UWB boards, the power bank and the tripod): primitives in the `PARTS`
  table in `index.html`, placed at the positions `cad/fit.py` writes to
  **`layout.js`** (generated; `window.SPORTCAM_LAYOUT`).
- No hand positioning: after a CAD or part-size change, re-run `fit.py`;
  the guide follows, including step text that names the side of the
  inlet or switch.

Constants at the top of `index.html`, all from the layout: `LID_Z`
(where the lid's ring meets the enclosure), `TILT_Z` (the Arducam base's tilt
axis), `SHELF_Z` (the underside of the Pi shelf) and `BAND_Z` (the diffuser
band); `ARM_R` (the wall boss the anchor arms and the mast foot bolt
to), `UWB_HALF`, `BOARD_Z`, and for the A3 mast `MAST_R`, `MAST_TOP` and
`A3_Z`. `render_steps.py` reads the same layout from `cad/layout.json`.
