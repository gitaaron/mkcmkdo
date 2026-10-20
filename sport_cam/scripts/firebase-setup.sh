#!/usr/bin/env bash
# One-time Firebase setup for SportCam: the project, Firestore, the recordings
# bucket, a Firestore-only account for the camera, and the camera key.
#
#   ./scripts/firebase-setup.sh <project-id>       e.g. sportcam-aaron
#
# Prereqs on your computer:
#   npm install                 (firebase-tools comes with the repo: npx firebase)
#   npx firebase login
#   gcloud CLI, logged in       (for the bucket and the two service-account
#                                steps; without it the script prints what to
#                                do in the console instead)
#
# Writes:
#   src/backend/.firebaserc        points the backend at the project
#   sportcam-firebase.json         the camera's service-account key — copy it to
#                                  the Pi as /home/pi/sportcam-firebase.json,
#                                  then delete it here. Never commit it.
# and prints the lines for the camera's config.py and the app link.
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT_ID="${1:?usage: firebase-setup.sh <project-id>}"
REGION="us-central1"
BUCKET="${PROJECT_ID}-recordings"
CAMERA_SA="sportcam-camera"
FIREBASE="npx --no-install firebase"

$FIREBASE --version >/dev/null 2>&1 || { echo "run npm install first (it installs firebase-tools)"; exit 1; }
have_gcloud() { command -v gcloud >/dev/null && gcloud auth list --format='value(account)' 2>/dev/null | grep -q .; }

echo "==> Creating Firebase project '${PROJECT_ID}' (skips if it already exists)"
$FIREBASE projects:create "${PROJECT_ID}" --display-name "SportCam" || true

echo "==> Pointing src/backend at the project"
cat > src/backend/.firebaserc <<EOF
{ "projects": { "default": "${PROJECT_ID}" } }
EOF

echo "==> Creating the Firestore database (${REGION})"
$FIREBASE firestore:databases:create "(default)" --location "${REGION}" --project "${PROJECT_ID}" 2>/dev/null \
  || echo "    (exists already, or create it in the console: Build → Firestore Database)"

if have_gcloud; then
  PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
  RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

  echo "==> Creating the recordings bucket gs://${BUCKET}"
  gcloud storage buckets create "gs://${BUCKET}" --project "${PROJECT_ID}" \
      --location "${REGION}" --uniform-bucket-level-access 2>/dev/null \
    || echo "    (bucket exists)"

  echo "==> Letting the API function sign upload/playback URLs"
  gcloud iam service-accounts add-iam-policy-binding "${RUNTIME_SA}" --project "${PROJECT_ID}" \
      --member "serviceAccount:${RUNTIME_SA}" --role roles/iam.serviceAccountTokenCreator >/dev/null

  echo "==> Creating the camera's account (${CAMERA_SA}: Firestore only)"
  gcloud iam service-accounts create "${CAMERA_SA}" --project "${PROJECT_ID}" \
      --display-name "SportCam camera (Firestore only)" 2>/dev/null || echo "    (exists)"
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member "serviceAccount:${CAMERA_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
      --role roles/datastore.user --condition=None >/dev/null
  if [ ! -f sportcam-firebase.json ]; then
    gcloud iam service-accounts keys create sportcam-firebase.json \
        --iam-account "${CAMERA_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
  fi
else
  cat <<EOF
    gcloud not found or not logged in — do these four in the console instead:
    1. Cloud Storage → create bucket "${BUCKET}" in ${REGION}, uniform access on
    2. IAM → service account "<project number>-compute@developer.gserviceaccount.com"
       → grant itself "Service Account Token Creator"
    3. IAM → create service account "${CAMERA_SA}" with role "Cloud Datastore User"
    4. that account → Keys → Add key → JSON → save as sportcam-firebase.json here
EOF
fi

CAMERA_KEY=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)

cat <<EOF

==> One manual step (Google requires it in the console):
    Upgrade the project to the Blaze (pay-as-you-go) plan — Cloud Functions
    need it. Free-tier quotas still apply; light use costs ~\$0.
    https://console.firebase.google.com/project/${PROJECT_ID}/usage/details

==> The camera: put these in src/<build>/device/sportcam/config.py on the Pi
    FIREBASE_PROJECT = "${PROJECT_ID}"
    CAMERA_KEY = "${CAMERA_KEY}"
    UPLOAD_API_BASE = "https://${PROJECT_ID}.web.app"
    and copy the key file:  scp sportcam-firebase.json pi@sportcam.local:/home/pi/
    then delete it here:    rm sportcam-firebase.json

==> Then deploy:   npm run deploy

==> Your app link (keep it private — the key in it is what lets you in):
    https://${PROJECT_ID}.web.app/#key=${CAMERA_KEY}
    Flutter app:  --dart-define=SPORTCAM_FALLBACK=https://${PROJECT_ID}.web.app
                  --dart-define=SPORTCAM_CAMERA_KEY=${CAMERA_KEY}
EOF
