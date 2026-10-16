#!/usr/bin/env bash
# One-time Firebase project creation for the SportCam cloud backend.
#
#   ./scripts/firebase-setup.sh <project-id>       e.g. sportcam-aaron
#
# Prereqs on your machine:
#   npm i -g firebase-tools     (and: firebase login)
#   gcloud CLI (optional — used to create the recordings bucket; otherwise
#   the script prints the one manual console step)
set -euo pipefail
cd "$(dirname "$0")/../firebase"

PROJECT_ID="${1:?usage: firebase-setup.sh <project-id>}"
REGION="us-central1"
BUCKET="${PROJECT_ID}-recordings"

command -v firebase >/dev/null || { echo "install the CLI first: npm i -g firebase-tools && firebase login"; exit 1; }

echo "==> Creating Firebase project '${PROJECT_ID}' (skips if it already exists)"
firebase projects:create "${PROJECT_ID}" --display-name "SportCam" || true

echo "==> Pointing this repo at the project"
cat > .firebaserc <<EOF
{ "projects": { "default": "${PROJECT_ID}" } }
EOF

echo "==> Creating the recordings bucket gs://${BUCKET}"
if command -v gcloud >/dev/null; then
  gcloud storage buckets create "gs://${BUCKET}" \
      --project "${PROJECT_ID}" --location "${REGION}" \
      --uniform-bucket-level-access 2>/dev/null \
    || echo "    (bucket exists or gcloud not authed — see manual step below)"
else
  echo "    gcloud not found — create it manually:"
  echo "    https://console.cloud.google.com/storage/create-bucket?project=${PROJECT_ID}"
  echo "    name: ${BUCKET}, location: ${REGION}, uniform access: on"
fi

cat <<EOF

==> One manual step (Google requires it in the console):
    Upgrade the project to the Blaze (pay-as-you-go) plan — Cloud Functions
    need it. Free-tier quotas still apply; light use costs ~\$0.
    https://console.firebase.google.com/project/${PROJECT_ID}/usage/details

Then deploy with:   ./scripts/firebase-deploy.sh
EOF
