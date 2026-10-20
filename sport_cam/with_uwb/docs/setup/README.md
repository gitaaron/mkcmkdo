# Setup — start here (with UWB)

These docs take you from ordering parts to a camera that films on its own.
Follow them in order. 11 — 3D printing is shared by both builds; the rest
are specific to this build.

| # | Doc | Covers | Time |
| --- | --- | --- | --- |
| 10 | [**Bill of materials**](10-bill-of-materials.md) | every part to order, with prices and Canadian sources, and the printed parts | ≈ 2 weeks of deliveries |
| 11 | [**3D printing**](../../../docs/setup/11-3d-printing.md) | printer requirements, filament, settings, orientation and print order for every printed part | ≈ 31 h of printing |
| 12 | [**Wiring guide**](12-wiring.md) | every connection, pin by pin, in wiring order with a check after each, linked to the [schematics](../../schematics/interactive/index.html) | ≈ 2 h, made during the assembly |
| 13 | [**Assembly guide**](assembly/index.html) (interactive, 3D) | the enclosure, power, LED ring, Pi shelf, camera, anchors and mast, battery, tripod, power-on checks | a weekend |
| 14 | [**Software setup**](14-software-setup.md) | radio firmware, Raspberry Pi OS, the camera software, bench checks, calibration, services, the app | ≈ 2 h |
| 15 | [**Verification checklist**](15-verification.md) | what to measure before printing, check on arrival, confirm on the bench and in the first session | used alongside the docs above |

Read the wiring guide before you start the assembly: the assembly guide makes
its connections in the same order, at the step where each one goes in.

Before you print anything, work through
[15 — Verification](15-verification.md#before-you-print): five
measurements decide whether the printed parts fit what you bought. Put them in
`cad/ordered_parts.toml` and run `python3 cad/fit.py` (see
[Appendix A](../../../docs/appendix/appendix-a-cad-parts.md#fit-the-layout-to-your-parts)).

The assembly guide is a single HTML page. Open it straight from disk, or run
`npm run docs` and pick it from the sidebar. Its build scripts are described
in [assembly/README.md](assembly/README.md).

Commands in these guides that touch `cad/` or `docs/` are written
relative to this build's folder, [`with_uwb/`](../../). Run them from there (`cd with_uwb`),
or prefix the path from the repo root — every script finds its files from its
own location, so both work. The Pi software is in `src/with_uwb/device/`, and things common to both builds
(the Firebase backend, the apps) are under `src/`; they're linked from here.
