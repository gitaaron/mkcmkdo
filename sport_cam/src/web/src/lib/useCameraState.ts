import { reactive, readonly, watch as vueWatch } from "vue";
import {
  collection, doc, limit, onSnapshot, orderBy, query, type Timestamp, type Unsubscribe,
} from "firebase/firestore";
import { api, recordingUrl, type CamState, type RecordingMeta, type StateSnapshot } from "./api.js";
import { cameraKey } from "./cameraKey.js";
import { chime } from "./chime.js";
import { firestore } from "./firebase.js";

export interface UploadProgress {
  name: string;
  sent: number;
  total: number;
}

interface CameraStore extends StateSnapshot {
  connected: boolean;              // we have the camera's document
  recordings: RecordingMeta[];
  upload: UploadProgress | null;
  lastSaved: RecordingMeta | null; // most recent arrival — drives the toast
  previewUrl: string | null;       // latest preview frame (object URL)
}

/** Matches the API: a camera that hasn't beaten its heart in this long is offline. */
const ONLINE_WINDOW_MS = 20_000;
/** How often to tell the camera someone is watching (it stops previews after a minute). */
const WATCH_EVERY_MS = 30_000;

const store = reactive<CameraStore>({
  mode: undefined,
  state: "off",
  telemetry: {},
  deviceOnline: false,
  whepUrl: null,
  updatedAt: "",
  connected: false,
  recordings: [],
  upload: null,
  lastSaved: null,
  previewUrl: null,
});

let lastState: CamState | null = null;   // null until the first snapshot
let seenAt = 0;

/** Chime on recording start and stop — never on the snapshot that arrives at connect. */
function announce(next: CamState): void {
  if (lastState !== null && lastState !== next) {
    if (next === "recording") chime("start");
    else if (lastState === "recording") chime("stop");
  }
  lastState = next;
}

const ms = (t: Timestamp | null | undefined) => (t ? t.toMillis() : 0);

let unsubs: Unsubscribe[] = [];

async function subscribe(key: string): Promise<void> {
  unsubs.forEach((u) => u());
  unsubs = [];
  Object.assign(store, { connected: false, recordings: [], upload: null, lastSaved: null });
  lastState = null;

  const db = await firestore();
  const cam = doc(db, "cameras", key);

  unsubs.push(onSnapshot(cam, (snap) => {
    const d = snap.data();
    store.connected = snap.exists();
    if (!d) return;
    announce(d.state);
    seenAt = ms(d.deviceSeenAt);
    Object.assign(store, {
      mode: d.mode,
      state: d.state,
      telemetry: d.telemetry ?? {},
      deviceOnline: Date.now() - seenAt < ONLINE_WINDOW_MS,
      whepUrl: d.whepUrl ?? null,
      updatedAt: d.updatedAt ? new Date(ms(d.updatedAt)).toISOString() : "",
      upload: d.upload ?? null,
    });
  }, () => { store.connected = false; }));

  let first = true;
  unsubs.push(onSnapshot(
    query(collection(cam, "recordings"), orderBy("createdAt", "desc"), limit(100)),
    (snap) => {
      const prev = store.recordings[0]?.name;
      store.recordings = snap.docs.map((r) => {
        const v = r.data();
        return {
          name: v.name,
          bytes: v.bytes,
          durationS: v.durationS ?? null,
          createdAt: new Date(ms(v.createdAt)).toISOString(),
          url: recordingUrl(v.name),
        };
      });
      const newest = store.recordings[0];
      if (!first && newest && newest.name !== prev) store.lastSaved = newest;
      first = false;
    },
  ));

  unsubs.push(onSnapshot(doc(cam, "live", "preview"), (snap) => {
    const p = snap.data();
    if (!p?.jpeg) return;
    const old = store.previewUrl;
    store.previewUrl = URL.createObjectURL(new Blob([p.jpeg.toUint8Array()], { type: "image/jpeg" }));
    if (old) URL.revokeObjectURL(old);
  }));
}

/** Keep the camera posting previews while this page is visible. */
function keepWatching(): void {
  const ping = () => {
    if (document.visibilityState === "visible" && cameraKey.value) api.watch().catch(() => { /* offline */ });
  };
  ping();
  setInterval(ping, WATCH_EVERY_MS);
  document.addEventListener("visibilitychange", ping);
  // the heartbeat goes stale without a new snapshot, so re-check it
  setInterval(() => { store.deviceOnline = Date.now() - seenAt < ONLINE_WINDOW_MS; }, 2000);
}

let started = false;

/** Reactive camera state, live from the camera's Firestore document. */
export function useCameraState() {
  if (!started) {
    started = true;
    vueWatch(cameraKey, (k) => { if (k) subscribe(k); }, { immediate: true });
    keepWatching();
  }
  return readonly(store);
}

export function dismissToast(): void {
  store.lastSaved = null;
}
