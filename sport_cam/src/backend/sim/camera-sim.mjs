#!/usr/bin/env node
/**
 * Simulated camera for local development (`npm run dev`).
 *
 * Talks to the Firebase emulators exactly the way the real Pi talks to
 * Firebase (src/<build>/device/sportcam/cloud.py):
 *
 *   - writes cameras/{key}: mode, state, telemetry and a heartbeat
 *   - listens to that document and adopts any state an app asked for
 *   - posts preview frames to cameras/{key}/live/preview while an app watches,
 *     with made-up live person boxes
 *   - when a "recording" stops, uploads sim/sample.mp4 through the API
 *     (createUploadUrl → PUT → finalizeRecording), like uploader.py, with
 *     made-up person boxes beside it so the players' overlay has something
 *     to show
 *
 * Environment (npm run dev sets these):
 *   FIRESTORE_EMULATOR_HOST   e.g. 127.0.0.1:8080
 *   GCLOUD_PROJECT            demo-sportcam
 *   CAMERA_KEY                the key the web app uses in dev
 *   TRACKING_MODE             with_uwb | without_uwb
 *   API_BASE                  the functions emulator's URL for `api`
 *
 * Regenerate the frames with `python3 src/backend/sim/gen_frames.py`.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { initializeApp } from "firebase-admin/app";
import { getFirestore, Timestamp } from "firebase-admin/firestore";

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = process.env.GCLOUD_PROJECT ?? "demo-sportcam";
const KEY = process.env.CAMERA_KEY ?? "dev-camera-key";
const MODE = process.env.TRACKING_MODE ?? "with_uwb";
const API = process.env.API_BASE ?? `http://127.0.0.1:5001/${PROJECT}/us-central1/api`;
const SAMPLE = join(HERE, "sample.mp4");
const PREVIEW_MS = 500;
const VIEWER_WINDOW_MS = 60_000;

if (!["with_uwb", "without_uwb"].includes(MODE)) {
  console.error(`[sim] TRACKING_MODE must be with_uwb or without_uwb (got '${MODE}')`);
  process.exit(1);
}
if (!process.env.FIRESTORE_EMULATOR_HOST) {
  console.error("[sim] FIRESTORE_EMULATOR_HOST is not set — the simulator only runs against the emulators");
  process.exit(1);
}

initializeApp({ projectId: PROJECT });
const db = getFirestore();
const cam = db.collection("cameras").doc(KEY);

const frames = (() => {
  try {
    const dir = join(HERE, "frames");
    return readdirSync(dir).filter((f) => f.endsWith(".jpg")).sort().map((f) => readFileSync(join(dir, f)));
  } catch {
    return [];
  }
})();

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function call(name, data) {
  const res = await fetch(`${API}/api/call/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Camera-Key": KEY },
    body: JSON.stringify({ data }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(`${name}: ${body.error?.message ?? res.status}`);
  return body.result;
}

/**
 * Person boxes in the device's boxlog.py format: a climber drifting across,
 * a belayer standing still, and the first second and a half unsure.
 */
function sampleBoxes(durationS) {
  const frames = [];
  for (let t = 0; t <= durationS; t += 1 / 3) {
    frames.push([Math.round(t * 100) / 100, boxesAt(t, t > 1.5)]);
  }
  return Buffer.from(JSON.stringify({ v: 1, size: [1280, 720], frames }));
}

/** The two people at `t` seconds, labelled once the camera is `sure` who climbs. */
function boxesAt(t, sure) {
  const climber = [Math.round(380 + 40 * Math.sin(t / 2)), 120 - Math.round(10 * t) % 60, 150, 420];
  const belayer = [820, 230, 140, 400];
  return [
    [...climber, sure ? "climber" : "unsure"],
    [...belayer, sure ? "other" : "unsure"],
  ];
}

async function put(name, bytes) {
  const target = await call("createUploadUrl", { name });
  const url = target.url.startsWith("/") ? API + target.url : target.url;
  const res = await fetch(url, { method: target.method, headers: target.headers, body: bytes });
  if (!res.ok) throw new Error(`upload HTTP ${res.status}`);
}

/** The same flow as the Pi's uploader.py. */
async function uploadSample(durationS) {
  const name = `rec_${new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14)}.mp4`;
  const bytes = readFileSync(SAMPLE);
  await cam.update({ upload: { name, sent: 0, total: bytes.length } });
  await put(name, bytes);
  await cam.update({ upload: { name, sent: bytes.length, total: bytes.length } });
  await put(name.replace(/\.mp4$/, ".boxes.json"), sampleBoxes(durationS ?? 10));
  await call("finalizeRecording", { name, bytes: bytes.length, durationS, boxes: true });
  console.log(`[sim] recording saved: ${name}`);
}

async function waitForEmulators() {
  for (let i = 0; ; i++) {
    try {
      await cam.get();
      const res = await fetch(`${API}/api/health`);
      if (res.ok) return;
    } catch {
      /* not up yet */
    }
    if (i === 0) console.log("[sim] waiting for the emulators…");
    await sleep(1000);
  }
}

await waitForEmulators();

let state = "idle";
let recStarted = 0;
let trackingSince = 0;
let searchMs = 0;
// Idle sub-state: someone walks into frame for 10 s of every 20.
const personInFrame = () => Math.floor(Date.now() / 10000) % 2 === 1;
// Tracking: search for searchMs (0 with a person already in frame; a turn to
// the tag with UWB, a sweep without), then found for FOUND_CONFIRM_MS, then
// recording.
const SEARCH_MS = MODE === "with_uwb" ? 1500 : 4000;
const FOUND_CONFIRM_MS = 3000;
let pan = 0;
let panDir = 1;
let wh = 0;

