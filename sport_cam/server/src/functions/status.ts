import type { StateSnapshot } from "../state.js";
import type { CallableFn } from "./index.js";

export const getState: CallableFn<void, StateSnapshot> = async (_data, ctx) => {
  return ctx.store.get();
};
