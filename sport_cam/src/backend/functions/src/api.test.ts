/**
 * API tests, run against the Firestore and Storage emulators:
 *   npm test            (from the repo root, or src/backend)
 * which wraps vitest in `firebase emulators:exec`.
 */
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";

process.env.GCLOUD_PROJECT ??= "demo-sportcam";
const PROJECT = process.env.GCLOUD_PROJECT;

const { initializeApp } = await import("firebase-admin/app");
const { getFirestore, Timestamp } = await import("firebase-admin/firestore");
const { createApp } = await import("./app.js");

if (!process.env.FIRESTORE_EMULATOR_HOST) {
  throw new Error("run these through `npm test`, which starts the emulators");
}
initializeApp({ projectId: PROJECT });
const db = getFirestore();

let server: Server;
let base = "";
beforeAll(async () => {
  server = createServer(createApp());
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => server.close());

let key = "";
const cam = () => db.collection("cameras").doc(key);

/** A camera that has just checked in, in `state`. */
async function camera(state = "idle", seenAgoMs = 0) {
  key = `test-${Math.random().toString(36).slice(2, 12)}`;
  await cam().set({
    mode: "with_uwb",
    state,
    stateBy: "device",
    telemetry: { pan: 0 },
    deviceSeenAt: Timestamp.fromMillis(Date.now() - seenAgoMs),
    whepUrl: null,
    upload: null,
    warning: null,
    viewerAt: null,
    updatedAt: Timestamp.now(),
  });
}

async function call(name: string, data?: unknown, k: string | null = key) {
  const res = await fetch(`${base}/api/call/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(k ? { "X-Camera-Key": k } : {}) },
    body: JSON.stringify({ data }),
  });
  return { status: res.status, body: (await res.json()) as any };
}

beforeEach(() => camera());

describe("state machine", () => {
  it("full happy path idle → tracking → recording → tracking → idle", async () => {
    for (const [fn, want] of [
      ["startTracking", "tracking"],
      ["startRecording", "recording"],
      ["stopRecording", "tracking"],
      ["stopTracking", "idle"],
    ] as const) {
      const r = await call(fn);
      expect(r.status).toBe(200);
      expect(r.body.result.state).toBe(want);
    }
  });

  it("writes the request for the camera to adopt, marked as from the app", async () => {
    await call("startTracking");
    const d = (await cam().get()).data()!;
    expect(d.state).toBe("tracking");
    expect(d.stateBy).toBe("app");
  });

  it("rejects recording from idle", async () => {
    const r = await call("startRecording");
    expect(r.status).toBe(412);
    expect(r.body.error.code).toBe("failed-precondition");
  });

  it("asking for the state it's already in is an error, as on the camera's own API", async () => {
    await camera("recording");
    expect((await call("startRecording")).status).toBe(412);
  });

  it("stopTracking while recording stops both", async () => {
    await camera("recording");
    expect((await call("stopTracking")).body.result.state).toBe("idle");
  });

  it("setPower validates its input and is idempotent", async () => {
    expect((await call("setPower", {})).status).toBe(400);
    expect((await call("setPower", { on: false })).body.result.state).toBe("off");
    expect((await call("setPower", { on: false })).body.result.state).toBe("off");
    expect((await call("setPower", { on: true })).body.result.state).toBe("idle");
  });

  it("refuses commands while the camera is offline, but still reports state", async () => {
    await camera("idle", 60_000);
    const r = await call("startTracking");
    expect(r.status).toBe(412);
    expect(r.body.error.message).toMatch(/offline/);
    const s = await call("getState");
    expect(s.body.result).toMatchObject({ state: "idle", deviceOnline: false, mode: "with_uwb" });
  });
});

describe("camera key", () => {
  it("is required and must be well formed", async () => {
    expect((await call("getState", undefined, null)).status).toBe(400);
    expect((await call("getState", undefined, "x/y")).status).toBe(400);
  });

  it("must name a camera that has connected", async () => {
    expect((await call("getState", undefined, "never-connected-camera")).status).toBe(404);
  });

  it("unknown functions are a 404", async () => {
    expect((await call("selfDestruct")).status).toBe(404);
  });
});

describe("live view", () => {
  it("watch marks a viewer; getPreview returns the latest frame", async () => {
    expect((await call("getPreview")).body.result).toBeNull();
    await call("watch");
    expect((await cam().get()).data()!.viewerAt).toBeTruthy();
    await cam().collection("live").doc("preview").set({ jpeg: Buffer.from([0xff, 0xd8, 1, 2]), at: Timestamp.now() });
    const r = await call("getPreview");
    expect(Buffer.from(r.body.result.jpeg, "base64")).toEqual(Buffer.from([0xff, 0xd8, 1, 2]));
  });
});

describe("firestore rules", () => {
  const rest = (path: string) =>
    fetch(`http://${process.env.FIRESTORE_EMULATOR_HOST}/v1/projects/${PROJECT}/databases/(default)/documents/${path}`);

  it("lets anyone with the key read the camera, its preview and its recordings", async () => {
    await cam().collection("recordings").doc("a.mp4").set({ name: "a.mp4" });
    expect((await rest(`cameras/${key}`)).status).toBe(200);
    expect((await rest(`cameras/${key}/recordings`)).status).toBe(200);
  });

  it("never lets anyone list cameras or write", async () => {
    expect((await rest("cameras")).status).toBe(403);
    const write = await fetch(
      `http://${process.env.FIRESTORE_EMULATOR_HOST}/v1/projects/${PROJECT}/databases/(default)/documents/cameras/${key}?updateMask.fieldPaths=state`,
      { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fields: { state: { stringValue: "recording" } } }) },
    );
    expect(write.status).toBe(403);
  });
});