await cam.set({
  mode: MODE,
  state,
  stateBy: "device",
  telemetry: {},
  deviceSeenAt: Timestamp.now(),
  whepUrl: null,
  upload: null,
  warning: null,
  viewerAt: null,
  updatedAt: Timestamp.now(),
});
console.log(`[sim] camera '${KEY}' online (${MODE}, ${frames.length} test frames)`);

function adopt(next) {
  const prev = state;
  state = next;
  if (next === "tracking") {
    trackingSince = Date.now();
    // A session started with a person in frame skips search.
    searchMs = personInFrame() ? 0 : SEARCH_MS;
  }
  if (next === "recording") recStarted = Date.now();
  if (prev === "recording" && next !== "recording") {
    const durationS = Math.round((Date.now() - recStarted) / 100) / 10;
    uploadSample(durationS).catch((e) => console.error("[sim] upload failed:", e.message));
  }
  console.log(`[sim] ${prev} → ${next}`);
}

// Commands from the apps arrive as a state written with stateBy: "app".
let viewerAt = 0;
cam.onSnapshot((snap) => {
  const d = snap.data();
  if (!d) return;
  viewerAt = d.viewerAt ? d.viewerAt.toMillis() : 0;
  if (d.stateBy === "app" && d.state !== state) {
    adopt(d.state);
    cam.update({ state, stateBy: "device", updatedAt: Timestamp.now() });
  }
});

// Seed an empty library so the Library screen has something to play.
const lib = await cam.collection("recordings").limit(1).get();
if (lib.empty && statSync(SAMPLE, { throwIfNoEntry: false })) {
  uploadSample(3).catch((e) => console.error("[sim] seeding the library failed:", e.message));
}

const tracking = () => state === "tracking" || state === "recording";

function phase() {
  if (state === "idle") return personInFrame() ? "person-in-frame" : "no-person-in-frame";
  if (state === "recording") return "track";
  if (state !== "tracking") return null;
  return Date.now() - trackingSince < searchMs ? "search" : "found";
}

/** Found: whole seconds left before recording (3, 2, 1); else 0. */
function countdown() {
  if (phase() !== "found") return 0;
  const left = searchMs + FOUND_CONFIRM_MS - (Date.now() - trackingSince);
  return Math.max(1, Math.ceil(left / 1000));
}

function telemetry() {
  const watts = state === "idle" ? 7.5 : 14.5;
  const frac = Math.max(0, 1 - wh / 92);
  return {
    pan: Math.round(pan * 10) / 10,
    tilt: 12,
    zoomMm: 7.4,
    dist: Math.round((4.2 + Math.sin(Date.now() / 3000)) * 100) / 100,
    phase: phase(),
    countdown: countdown(),
    acquireStalled: false,
    ...(MODE === "with_uwb" ? { tagPresent: true } : {}),
    battery: Math.round(frac * 1000) / 1000,
    batteryWatts: watts,
    batteryMinutes: Math.round(((92 * frac) / watts) * 60),
    batteryLevel: frac <= 0.07 ? "critical" : frac <= 0.2 ? "low" : "ok",
  };
}

// Heartbeat + telemetry, once a second.
setInterval(() => {
  if (tracking()) {
    pan += 3.6 * panDir;
    if (pan >= 80 || pan <= -80) panDir = -panDir;
  }
  wh += (state === "idle" ? 7.5 : 14.5) / 3600;
  cam.update({ deviceSeenAt: Timestamp.now(), telemetry: telemetry() })
    .catch((e) => console.error("[sim] heartbeat failed:", e.message));
}, 1000);

// Like the device: a phase change and each second of the countdown go up at
// once (the apps ping and beep on them), and found for FOUND_CONFIRM_MS starts
// recording.
let sent = "";
setInterval(() => {
  const now = `${phase()}/${countdown()}`;
  if (now !== sent) {
    sent = now;
    cam.update({ telemetry: telemetry() })
      .catch((e) => console.error("[sim] telemetry failed:", e.message));
  }
  if (state === "tracking" && Date.now() - trackingSince >= searchMs + FOUND_CONFIRM_MS) {
    adopt("recording");
    cam.update({ state, stateBy: "device", updatedAt: Timestamp.now() });
  }
}, 50);

/**
 * The live view's boxes, like the device: everyone "unsure" in idle (nobody
 * picked yet), the climber and belayer once found, nobody while searching.
 */
function liveBoxes() {
  const t = Date.now() / 1000;
  const p = phase();
  const boxes = p === "search" || p === "no-person-in-frame" ? []
    : boxesAt(t, state === "recording" || p === "found");
  return boxes.map(([x, y, w, h, label]) => ({ x, y, w, h, label }));
}

// Preview frames, only while someone is watching.
let i = 0;
setInterval(() => {
  if (state === "off" || !frames.length || Date.now() - viewerAt > VIEWER_WINDOW_MS) return;
  cam.collection("live").doc("preview")
    .set({ jpeg: frames[i++ % frames.length], at: Timestamp.now(), size: [1280, 720], boxes: liveBoxes() })
    .catch((e) => console.error("[sim] preview failed:", e.message));
}, PREVIEW_MS);
