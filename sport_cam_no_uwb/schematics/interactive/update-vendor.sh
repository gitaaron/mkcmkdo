#!/usr/bin/env bash
# Re-fetch the vendored libraries for the interactive schematic viewer.
# (They are committed to the repo so the viewer works offline; run this only
# to upgrade versions.)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p vendor
curl -sfo vendor/d3.min.js          "https://cdn.jsdelivr.net/npm/d3@6.7.0/dist/d3.min.js"
curl -sfo vendor/elk.bundled.js     "https://cdn.jsdelivr.net/npm/elkjs@0.7.1/lib/elk.bundled.js"
curl -sfo vendor/d3-hwschematic.js  "https://cdn.jsdelivr.net/npm/d3-hwschematic@0.1.6/dist/d3-hwschematic.js"
curl -sfo vendor/d3-hwschematic.css "https://cdn.jsdelivr.net/npm/d3-hwschematic@0.1.6/dist/d3-hwschematic.css"
echo "vendored:"
ls -la vendor/
