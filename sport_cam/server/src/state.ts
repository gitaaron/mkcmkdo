import { EventEmitter } from "node:events";

export type CamState = "off" | "idle" | "tracking" | "recording";

/**
 * Which hardware build this server is serving — see the with_uwb/ and
 * without_uwb/ folders. Set with TRACKING_MODE; the apps read it from the
 * state snapshot and word their buttons and hints to match.
 *   with_uwb     the subject wears a UWB tag; the tag starts and ends sessions
 *   without_uwb  vision only; the camera sweeps for a person and locks on
 */
export type TrackingMode = "with_uwb" | "without_uwb";

export const TRACKING_MODES: readonly TrackingMode[] = ["with_uwb", "without_uwb"];

export function parseTrackingMode(value: string | undefined): TrackingMode {
  const v = (value ?? "with_uwb").trim();
  if (!(TRACKING_MODES as readonly string[]).includes(v)) {
    throw new Error(`TRACKING_MODE must be one of ${TRACKING_MODES.join(", ")} (got '${v}')`);
  }
  return v as TrackingMode;
}

export interface Telemetry {
  pan?: number;          // degrees from centre, +/- PAN_MAX_DEG (not 0-360)
  tilt?: number;
  zoomMm?: number;
  dist?: number;         // with_uwb: from ranging; without_uwb: from the person's size in frame
  phase?: "acquiring" | "acquired" | null;  // while tracking: found the subject yet?
  acquireStalled?: boolean;  // acquiring a long time: nobody found / vision cannot see the subject
  tagPresent?: boolean;      // with_uwb only: the wearable is switched on and ranging
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
  mode: TrackingMode;
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
  private snap: StateSnapshot;

  constructor(mode: TrackingMode = "with_uwb") {
    this.snap = {
      mode,
      state: "idle",
      telemetry: {},
      deviceOnline: false,
      whepUrl: null,
      updatedAt: new Date().toISOString(),
    };
  }

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
