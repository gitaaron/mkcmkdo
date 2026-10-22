#!/usr/bin/env bash
# Resume Claude in the claude-mkcmkdo Docker sandbox.
repo=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$repo/.sbx-cache" && touch "$repo/.sbx-cache/.metadata_never_index"
sbx run --name claude-mkcmkdo -- --resume
