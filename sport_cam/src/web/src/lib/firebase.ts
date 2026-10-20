import { initializeApp, type FirebaseOptions } from "firebase/app";
import { connectFirestoreEmulator, getFirestore, type Firestore } from "firebase/firestore";

/**
 * Firestore, either the real one or the local emulator.
 *
 * In dev (`npm run dev`) the app uses the emulator on the same host as the
 * page, so a phone on your Wi-Fi works too. Deployed on Firebase Hosting, the
 * project's config comes from /__/firebase/init.json, which Hosting serves
 * automatically — nothing to paste in.
 */
let db: Promise<Firestore> | null = null;

async function config(): Promise<FirebaseOptions> {
  if (import.meta.env.DEV) return { projectId: "demo-sportcam", apiKey: "demo-key" };
  const res = await fetch("/__/firebase/init.json");
  if (!res.ok) throw new Error("no Firebase config — is this served from Firebase Hosting?");
  return res.json();
}

export function firestore(): Promise<Firestore> {
  db ??= config().then((cfg) => {
    const fs = getFirestore(initializeApp(cfg));
    if (import.meta.env.DEV) connectFirestoreEmulator(fs, location.hostname, 8080);
    return fs;
  });
  return db;
}
