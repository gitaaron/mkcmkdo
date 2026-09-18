import { reactive, readonly } from "vue";
import type { StateSnapshot } from "./api.js";

interface CameraStore extends StateSnapshot {
  connected: boolean;
}

const store = reactive<CameraStore>({
  state: "off",
  telemetry: {},
  deviceOnline: false,
  whepUrl: null,
  updatedAt: "",
  connected: false,
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
  }
  return readonly(store);
}
