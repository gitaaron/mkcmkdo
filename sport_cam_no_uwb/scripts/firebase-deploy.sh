#!/usr/bin/env bash
# Build and deploy the SportCam cloud backend + web app to Firebase.
#
#   ./scripts/firebase-deploy.sh
#
# Deploys:
#   functions : the /api/** callable + playback endpoints (see firebase/functions)
#   hosting   : the Vue app (built same-origin, so /api/call/* just works)
#   firestore : deny-all rules (all access is via the function's Admin SDK)
#
# After deploy, point the Pi at the cloud:
#   device/sportcam/config.py → UPLOAD_API_BASE = "https://<project-id>.web.app"
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f firebase/.firebaserc ] || { echo "run ./scripts/firebase-setup.sh <project-id> first"; exit 1; }

echo "==> Installing workspaces + building the web app (same-origin API base)"
npm install --no-audit --no-fund
VITE_API_BASE="" npm run build -w web

echo "==> Installing + building functions"
(cd firebase/functions && npm install --no-audit --no-fund && npm run build)

echo "==> Deploying"
(cd firebase && firebase deploy --only functions,hosting,firestore)

PROJECT_ID=$(sed -n 's/.*"default": "\([^"]*\)".*/\1/p' firebase/.firebaserc)
cat <<EOF

Deployed.
  App     : https://${PROJECT_ID}.web.app
  Health  : https://${PROJECT_ID}.web.app/api/health
  Pi      : set UPLOAD_API_BASE = "https://${PROJECT_ID}.web.app" in device/sportcam/config.py
EOF
