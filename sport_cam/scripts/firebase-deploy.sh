#!/usr/bin/env bash
# Build and deploy the SportCam backend to Firebase.
#
#   ./scripts/firebase-deploy.sh        (or: npm run deploy)
#
# Deploys, from src/backend:
#   functions : the `api` function — every /api/** call, upload and playback
#   hosting   : https://<project>.web.app/api/** → the function (the address
#               the cameras and the phone app use)
#   firestore : rules (no client access — everything goes through the API)
#               and indexes
#   storage   : rules (deny all — recordings move on signed URLs)
#
# Run ./scripts/firebase-setup.sh <project-id> once first.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f src/backend/.firebaserc ] || { echo "run ./scripts/firebase-setup.sh <project-id> first"; exit 1; }

echo "==> Installing + building the function"
npm install --no-audit --no-fund
npm run build

echo "==> Deploying"
(cd src/backend && npx --no-install firebase deploy --only functions,hosting,firestore,storage)

PROJECT_ID=$(sed -n 's/.*"default": "\([^"]*\)".*/\1/p' src/backend/.firebaserc)
cat <<EOF

Deployed.
  API     : https://${PROJECT_ID}.web.app/api/health
  Phone app: build it with the --dart-define lines setup printed
EOF
