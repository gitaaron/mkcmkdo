# without_uwb/docs/setup/assembly — interactive assembly guide

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
| `build_models.py` | regenerates `models.js` — run after `./cad/render_all.sh` |
| `render_steps.py` | renders the offline fallback turntables into `renders/` |
| `renders/` | fallback PNGs, used only when three.js can't load (no internet / no WebGL) |
| `../../../../docs/assembly/catalog.js`, `catalog.css` | shared by both builds: the parts-and-tools catalogue. Names in a step's Parts and Tools lists become links that open a picture and a description ("what is an M2.5 × 6?"). Add an entry there when a step names something new |

## Regenerating after a CAD change

```bash
./cad/render_all.sh                     # .scad → cad/stl/*.stl
python3 docs/setup/assembly/build_models.py   # cad/stl → docs/assembly/models.js   (needs numpy-stl)
python3 docs/setup/assembly/render_steps.py   # fallback PNGs                        (needs numpy-stl, matplotlib)
```

The printed parts (base housing, lid, LED diffuser ring, battery tray) are the
real STL geometry. Everything bought — the Raspberry Pi, the power chain, the
Arducam PTZ base and camera, the power bank and the tripod — is a primitive
defined in the `PARTS` table in `index.html`, positioned from the dimensions in
`cad/config.scad`. If you move a feature in the CAD, update the matching seat
position there.

The constants at the top of `index.html` fix the geometry: `LID_Z` (where the
lid's spigot meets the enclosure) and `TILT_Z` (the Arducam base's tilt axis).
`render_steps.py` mirrors the ones it uses.