describe("recording library", () => {
  const clip = Buffer.from(Array.from({ length: 4096 }, (_, i) => i % 251));

  async function upload(name: string, bytes = clip) {
    const target = (await call("createUploadUrl", { name })).body.result;
    expect(target.method).toBe("PUT");
    const put = await fetch(base + target.url, { method: "PUT", headers: target.headers, body: bytes });
    expect(put.status).toBe(200);
  }

  it("upload → finalize → list → play back with Range", async () => {
    await upload("rec_1.mp4");
    const fin = await call("finalizeRecording", { name: "rec_1.mp4", bytes: clip.length, durationS: 12.5 });
    expect(fin.status).toBe(200);
    expect(fin.body.result).toMatchObject({ name: "rec_1.mp4", bytes: clip.length, durationS: 12.5 });

    const list = (await call("getRecordings")).body.result.recordings;
    expect(list.map((r: any) => r.name)).toEqual(["rec_1.mp4"]);

    const whole = await fetch(base + list[0].url);
    expect(whole.status).toBe(200);
    expect(Buffer.from(await whole.arrayBuffer())).toEqual(clip);

    const part = await fetch(base + list[0].url, { headers: { Range: "bytes=100-199" } });
    expect(part.status).toBe(206);
    expect(part.headers.get("content-range")).toBe(`bytes 100-199/${clip.length}`);
    expect(Buffer.from(await part.arrayBuffer())).toEqual(clip.subarray(100, 200));
  });

  it("finalize clears the upload progress shown in the app", async () => {
    await cam().update({ upload: { name: "rec_2.mp4", sent: 10, total: 10 } });
    await upload("rec_2.mp4");
    await call("finalizeRecording", { name: "rec_2.mp4", bytes: clip.length });
    expect((await cam().get()).data()!.upload).toBeNull();
  });

  it("rejects a finalize that doesn't match what was stored", async () => {
    expect((await call("finalizeRecording", { name: "never.mp4", bytes: 1 })).status).toBe(412);
    await upload("rec_3.mp4");
    const r = await call("finalizeRecording", { name: "rec_3.mp4", bytes: clip.length + 1 });
    expect(r.status).toBe(412);
    expect(r.body.error.message).toMatch(/size mismatch/);
  });

  it("rejects unsafe names", async () => {
    expect((await call("createUploadUrl", { name: "../etc/passwd" })).status).toBe(400);
    expect((await call("createUploadUrl", { name: "clip.mov" })).status).toBe(400);
  });

  it("keeps each camera's recordings separate", async () => {
    await upload("rec_4.mp4");
    await call("finalizeRecording", { name: "rec_4.mp4", bytes: clip.length });
    await camera();
    expect((await call("getRecordings")).body.result.recordings).toEqual([]);
    expect((await fetch(`${base}/api/recordings/rec_4.mp4?k=${key}`)).status).toBe(404);
  });
});
