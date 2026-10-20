/**
 * The camera's live state, kept in one Firestore document per camera:
 *
 *   cameras/{cameraKey}                 this file's CameraDoc
 *   cameras/{cameraKey}/live/preview    low-rate JPEG preview, while someone watches
 *   cameras/{cameraKey}/recordings/*    the recording library (recordings.ts)
 *
 * The camera key is the document id: a long random string the camera and
 * every app share. Knowing it is what lets you read the camera and call its
 * functions; firestore.rules lets anyone *get* a camera by key but never
 * *list* them, so the key can't be discovered.
 *
 * The camera owns its state, as it did with the home server. It writes the
 * document itself (state, telemetry, a heartbeat) with `stateBy: "device"`.
 * The app's commands go through the functions below, which check the
 * transition and write `state` with `stateBy: "app"`; the camera's listener
 * adopts that and writes back what it actually did.
 */
import { FieldValue, Timestamp, getFirestore, type DocumentReference } from "firebase-admin/firestore";
import { FnError } from "./errors.js";

export type CamState = "off" | "idle" | "tracking" | "recording";

/** Which hardware build the camera is. The camera reports it; the apps word their buttons to match. */
export type TrackingMode = "with_uwb" | "without_uwb";

export interface Telemetry {
  pan?: number;          // degrees from centre, +/- PAN_MAX_DEG (not 0-360)
  tilt?: number;
  zoomMm?: number;
  dist?: number | null;  // with_uwb: from ranging; without_uwb: from the person's size in frame
  /** idle: is a person in frame? tracking: found the subject yet? */
  phase?: "person-in-frame" | "no-person-in-frame" | "acquiring" | "acquired" | null;
  acquireStalled?: boolean;  // acquiring a long time: nobody found / vision cannot see the subject
  tagPresent?: boolean;      // with_uwb only: the wearable is switched on and ranging
  battery?: number;          // fraction of the pack remaining, 0-1
  batteryWatts?: number;
  batteryMinutes?: number;
  batteryLevel?: "ok" | "low" | "critical";
  storageFreeGb?: number;
  storageMinutes?: number;
  storageLevel?: "ok" | "low" | "critical";
  pendingUploads?: number;
}

/** What is stored in cameras/{key}. */
export interface CameraDoc {
  mode: TrackingMode;
  state: CamState;
  stateBy: "app" | "device";
  telemetry: Telemetry;
  deviceSeenAt: Timestamp | null;   // the camera's heartbeat
  whepUrl: string | null;           // WebRTC stream on the camera's LAN, if it runs one
  upload: { name: string; sent: number; total: number } | null;
  warning: { code: string; at: Timestamp } | null;
  viewerAt: Timestamp | null;       // an app is watching: the camera posts previews
  updatedAt: Timestamp;
}

/** What the API returns and the apps render — the same shape the home server sent. */
export interface StateSnapshot {
  mode: TrackingMode;
  state: CamState;
  telemetry: Telemetry;
  deviceOnline: boolean;
  whepUrl: string | null;
  upload: { name: string; sent: number; total: number } | null;  // a clip on its way to the library
  updatedAt: string;
}

/** The camera beats every few seconds; past this it counts as offline. */
export const ONLINE_WINDOW_MS = 20_000;

const KEY_RE = /^[A-Za-z0-9_-]{8,64}$/;

export function cameraRef(key: unknown): DocumentReference {
  if (typeof key !== "string" || !KEY_RE.test(key)) {
    throw new FnError("invalid-argument", "missing or malformed camera key (X-Camera-Key header or ?k=)");
  }
  return getFirestore().collection("cameras").doc(key);
}

export function isOnline(d: Pick<CameraDoc, "deviceSeenAt">, now = Date.now()): boolean {
  return !!d.deviceSeenAt && now - d.deviceSeenAt.toMillis() < ONLINE_WINDOW_MS;
}

export function snapshot(d: CameraDoc): StateSnapshot {
  return {
    mode: d.mode,
    state: d.state,
    telemetry: d.telemetry ?? {},
    deviceOnline: isOnline(d),
    whepUrl: d.whepUrl ?? null,
    upload: d.upload ?? null,
    updatedAt: d.updatedAt.toDate().toISOString(),
  };
}

const TRANSITIONS: Record<CamState, CamState[]> = {
  off: ["idle"],
  idle: ["off", "tracking"],
  tracking: ["off", "idle", "recording"],
  recording: ["off", "idle", "tracking"],
};

export function assertTransition(from: CamState, to: CamState): void {
  if (!TRANSITIONS[from].includes(to)) {
    throw new FnError("failed-precondition", `cannot go from '${from}' to '${to}'`);
  }
}

async function load(ref: DocumentReference): Promise<CameraDoc> {
  const snap = await ref.get();
  if (!snap.exists) throw new FnError("not-found", "no camera with that key — has it connected yet?");
  return snap.data() as CameraDoc;
}

export async function getState(ref: DocumentReference): Promise<StateSnapshot> {
  return snapshot(await load(ref));
}

/**
 * Ask the camera for a new state. `pick` maps the current state to the one
 * wanted (or null for "nothing to do", which setPower uses to be idempotent). Refused while the camera is offline:
 * nothing would act on it, and the app would show a state the camera isn't in.
 */
export async function requestState(
  ref: DocumentReference,
  pick: (current: CamState) => CamState | null,
): Promise<StateSnapshot> {
  return getFirestore().runTransaction(async (tx) => {
    const snap = await tx.get(ref);
    if (!snap.exists) throw new FnError("not-found", "no camera with that key — has it connected yet?");
    const d = snap.data() as CameraDoc;
    const to = pick(d.state);
    if (to === null) return snapshot(d);
    assertTransition(d.state, to);   // includes "already there", as on the camera's own API
    if (!isOnline(d)) throw new FnError("failed-precondition", "the camera is offline");
    const now = Timestamp.now();
    tx.update(ref, { state: to, stateBy: "app", updatedAt: now });
    return snapshot({ ...d, state: to, updatedAt: now });
  });
}

/** An app is showing the live view: keep the camera posting previews for a minute. */
export async function watch(ref: DocumentReference): Promise<{ ok: true }> {
  await load(ref);
  await ref.update({ viewerAt: FieldValue.serverTimestamp() });
  return { ok: true };
}

/** The latest preview frame, for clients that poll rather than listen (the Flutter relay). */
export async function getPreview(ref: DocumentReference): Promise<{ jpeg: string; at: string } | null> {
  const snap = await ref.collection("live").doc("preview").get();
  if (!snap.exists) return null;
  const p = snap.data() as { jpeg: Buffer | Uint8Array; at: Timestamp };
  return { jpeg: Buffer.from(p.jpeg).toString("base64"), at: p.at.toDate().toISOString() };
}
