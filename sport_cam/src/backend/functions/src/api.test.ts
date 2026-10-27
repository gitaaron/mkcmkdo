/**
 * API tests, run against the Firestore, Storage and Authentication emulators:
 *   npm test            (from the repo root, or src/backend)
 * which wraps vitest in `firebase emulators:exec`.
 */
import { createHash } from "node:crypto";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";

process.env.GCLOUD_PROJECT ??= "demo-sportcam";
const PROJECT = process.env.GCLOUD_PROJECT;

const { initializeApp } = await import("firebase-admin/app");
const { getAuth } = await import("firebase-admin/auth");
const { getFirestore, Timestamp } = await import("firebase-admin/firestore");
const { createApp } = await import("./app.js");

if (!process.env.FIRESTORE_EMULATOR_HOST || !process.env.FIREBASE_AUTH_EMULATOR_HOST) {
  throw new Error("run these through `npm test`, which starts the emulators");
}
initializeApp({ projectId: PROJECT });
const db = getFirestore();
const sha256 = (s: string) => createHash("sha256").update(s).digest("hex");

/** Sign in as the app does, against the Authentication emulator: an ID token. */
async function signIn(email: string, password: string): Promise<string> {
  const res = await fetch(
    `http://${process.env.FIREBASE_AUTH_EMULATOR_HOST}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password, returnSecureToken: true }) },
  );
  const body = (await res.json()) as any;
  if (!res.ok) throw new Error(`sign-in failed: ${JSON.stringify(body)}`);
  return body.idToken;
}

const PASSWORD = "correct horse";
const people = new Map<string, { uid: string; token: string }>();

/** A person who can sign in, made (once) by the admin SDK; `admin` gives them the claim. */
async function person(name: string, admin = false) {
  const email = `${name}@test.sportcam`;
  if (!people.has(email)) {
    const auth = getAuth();
    const u = await auth.getUserByEmail(email).catch(() => auth.createUser({ email, password: PASSWORD }));
    if (admin) await auth.setCustomUserClaims(u.uid, { admin: true });
    people.set(email, { uid: u.uid, token: await signIn(email, PASSWORD) });
  }
  return people.get(email)!;
}

let server: Server;
let base = "";
beforeAll(async () => {
  server = createServer(createApp());
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => server.close());

let key = "";
let token = "";          // the person calling: alice, unless a test says otherwise
const cam = () => db.collection("cameras").doc(key);

/** A camera that has just checked in, in `state`. */
async function camera(state = "awake", seenAgoMs = 0) {
  key = `test-${Math.random().toString(36).slice(2, 12)}`;
  await cam().set({
    mode: "with_uwb",
    state,
    stateBy: "device",
    sessionHash: null,
    telemetry: { pan: 0 },
    deviceSeenAt: Timestamp.fromMillis(Date.now() - seenAgoMs),
    whepUrl: null,
    upload: null,
    warning: null,
    viewerAt: null,
    updatedAt: Timestamp.now(),
  });
}

async function call(name: string, data?: unknown, k: string | null = key, as: string | null = token) {
  const res = await fetch(`${base}/api/call/${name}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(k ? { "X-Camera-Key": k } : {}),
      ...(as ? { Authorization: `Bearer ${as}` } : {}),
    },
    body: JSON.stringify({ data }),
  });
  return { status: res.status, body: (await res.json()) as any };
}

/** As the camera calls: its key, nobody signed in. */
const camCall = (name: string, data?: unknown) => call(name, data, key, null);

beforeEach(async () => {
  token = (await person("alice")).token;
  await camera();
});

