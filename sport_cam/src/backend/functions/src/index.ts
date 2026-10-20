/**
 * SportCam backend: one HTTPS function (`api`) serving the whole API, plus
 * Firestore for the cameras' live state and Cloud Storage for recordings.
 * Nothing runs anywhere else — not on a home server, not on a PC.
 *
 * Locally, `npm run dev` runs this under the Firebase emulators (functions,
 * Firestore, Storage) with a simulated camera; see src/backend/README.md.
 */
import { initializeApp } from "firebase-admin/app";
import { onRequest } from "firebase-functions/v2/https";
import { createApp } from "./app.js";

initializeApp();

export const api = onRequest({ region: "us-central1", memory: "256MiB", maxInstances: 4 }, createApp());
