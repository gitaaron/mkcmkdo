import { transition, type StateSnapshot } from "../state.js";
import type { CallableFn } from "./index.js";

export const startRecording: CallableFn<void, StateSnapshot> = async (_data, ctx) => {
  return transition(ctx.store, "recording");
};

export const stopRecording: CallableFn<void, StateSnapshot> = async (_data, ctx) => {
  return transition(ctx.store, "tracking");
};