describe("state machine", () => {
  it("full happy path awake → tracking → recording → awake", async () => {
    const start = await call("startTracking");
    expect(start.body.result.state).toBe("tracking");
    const secrets = [start.body.result.sessionSecret];
    for (const [fn, want] of [
      ["startRecording", "recording"],
      ["stopRecording", "awake"],
    ] as const) {
      const r = await call(fn, { secrets });
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

describe("who started it stops it", () => {
  let bob = "";
  beforeEach(async () => {
    bob = (await person("bob")).token;
  });

  it("starting a session hands its secret to the starter alone, and registers it to them", async () => {
    const r = (await call("startTracking")).body.result;
    expect(r.sessionSecret).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(r.sessionHash).toBe(sha256(r.sessionSecret));
    expect((await cam().get()).data()!.sessionHash).toBe(r.sessionHash);
    expect((await db.collection("claims").doc(r.sessionHash).get()).data()!.owner).toBe((await person("alice")).uid);
    const seen = (await call("getState", undefined, key, bob)).body.result;
    expect(seen.sessionHash).toBe(r.sessionHash);       // everyone sees whose it is…
    expect(seen.sessionSecret).toBeUndefined();         // …but not the secret
  });

  it("nobody else can stop, sleep, advance or end it", async () => {
    const { sessionSecret } = (await call("startTracking")).body.result;
    for (const [fn, data] of [
      ["startRecording", {}], ["stopTracking", {}], ["setPower", { on: false }],
    ] as const) {
      const r = await call(fn, { ...data, secrets: ["not-the-secret-at-all"] }, key, bob);
      expect(r.status, fn).toBe(403);
      expect(r.body.error.code).toBe("permission-denied");
    }
    expect((await call("startRecording", { secrets: [sessionSecret] })).body.result.state).toBe("recording");
    expect((await call("stopRecording", {}, key, bob)).status).toBe(403);
    expect((await call("stopRecording")).status).toBe(403);   // alice too, without the secret
    // anyone holding the secret may (it is alice's phone); one among others is enough
    const stop = await call("stopRecording", { secrets: ["another-secret-xxxxxx", sessionSecret] });
    expect(stop.body.result).toMatchObject({ state: "awake", sessionHash: null });
    expect((await cam().get()).data()!.sessionHash).toBeNull();
  });

  it("once it is over, anyone can start the next", async () => {
    const { sessionSecret } = (await call("startTracking")).body.result;
    await call("stopTracking", { secrets: [sessionSecret] });
    const next = await call("startTracking", {}, key, bob);
    expect(next.status).toBe(200);
    expect(next.body.result.sessionSecret).not.toBe(sessionSecret);
  });

  it("a session nobody owns (an unpaired tag's) can be stopped by anyone", async () => {
    await camera("recording");
    expect((await call("stopRecording", {}, key, bob)).body.result.state).toBe("awake");
  });

  it("a paired tag's secret starts the session as its own", async () => {
    const pairing = "a-tag-pairing-secret-0123456789";
    const r = (await call("startTracking", { pairing })).body.result;
    expect(r.sessionSecret).toBe(pairing);
    expect(r.sessionHash).toBe(sha256(pairing));
    await call("stopTracking", { secrets: [pairing] });
    const stolen = await call("startTracking", { pairing }, key, bob);
    expect(stolen.status).toBe(403);
    expect(stolen.body.error.message).toMatch(/paired to someone else/);
  });
});

describe("signing in", () => {
  it("driving a camera needs a signed-in person", async () => {
    expect((await call("getState", undefined, key, null)).status).toBe(401);
    expect((await call("startTracking", undefined, key, "not-a-token")).status).toBe(401);
    expect((await call("getRecordings", undefined, null, null)).status).toBe(401);
  });

  it("the camera uploads with its key alone", async () => {
    expect((await camCall("createUploadUrl", { name: "rec_k.mp4" })).status).toBe(200);
  });
});

describe("admin", () => {
  it("only an admin can add people or list them", async () => {
    expect((await call("createUser", { email: "x@test.sportcam", password: PASSWORD })).status).toBe(403);
    expect((await call("listUsers")).status).toBe(403);
  });

  it("adds a person who can then sign in, and refuses duplicates and short passwords", async () => {
    const admin = (await person("root", true)).token;
    const email = `new-${Date.now()}@test.sportcam`;
    expect((await call("createUser", { email, password: "short" }, null, admin)).status).toBe(400);
    expect((await call("createUser", { email: "nope", password: PASSWORD }, null, admin)).status).toBe(400);
    const made = await call("createUser", { email: email.toUpperCase(), password: PASSWORD }, null, admin);
    expect(made.status).toBe(200);
    expect(made.body.result).toMatchObject({ email, admin: false });
    expect(await signIn(email, PASSWORD)).toBeTruthy();
    expect((await call("createUser", { email, password: PASSWORD }, null, admin)).status).toBe(409);
    const listed = (await call("listUsers", undefined, null, admin)).body.result.users;
    expect(listed.find((u: any) => u.email === email)).toMatchObject({ admin: false });
    expect(listed.find((u: any) => u.email === "root@test.sportcam")).toMatchObject({ admin: true });
  });

  it("can make another admin", async () => {
    const admin = (await person("root", true)).token;
    const email = `admin-${Date.now()}@test.sportcam`;
    await call("createUser", { email, password: PASSWORD, admin: true }, null, admin);
    const theirs = await signIn(email, PASSWORD);
    expect((await call("listUsers", undefined, null, theirs)).status).toBe(200);
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
    expect((await rest("recordings")).status).toBe(403);
    expect((await rest("claims")).status).toBe(403);
    const write = await fetch(
      `http://${process.env.FIRESTORE_EMULATOR_HOST}/v1/projects/${PROJECT}/databases/(default)/documents/cameras/${key}?updateMask.fieldPaths=state`,
      { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fields: { state: { stringValue: "recording" } } }) },
    );
    expect(write.status).toBe(403);
  });
});

describe("recording library", () => {
  const clip = Buffer.from(Array.from({ length: 4096 }, (_, i) => i % 251));
  const auth = (as: string) => ({ Authorization: `Bearer ${as}` });

  async function upload(name: string, bytes = clip) {
    const target = (await camCall("createUploadUrl", { name })).body.result;
    expect(target.method).toBe("PUT");
    const put = await fetch(base + target.url, { method: "PUT", headers: target.headers, body: bytes });
    expect(put.status).toBe(200);
  }

  /** A session alice starts and stops on this camera: its secret, and its hash for the clip. */
  async function session() {
    const { sessionSecret } = (await call("startTracking")).body.result;
    await call("stopTracking", { secrets: [sessionSecret] });
    return { secret: sessionSecret as string, hash: sha256(sessionSecret) };
  }

  const library = async (as = token) => (await call("getRecordings", undefined, null, as)).body.result.recordings;

  it("upload → finalize → the owner's library → play back with Range", async () => {
    const { hash } = await session();
    await upload("rec_1.mp4");
    const fin = await camCall("finalizeRecording", { name: "rec_1.mp4", bytes: clip.length, durationS: 12.5, claimHash: hash });
    expect(fin.status).toBe(200);
    expect(fin.body.result).toMatchObject({ name: "rec_1.mp4", camera: key, bytes: clip.length, durationS: 12.5 });

    const list = (await library()).filter((r: any) => r.camera === key);
    expect(list.map((r: any) => r.name)).toEqual(["rec_1.mp4"]);

    const whole = await fetch(base + list[0].url, { headers: auth(token) });
    expect(whole.status).toBe(200);
    expect(Buffer.from(await whole.arrayBuffer())).toEqual(clip);

    const part = await fetch(base + list[0].url, { headers: { ...auth(token), Range: "bytes=100-199" } });
    expect(part.status).toBe(206);
    expect(part.headers.get("content-range")).toBe(`bytes 100-199/${clip.length}`);
    expect(Buffer.from(await part.arrayBuffer())).toEqual(clip.subarray(100, 200));
    expect(list[0].boxesUrl).toBeNull();

    const play = await call("getPlaybackUrl", { camera: key, name: "rec_1.mp4" });
    expect(play.body.result.url).toBe(list[0].url);       // emulator: through the API
  });

  it("nobody else can list, play or fetch the URL of someone's clip", async () => {
    const bob = (await person("bob")).token;
    const { hash } = await session();
    await upload("rec_7.mp4");
    await camCall("finalizeRecording", { name: "rec_7.mp4", bytes: clip.length, claimHash: hash });
    expect((await library(bob)).some((r: any) => r.camera === key)).toBe(false);
    const url = `${base}/api/recordings/rec_7.mp4?c=${key}`;
    expect((await fetch(url)).status).toBe(401);
    expect((await fetch(url, { headers: auth(bob) })).status).toBe(404);
    expect((await call("getPlaybackUrl", { camera: key, name: "rec_7.mp4" }, null, bob)).status).toBe(404);
  });

  it("a clip uploaded before its secret is claimed waits, unseen, for its owner", async () => {
    const secret = "secret-made-on-the-camera-0123";       // a session started on the camera's Wi-Fi
    await upload("rec_8.mp4");
    await camCall("finalizeRecording", { name: "rec_8.mp4", bytes: clip.length, claimHash: sha256(secret) });
    expect((await library()).some((r: any) => r.camera === key)).toBe(false);

    const bob = (await person("bob")).token;
    expect((await call("claimRecordings", { secrets: [secret] })).body.result).toEqual({ claimed: 1, refused: 0 });
    expect((await library()).filter((r: any) => r.camera === key).map((r: any) => r.name)).toEqual(["rec_8.mp4"]);
    expect((await call("claimRecordings", { secrets: [secret] })).body.result).toEqual({ claimed: 0, refused: 0 });
    expect((await call("claimRecordings", { secrets: [secret] }, null, bob)).body.result).toEqual({ claimed: 0, refused: 1 });

    // and the next clip under the same secret goes straight to alice
    await upload("rec_9.mp4");
    await camCall("finalizeRecording", { name: "rec_9.mp4", bytes: clip.length, claimHash: sha256(secret) });
    expect((await library()).filter((r: any) => r.camera === key).map((r: any) => r.name)).toEqual(["rec_9.mp4", "rec_8.mp4"]);
  });

  it("a clip from a session nobody owns is seen by no one", async () => {
    await upload("rec_0.mp4");
    const fin = await camCall("finalizeRecording", { name: "rec_0.mp4", bytes: clip.length });
    expect(fin.status).toBe(200);
    expect((await db.collection("recordings").doc(`${key}:rec_0.mp4`).get()).data()!.owner).toBeNull();
    expect((await library()).some((r: any) => r.camera === key)).toBe(false);
  });

  it("keeps the clip's person boxes beside it, for the owner's player to draw", async () => {
    const { hash } = await session();
    const boxes = { v: 1, size: [1280, 720], frames: [[0.5, [[10, 20, 30, 90, "climber"]]]] };
    await upload("rec_5.mp4");
    expect((await camCall("finalizeRecording", { name: "rec_5.mp4", bytes: clip.length, boxes: true, claimHash: hash })).status)
      .toBe(412);                                       // said it had boxes, never sent them
    await upload("rec_5.boxes.json", Buffer.from(JSON.stringify(boxes)));
    const fin = await camCall("finalizeRecording", { name: "rec_5.mp4", bytes: clip.length, boxes: true, claimHash: hash });
    expect(fin.status).toBe(200);
    expect(fin.body.result.boxesUrl).toMatch(/^\/api\/recordings\/rec_5\.boxes\.json\?c=/);

    const listed = (await library()).find((r: any) => r.camera === key && r.name === "rec_5.mp4");
    const got = await fetch(base + listed.boxesUrl, { headers: auth(token) });
    expect(got.status).toBe(200);
    expect(got.headers.get("content-type")).toMatch(/application\/json/);
    expect(await got.json()).toEqual(boxes);
    const bob = (await person("bob")).token;
    expect((await fetch(base + listed.boxesUrl, { headers: auth(bob) })).status).toBe(404);
  });

  it("a boxes file is not a recording of its own", async () => {
    await upload("rec_6.boxes.json", Buffer.from("{}"));
    expect((await camCall("finalizeRecording", { name: "rec_6.boxes.json", bytes: 2 })).status).toBe(400);
  });

  it("finalize clears the upload progress shown in the app", async () => {
    await cam().update({ upload: { name: "rec_2.mp4", sent: 10, total: 10 } });
    await upload("rec_2.mp4");
    await camCall("finalizeRecording", { name: "rec_2.mp4", bytes: clip.length });
    expect((await cam().get()).data()!.upload).toBeNull();
  });

  it("rejects a finalize that doesn't match what was stored, or a malformed claim hash", async () => {
    expect((await camCall("finalizeRecording", { name: "never.mp4", bytes: 1 })).status).toBe(412);
    await upload("rec_3.mp4");
    const r = await camCall("finalizeRecording", { name: "rec_3.mp4", bytes: clip.length + 1 });
    expect(r.status).toBe(412);
    expect(r.body.error.message).toMatch(/size mismatch/);
    expect((await camCall("finalizeRecording", { name: "rec_3.mp4", bytes: clip.length, claimHash: "abc" })).status).toBe(400);
  });

  it("rejects unsafe names", async () => {
    expect((await camCall("createUploadUrl", { name: "../etc/passwd" })).status).toBe(400);
    expect((await camCall("createUploadUrl", { name: "clip.mov" })).status).toBe(400);
  });

  it("keeps clips of the same name from two cameras apart", async () => {
    const first = key;
    const a = await session();
    await upload("rec_4.mp4");
    await camCall("finalizeRecording", { name: "rec_4.mp4", bytes: clip.length, claimHash: a.hash });
    await camera();
    const b = await session();
    await upload("rec_4.mp4", clip.subarray(0, 100));
    await camCall("finalizeRecording", { name: "rec_4.mp4", bytes: 100, claimHash: b.hash });
    const mine = (await library()).filter((r: any) => r.name === "rec_4.mp4" && [first, key].includes(r.camera));
    expect(mine.map((r: any) => [r.camera, r.bytes]).sort()).toEqual([[first, clip.length], [key, 100]].sort());
  });
});
