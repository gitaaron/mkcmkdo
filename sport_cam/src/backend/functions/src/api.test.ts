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
async function camera(state = "awake", seenAgoMs = 0) {
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
  it("full happy path awake → tracking → recording → awake", async () => {
    for (const [fn, want] of [
      ["startTracking", "tracking"],
      ["startRecording", "recording"],
      ["stopRecording", "awake"],
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

  it("rejects recording from awake", async () => {
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
    expect((await call("stopTracking")).body.result.state).toBe("awake");
  });

  it("there is no way back from recording to tracking: stopping ends the session", async () => {
    await camera("recording");
    expect((await call("stopRecording")).body.result.state).toBe("awake");
  });

  it("setPower validates its input and is idempotent", async () => {
    expect((await call("setPower", {})).status).toBe(400);
    expect((await call("setPower", { on: false })).body.result.state).toBe("sleep");
    expect((await call("setPower", { on: false })).body.result.state).toBe("sleep");
    expect((await call("setPower", { on: true })).body.result.state).toBe("awake");
  });

  it("record from sleep goes straight to tracking, skipping awake", async () => {
    await camera("sleep");
    expect((await call("startTracking")).body.result.state).toBe("tracking");
  });

  it("sleep only wakes or records", async () => {
    await camera("sleep");
    expect((await call("startRecording")).status).toBe(412);
    expect((await call("stopTracking")).body.result.state).toBe("awake");   // = wake up
  });

  it("nothing can be asked of a camera still booting", async () => {
    await camera("off");
    expect((await call("startTracking")).status).toBe(412);
    expect((await call("setPower", { on: true })).body.result.state).toBe("off");
  });

  it("refuses commands while the camera is offline, but still reports state", async () => {
    await camera("awake", 60_000);
    const r = await call("startTracking");
    expect(r.status).toBe(412);
    expect(r.body.error.message).toMatch(/offline/);
    const s = await call("getState");
    expect(s.body.result).toMatchObject({ state: "awake", deviceOnline: false, mode: "with_uwb" });
  });

  it("passes the camera's latest warning through, for the app to toast", async () => {
    await camera("awake");
    expect((await call("getState")).body.result.warning).toBeNull();
    const at = Timestamp.fromMillis(Date.UTC(2026, 9, 27, 12));
    await cam().update({ warning: { code: "no-detector", at } });
    expect((await call("getState")).body.result.warning).toEqual({
      code: "no-detector", at: "2026-10-27T12:00:00.000Z",
    });
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
    expect(r.body.result.boxes).toEqual([]);   // a camera from before live boxes
  });

  it("getPreview returns the frame's person boxes as the players draw them", async () => {
    await cam().collection("live").doc("preview").set({
      jpeg: Buffer.from([0xff, 0xd8]), at: Timestamp.now(), size: [1280, 720],
      boxes: [{ x: 10, y: 20, w: 30, h: 60, label: "climber" }, { x: 400, y: 20, w: 30, h: 60, label: "other" }],
    });
    const r = await call("getPreview");
    expect(r.body.result.size).toEqual([1280, 720]);
    expect(r.body.result.boxes).toEqual([[10, 20, 30, 60, "climber"], [400, 20, 30, 60, "other"]]);
  });
});

describe("firestore rules", () => {
  const rest = (path: string) =>
    fetch(`http://${process.env.FIRESTORE_EMULATOR_HOST}/v1/projects/${PROJECT}/databases/(default)/documents/${path}`);

  it("doesn't let a client read a camera, even with its key: the API does that", async () => {
    await cam().collection("recordings").doc("a.mp4").set({ name: "a.mp4" });
    expect((await rest(`cameras/${key}`)).status).toBe(403);
    expect((await rest(`cameras/${key}/recordings`)).status).toBe(403);
    expect((await rest(`cameras/${key}/live/preview`)).status).toBe(403);
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
    expect(list[0].boxesUrl).toBeNull();
  });

  it("keeps the clip's person boxes beside it, for the players to draw", async () => {
    const boxes = { v: 1, size: [1280, 720], frames: [[0.5, [[10, 20, 30, 90, "climber"]]]] };
    await upload("rec_5.mp4");
    expect((await call("finalizeRecording", { name: "rec_5.mp4", bytes: clip.length, boxes: true })).status)
      .toBe(412);                                       // said it had boxes, never sent them
    await upload("rec_5.boxes.json", Buffer.from(JSON.stringify(boxes)));
    const fin = await call("finalizeRecording", { name: "rec_5.mp4", bytes: clip.length, boxes: true });
    expect(fin.status).toBe(200);
    expect(fin.body.result.boxesUrl).toMatch(/^\/api\/recordings\/rec_5\.boxes\.json\?k=/);

    const listed = (await call("getRecordings")).body.result.recordings.find((r: any) => r.name === "rec_5.mp4");
    const got = await fetch(base + listed.boxesUrl);
    expect(got.status).toBe(200);
    expect(got.headers.get("content-type")).toMatch(/application\/json/);
    expect(await got.json()).toEqual(boxes);
  });

  it("a boxes file is not a recording of its own", async () => {
    await upload("rec_6.boxes.json", Buffer.from("{}"));
    expect((await call("finalizeRecording", { name: "rec_6.boxes.json", bytes: 2 })).status).toBe(400);
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
