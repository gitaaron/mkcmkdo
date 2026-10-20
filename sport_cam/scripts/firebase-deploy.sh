#!/usr/bin/env bash
# Build and deploy SportCam to Firebase — the whole backend and the web app.
#
#   ./scripts/firebase-deploy.sh        (or: npm run deploy)
#
# Deploys, from src/backend:
#   functions : the `api` function — every /api/** call, upload and playback
#   hosting   : the web app (src/web), same-origin with /api through a rewrite
#   firestore : rules (anyone holding a camera key can read that camera; no
#               client writes) and indexes
#   storage   : rules (deny all — recordings move on signed URLs)
#
# Run ./scripts/firebase-setup.sh <project-id> once first.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f src/backend/.firebaserc ] || { echo "run ./scripts/firebase-setup.sh <project-id> first"; exit 1; }

echo "==> Installing + building the web app and the function"
npm install --no-audit --no-fund
npm run build

echo "==> Deploying"
(cd src/backend && npx --no-install firebase deploy --only functions,hosting,firestore,storage)

PROJECT_ID=$(sed -n 's/.*"default": "\([^"]*\)".*/\1/p' src/backend/.firebaserc)
cat <<EOF

Deployed.
  App     : https://${PROJECT_ID}.web.app/#key=<CAMERA_KEY>   (setup printed the full link)
  Health  : https://${PROJECT_ID}.web.app/api/health
EOF
