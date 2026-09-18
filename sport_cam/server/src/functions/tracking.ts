import { transition, type StateSnapshot } from "../state.js";
import type { CallableFn } from "./index.js";

export const startTracking: CallableFn<void, StateSnapshot> = async (_data, ctx) => {
  return transition(ctx.store, "tracking");
};

/** Stops tracking; if currently recording this stops (and saves) that too. */
export const stopTracking: CallableFn<void, StateSnapshot> = async (_data, ctx) => {
  return transition(ctx.store, "idle");
};
