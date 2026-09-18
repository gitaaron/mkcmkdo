import { describe, expect, it } from "vitest";
import { MemoryStore, FnError } from "../state.js";
import { fns } from "./index.js";

const ctx = () => ({ store: new MemoryStore() }); // starts in 'idle'

describe("state machine functions", () => {
  it("full happy path idle → tracking → recording → tracking → idle", async () => {
    const c = ctx();
    expect((await fns.startTracking(undefined, c)).state).toBe("tracking");
    expect((await fns.startRecording(undefined, c)).state).toBe("recording");
    expect((await fns.stopRecording(undefined, c)).state).toBe("tracking");
    expect((await fns.stopTracking(undefined, c)).state).toBe("idle");
  });

  it("rejects recording from idle", async () => {
    const c = ctx();
    await expect(fns.startRecording(undefined, c)).rejects.toThrowError(FnError);
    await expect(fns.startRecording(undefined, c)).rejects.toMatchObject({ code: "failed-precondition" });
  });

  it("stopTracking while recording stops both", async () => {
    const c = ctx();
    await fns.startTracking(undefined, c);
    await fns.startRecording(undefined, c);
    expect((await fns.stopTracking(undefined, c)).state).toBe("idle");
  });

  it("power off is legal from every powered state, power on only from off", async () => {
    const c = ctx();
    await fns.startTracking(undefined, c);
    expect((await fns.setPower({ on: false }, c)).state).toBe("off");
    expect((await fns.setPower({ on: false }, c)).state).toBe("off"); // idempotent
    expect((await fns.setPower({ on: true }, c)).state).toBe("idle");
    expect((await fns.setPower({ on: true }, c)).state).toBe("idle"); // idempotent
  });

  it("validates setPower payload", async () => {
    await expect(fns.setPower({ on: "yes" as unknown as boolean }, ctx())).rejects.toMatchObject({
      code: "invalid-argument",
    });
  });

  it("getState returns the snapshot", async () => {
    const c = ctx();
    const snap = await fns.getState(undefined, c);
    expect(snap.state).toBe("idle");
    expect(snap.whepUrl).toBeNull();
  });
});
