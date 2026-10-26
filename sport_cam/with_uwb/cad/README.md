# cad/ — parametric OpenSCAD sources

Documentation:
**[docs/appendix/appendix-a-cad-parts.md](../../docs/appendix/appendix-a-cad-parts.md)**
(fit workflow, print settings, measure-first checklist).

The layout in `layout.scad` (and `layout.json`) is **generated**: the sizes
of the parts you buy are in [`../../cad/ordered_parts.toml`](../../cad/ordered_parts.toml),
design choices in `config.scad`, and `../../cad/fit.py` solves where
everything goes, renders the STLs and audits the fit.

```bash
python3 cad/fit.py           # from sport_cam/ — or ./render_all.sh here, which runs it
```

Per-part previews with STL download links:
[BOM printed-parts table](../../docs/with_uwb/setup/10-bill-of-materials.md#printed-parts).
