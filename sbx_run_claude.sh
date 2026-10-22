#!/usr/bin/env bash
# Start Claude in the claude-mkcmkdo Docker sandbox.
# .sbx-cache/ holds the sandbox's tools (see sbx_setup.sh); make it here on
# the host first so a fresh clone has it before the sandbox mounts the repo.
repo=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$repo/.sbx-cache" && touch "$repo/.sbx-cache/.metadata_never_index"
sbx run --name claude-mkcmkdo claude "$repo" -- --dangerously-skip-permissions
