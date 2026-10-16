import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { WebSocket } from "ws";
import { Hub } from "./hub.js";
import { MemoryStore } from "./state.js";
import { FrameBus } from "./stream.js";
import { Recordings } from "./recordings.js";

// The head can change state on its own: locking on starts recording, and
// giving up on an empty room ends the search. The server
// has to adopt those changes, or the apps show stale state and the next
// server → device message undoes them.

let close: (() => void) | null = null;
afterEach(() => close?.());

async function setup() {
  const store = new MemoryStore();
  const hub = new Hub(store, new FrameBus(),
    new Recordings(mkdtempSync(join(tmpdir(), "sportcam-hub-")), 1024 ** 3));
  const server = createServer();
  hub.attach(server);
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const { port } = server.address() as AddressInfo;
  const device = new WebSocket(`ws://127.0.0.1:${port}/ws/device`);
  await new Promise((r) => device.once("open", r));
  close = () => { device.close(); server.close(); };
  const fromServer: string[] = [];
  device.on("message", (d) => {
    const msg = JSON.parse(d.toString());
    if (msg.type === "state") fromServer.push(msg.state);
  });
  const send = (msg: object) => device.send(JSON.stringify(msg));
  const settle = () => new Promise((r) => setTimeout(r, 50));
  return { store, send, settle, fromServer };
}

describe("device-originated state", () => {
  it("adopts a state the head reports, and echoes it back unchanged", async () => {
    const { store, send, settle, fromServer } = await setup();
    send({ type: "hello", device: "head" });
    send({ type: "stateReport", state: "tracking" });     // track / record pressed, sweeping
    await settle();
    expect(store.get().state).toBe("tracking");
    send({ type: "stateReport", state: "recording" });    // locked on
    await settle();
    expect(store.get().state).toBe("recording");
    send({ type: "stateReport", state: "idle" });         // search gave up
    await settle();
    expect(store.get().state).toBe("idle");
    // whatever the server sends the head must agree with what it reported
    expect(fromServer.slice(-1)[0]).toBe("idle");
  });

  it("does not push its own state at a reconnecting head", async () => {
    const { store, send, settle, fromServer } = await setup();
    await settle();
    expect(fromServer).toEqual([]);              // nothing pushed on connect
    store.patch({ state: "tracking" });          // stale, from before a restart
    send({ type: "hello", device: "head" });
    send({ type: "stateReport", state: "recording" });  // locked on and started recording
    await settle();
    expect(store.get().state).toBe("recording");
  });

  it("ignores a report that is not a state", async () => {
    const { store, send, settle } = await setup();
    send({ type: "stateReport", state: "dancing" });
    await settle();
    expect(store.get().state).toBe("idle");
  });
});
