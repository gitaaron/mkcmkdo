# Setup — start here (with UWB)

Build procedure from ordering to a working camera, in order. 11 — 3D
printing is shared by both builds; the others are build-specific.

| # | Doc | Covers | Time |
| --- | --- | --- | --- |
| 10 | [**Bill of materials**](10-bill-of-materials.md) | every part to order, with prices and Canadian sources, and the printed parts | ≈ 2 weeks of deliveries |
| 11 | [**3D printing**](../../setup/11-3d-printing.md) | printer requirements, filament, settings, orientation and print order for every printed part | ≈ 41 h of printing |
| 12 | [**Wiring guide**](12-wiring.md) | every connection, pin by pin, in wiring order with a check after each, linked to the [schematics](../../../with_uwb/schematics/interactive/index.html) | ≈ 2 h, made during the assembly |
| 13 | [**Assembly guide**](assembly/index.html) (interactive, 3D) | the enclosure, power, LED ring, Pi shelf, camera, anchors and mast, battery, tripod, power-on checks | a weekend |
| 14 | [**Software setup**](14-software-setup.md) | radio firmware, Raspberry Pi OS, the camera software, bench checks, calibration, services, the app | ≈ 2 h |
| 15 | [**Verification checklist**](15-verification.md) | what to measure before printing, check on arrival, confirm on the bench and in the first session | used alongside the docs above |

| Rule | Detail |
| --- | --- |
| Read 12 before 13 | the assembly guide makes the wiring guide's connections in the same order, at the step each belongs to |
| Measure before printing | [15 — Verification](15-verification.md#before-you-print): nine measurements decide whether the prints fit the bought parts. Enter them in `cad/ordered_parts.toml` and run `python3 cad/fit.py` ([Appendix A](../../appendix/appendix-a-cad-parts.md#fit-the-layout-to-your-parts)) |
| Assembly guide | single HTML page; open from disk or via `npm run docs`. Build scripts: [assembly/README.md](assembly/README.md) |

**Working directory.** Commands touching `cad/` or `docs/` are relative to
[`with_uwb/`](../../../with_uwb/): run from there (`cd with_uwb`), or prefix `with_uwb/` from the repo
root (scripts resolve paths from their own location). Pi software:
`src/with_uwb/device/`. Shared code (Firebase backend, apps): elsewhere under
`src/`.
