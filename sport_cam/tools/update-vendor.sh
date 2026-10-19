#!/usr/bin/env bash
# Re-fetch the vendored libraries for the docs viewer.
# (They are committed to the repo so the viewer works offline; run this only
# to upgrade versions.)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p vendor
curl -sfo vendor/marked.min.js "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"
echo "vendored:"
ls -la vendor/
