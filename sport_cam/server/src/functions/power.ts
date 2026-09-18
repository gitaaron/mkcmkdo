import { FnError, transition, type StateSnapshot } from "../state.js";
import type { CallableFn } from "./index.js";

export const setPower: CallableFn<{ on: boolean }, StateSnapshot> = async (data, ctx) => {
  if (typeof data?.on !== "boolean") {
    throw new FnError("invalid-argument", "expected { on: boolean }");
  }
  const current = ctx.store.get().state;
  if (data.on) {
    return current === "off" ? transition(ctx.store, "idle") : ctx.store.get();
  }
  // Turning off is legal from every powered state; stops recording implicitly.
  return current === "off" ? ctx.store.get() : transition(ctx.store, "off");
};
