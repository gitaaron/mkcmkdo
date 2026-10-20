# 13 — Assembly guide (interactive 3D)

**Open [`index.html`](index.html)** — straight from disk, or via `npm run docs`
at http://localhost:8090/without_uwb/docs/setup/assembly/index.html (it is also linked from the
docs viewer's sidebar).

Twelve steps in five phases (prepare → enclosure → camera → power & cables →
finish), each with a live 3D rendering of exactly that step: parts already
fitted in grey, the part being fitted highlighted in blue and animated along
its insertion path, green arrows and callouts for direction and wiring, plus
parts, tools and checks. Click any part or tool for a picture and a short description of what it is. Orbit by dragging, scroll to zoom, right-drag to pan.
The viewer bar has an *exploded ↔ assembled* slider, preset views
(Iso / Front / Side / Top / Under), **X-ray** and **Labels**; the last steps
have a **Motion demo** that sweeps pan and tilt between their soft limits.
Progress is kept in the browser's localStorage; steps are deep-linkable
(`index.html#lid-ptz`). Keyboard: ← → move, D done, R replay, X x-ray,
L labels.

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

Run it after changing a part size in `cad/ordered_parts.toml` or anything in
`<build>/cad/`. It re-runs `build_models.py` (cad/stl → `models.js`) and
`render_steps.py` (fallback PNGs) when `numpy-stl` and `matplotlib` are
installed.

The printed parts are the real STL geometry. Everything bought — the Raspberry
Pi, the power boards, the Arducam PTZ base and camera, the
power bank and the tripod — is a primitive defined in the `PARTS` table in
`index.html`, at the position `cad/fit.py` solved for it and wrote to
**`layout.js`** (generated; `window.SPORTCAM_LAYOUT`). Nothing in the guide is
positioned by hand any more: change the CAD or a part size, re-run `fit.py`,
and the guide follows — step text included, where it says which side of the
enclosure the inlet or the switch is on.

The constants at the top of `index.html` all come from the layout: `LID_Z`
(where the lid's ring meets the enclosure), `TILT_Z` (the Arducam base's tilt
axis), `SHELF_Z` (the underside of the Pi shelf) and `BAND_Z` (the diffuser
band). `render_steps.py` reads the same layout from `cad/layout.json`.
