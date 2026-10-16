import { EventEmitter } from "node:events";

export type CamState = "off" | "idle" | "tracking" | "recording";

export interface Telemetry {
  pan?: number;          // degrees from centre, +/- PAN_MAX_DEG (not 0-360)
  tilt?: number;
  zoomMm?: number;
  dist?: number;         // estimated from the person's size in frame; null while searching
  phase?: "acquiring" | "acquired" | null;  // while tracking: sweeping for a person, or locked on?
  acquireStalled?: boolean;  // searching a long time: nobody found
  battery?: number;          // fraction of the pack remaining, 0-1
  batteryWatts?: number;     // present draw
  batteryMinutes?: number;   // estimated runtime left
  batteryLevel?: "ok" | "low" | "critical";
  storageFreeGb?: number;      // space left on the SD card
  storageMinutes?: number;     // recording time that space represents
  storageLevel?: "ok" | "low" | "critical";
  pendingUploads?: number;     // clips still on the card awaiting upload
}

export interface StateSnapshot {
  state: CamState;
  telemetry: Telemetry;
  deviceOnline: boolean;
  whepUrl: string | null;
  updatedAt: string;
}

/**
 * Persistence boundary. The in-memory implementation below is used locally;
 * swap for a Firestore-document-backed implementation when migrating to
 * Firebase — nothing else in the codebase changes.
 */
export interface Store {
  get(): StateSnapshot;
  patch(p: Partial<StateSnapshot>): StateSnapshot;
  on(event: "change", fn: (s: StateSnapshot) => void): void;
}

export type FnErrorCode = "failed-precondition" | "invalid-argument" | "not-found" | "internal";

export class FnError extends Error {
  constructor(public code: FnErrorCode, message: string) {
    super(message);
  }
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

export class MemoryStore implements Store {
  private emitter = new EventEmitter();
  private snap: StateSnapshot = {
    state: "idle",
    telemetry: {},
    deviceOnline: false,
    whepUrl: null,
    updatedAt: new Date().toISOString(),
  };

  get(): StateSnapshot {
    return this.snap;
  }

  patch(p: Partial<StateSnapshot>): StateSnapshot {
    this.snap = { ...this.snap, ...p, updatedAt: new Date().toISOString() };
    this.emitter.emit("change", this.snap);
    return this.snap;
  }

  on(event: "change", fn: (s: StateSnapshot) => void): void {
    this.emitter.on(event, fn);
  }
}

/** Transition helper used by the callable functions. */
export function transition(store: Store, to: CamState): StateSnapshot {
  assertTransition(store.get().state, to);
  return store.patch({ state: to });
}
