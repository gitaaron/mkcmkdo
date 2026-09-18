import type { Store, StateSnapshot } from "../state.js";
import { setPower } from "./power.js";
import { startTracking, stopTracking } from "./tracking.js";
import { startRecording, stopRecording } from "./recording.js";
import { getState } from "./status.js";

/**
 * Every API operation is a CallableFn: `(data, ctx) => Promise<result>` —
 * the exact shape of a Firebase `onCall` handler, so migration is
 * `export const startTracking = onCall((req) => fns.startTracking(req.data, ctx))`.
 */
export interface FnContext {
  store: Store;
}

export type CallableFn<D = unknown, R = unknown> = (data: D, ctx: FnContext) => Promise<R>;

export interface FnMap {
  [name: string]: CallableFn<any, any>;
}

export const fns = {
  setPower,
  startTracking,
  stopTracking,
  startRecording,
  stopRecording,
  getState,
} satisfies FnMap;

export type { StateSnapshot };
