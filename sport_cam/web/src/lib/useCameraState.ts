import { reactive, readonly } from "vue";
import { api, type RecordingMeta, type StateSnapshot } from "./api.js";

export interface UploadProgress {
  name: string;
  sent: number;
  total: number;
}

interface CameraStore extends StateSnapshot {
  connected: boolean;
  recordings: RecordingMeta[];
  upload: UploadProgress | null;
  lastSaved: RecordingMeta | null; // most recent arrival — drives the toast
}

const store = reactive<CameraStore>({
  state: "off",
  telemetry: {},
  deviceOnline: false,
  whepUrl: null,
  updatedAt: "",
  connected: false,
  recordings: [],
  upload: null,
  lastSaved: null,
});

let started = false;

function connect(): void {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => {
    store.connected = true;
  };
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "state") {
        Object.assign(store, {
          state: msg.state,
          telemetry: msg.telemetry ?? {},
          deviceOnline: msg.deviceOnline ?? false,
          whepUrl: msg.whepUrl ?? null,
          updatedAt: msg.updatedAt ?? "",
        });
      } else if (msg.type === "recordings") {
        const prev = store.recordings[0]?.name;
        store.recordings = msg.recordings ?? [];
        const newest = store.recordings[0];
        if (newest && newest.name !== prev && prev !== undefined) {
          store.lastSaved = newest;
        }
        store.upload = null; // list refresh means any in-flight upload landed
      } else if (msg.type === "uploadProgress") {
        store.upload = { name: msg.name, sent: msg.sent, total: msg.total };
      }
    } catch {
      /* ignore malformed */
    }
  };
  ws.onclose = () => {
    store.connected = false;
    setTimeout(connect, 1500);
  };
}

/** Reactive camera state fed by the server's WebSocket broadcasts. */
export function useCameraState() {
  if (!started) {
    started = true;
    connect();
    // WS-less deployments (Firebase hosting) still get the library via REST.
    api.getRecordings().then((r) => {
      if (store.recordings.length === 0) store.recordings = r.recordings;
    }).catch(() => { /* server may not be up yet */ });
  }
  return readonly(store);
}

export function dismissToast(): void {
  store.lastSaved = null;
}
