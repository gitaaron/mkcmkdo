/**
 * The recording library: MP4s in Cloud Storage, metadata in Firestore.
 *
 *   camera:  createUploadUrl({name})                                       → { url, method, headers }
 *            finalizeRecording({name, bytes, durationS, boxes, claimHash}) → RecordingMeta
 *   person:  getRecordings()                                               → { recordings: RecordingMeta[] }
 *            getPlaybackUrl({camera, name})                                → { url }
 *
 * Each clip is one document, `recordings/{cameraKey}:{name}`, with the
 * `claimHash` of the session it was filmed in and its `owner`: the person who
 * registered that hash (sessions.ts), or null until someone does. A person's
 * library is the clips they own, from every camera; nobody sees anyone
 * else's, and a clip nobody owns is seen by no one.
 *
 * The camera uploads straight to Cloud Storage on a V4-signed PUT URL, so the
 * video never passes through a function. Playback is a signed GET URL
 * (`getPlaybackUrl`), handed only to the owner; Cloud Storage serves range
 * requests, so phones can seek.
 *
 * Beside each clip the camera may upload `<clip>.boxes.json`: the people it
 * detected while recording, for the players to draw over the video (the
 * device's boxlog.py has the format). `boxes: true` on finalize says it did.
 * It is small and fetched by script, so it is always streamed through here,
 * to its owner: a redirect to Cloud Storage would need CORS on the bucket.
 *
 * Under the emulator there is nothing to sign with, so the upload URL points
 * back at this function (PUT /api/recordings/upload/:name), and playback
 * streams the object through it, honouring Range.
 */
import type { Request, Response } from "express";
import { Timestamp, getFirestore, type DocumentData, type DocumentReference } from "firebase-admin/firestore";
import { getStorage } from "firebase-admin/storage";
import type { User } from "./auth.js";
import { FnError } from "./errors.js";
import { HASH_RE, ownerOf } from "./sessions.js";

export interface RecordingMeta {
  name: string;
  camera: string;
  bytes: number;
  createdAt: string;
  durationS: number | null;
  url: string; // this API's playback route: needs the owner's Authorization header
  boxesUrl: string | null; // the person boxes to draw over it, if the camera sent them
}

const SIGNED_PUT_MIN = 30;
const SIGNED_GET_HOURS = 6;
const NAME_RE = /^[A-Za-z0-9._-]+\.(mp4|boxes\.json)$/;
const KEY_RE = /^[A-Za-z0-9_-]{8,64}$/;
const isBoxes = (name: string) => name.endsWith(".boxes.json");
const contentType = (name: string) => (isBoxes(name) ? "application/json" : "video/mp4");
export const boxesName = (clip: string) => clip.replace(/\.mp4$/, ".boxes.json");
const clipName = (name: string) => name.replace(/\.boxes\.json$/, ".mp4");

export const emulated = () => !!process.env.FIREBASE_STORAGE_EMULATOR_HOST || process.env.FUNCTIONS_EMULATOR === "true";

export function safeName(name: unknown): string | null {
  return typeof name === "string" && NAME_RE.test(name) && !name.includes("..") ? name : null;
}

function bucketName(): string {
  if (process.env.RECORDINGS_BUCKET) return process.env.RECORDINGS_BUCKET;
  const project = process.env.GCLOUD_PROJECT ?? process.env.GCP_PROJECT ?? "demo-sportcam";
  return `${project}-recordings`;
}

const bucket = () => getStorage().bucket(bucketName());
const objectPath = (camera: string, name: string) => `recordings/${camera}/${name}`;
const clipRef = (camera: string, name: string) => getFirestore().collection("recordings").doc(`${camera}:${name}`);
const playbackUrl = (camera: string, name: string) =>
  `/api/recordings/${name}?c=${encodeURIComponent(camera)}`;
const boxesUrl = (camera: string, clip: string, has: unknown) =>
  has === true ? playbackUrl(camera, boxesName(clip)) : null;

function meta(r: DocumentData): RecordingMeta {
  return {
    name: r.name,
    camera: r.camera,
    bytes: r.bytes,
    durationS: r.durationS ?? null,
    createdAt: (r.createdAt as Timestamp).toDate().toISOString(),
    url: playbackUrl(r.camera, r.name),
    boxesUrl: boxesUrl(r.camera, r.name, r.boxes),
  };
}

export async function createUploadUrl(cam: DocumentReference, data: any) {
  const name = safeName(data?.name);
  if (!name) throw new FnError("invalid-argument", "expected { name: '<file>.mp4' or '<file>.boxes.json' }");
  if (!(await cam.get()).exists) throw new FnError("not-found", "no camera with that key");
  const headers = { "Content-Type": contentType(name) };
  if (emulated()) {
    return { url: `/api/recordings/upload/${name}?k=${encodeURIComponent(cam.id)}`, method: "PUT", headers };
  }
  const [url] = await bucket().file(objectPath(cam.id, name)).getSignedUrl({
    version: "v4",
    action: "write",
    expires: Date.now() + SIGNED_PUT_MIN * 60_000,
    contentType: contentType(name),
  });
  return { url, method: "PUT", headers };
}

export async function finalizeRecording(cam: DocumentReference, data: any): Promise<RecordingMeta> {
  const name = safeName(data?.name);
  if (!name || isBoxes(name) || typeof data?.bytes !== "number") {
    throw new FnError("invalid-argument", "expected { name: '<file>.mp4', bytes }");
  }
  const claimHash = data.claimHash ?? null;
  if (claimHash !== null && !(typeof claimHash === "string" && HASH_RE.test(claimHash))) {
    throw new FnError("invalid-argument", "claimHash must be a SHA-256 in hex, or null");
  }
  const file = bucket().file(objectPath(cam.id, name));
  const [exists] = await file.exists();
  if (!exists) throw new FnError("failed-precondition", `recording '${name}' was never uploaded`);
  const [fileMeta] = await file.getMetadata();
  const stored = Number(fileMeta.size);
  if (stored !== data.bytes) {
    throw new FnError("failed-precondition", `size mismatch: stored ${stored}, expected ${data.bytes}`);
  }
  const boxes = data.boxes === true;
  if (boxes && !(await bucket().file(objectPath(cam.id, boxesName(name))).exists())[0]) {
    throw new FnError("failed-precondition", `boxes for '${name}' were never uploaded`);
  }
  const doc = {
    camera: cam.id, name, bytes: stored, durationS: data.durationS ?? null, boxes,
    claimHash, owner: await ownerOf(claimHash), createdAt: Timestamp.now(),
  };
  await clipRef(cam.id, name).set(doc);
  // clears the app's "uploading…" bar
  await cam.update({ upload: null });
  return meta(doc);
}

/** The caller's own clips, from every camera, newest first. */
export async function getRecordings(user: User): Promise<{ recordings: RecordingMeta[] }> {
  const snap = await getFirestore().collection("recordings")
    .where("owner", "==", user.uid).orderBy("createdAt", "desc").limit(100).get();
  return { recordings: snap.docs.map((d) => meta(d.data())) };
}

/** The clip `name` from `camera`, if `user` owns it; not-found otherwise, so others can't probe for it. */
async function ownClip(user: User, camera: unknown, name: string) {
  if (typeof camera !== "string" || !KEY_RE.test(camera)) throw new FnError("invalid-argument", "bad camera");
  const snap = await clipRef(camera, clipName(name)).get();
  if (!snap.exists || snap.get("owner") !== user.uid) throw new FnError("not-found", "no such recording");
  return bucket().file(objectPath(camera, name));
}

/**
 * Where the owner's player can fetch the clip: a signed Cloud Storage URL,
 * valid 6 h, that needs no other credentials. Under the emulator, this API's
 * own route, which needs the Authorization header.
 */
export async function getPlaybackUrl(user: User, data: any): Promise<{ url: string }> {
  const name = safeName(data?.name);
  if (!name || isBoxes(name)) throw new FnError("invalid-argument", "expected { camera, name: '<file>.mp4' }");
  const file = await ownClip(user, data?.camera, name);
  if (emulated()) return { url: playbackUrl(data.camera, name) };
  const [url] = await file.getSignedUrl({
    version: "v4",
    action: "read",
    expires: Date.now() + SIGNED_GET_HOURS * 3_600_000,
  });
  return { url };
}

/** GET /api/recordings/:name?c=<camera key> — the owner's clip, or its boxes. */
export async function serve(user: User, req: Request, res: Response): Promise<void> {
  const name = safeName(req.params.name);
  if (!name) throw new FnError("invalid-argument", "bad recording name");
  const file = await ownClip(user, req.query.c, name);
  const [exists] = await file.exists();
  if (!exists) throw new FnError("not-found", "no such recording");

  if (isBoxes(name)) {
    res.setHeader("Content-Type", "application/json");
    file.createReadStream().pipe(res);
    return;
  }
  if (!emulated()) {
    res.redirect(302, (await getPlaybackUrl(user, { camera: req.query.c, name })).url);
    return;
  }

  const [fileMeta] = await file.getMetadata();
  const size = Number(fileMeta.size);
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? "");
  res.setHeader("Accept-Ranges", "bytes");
  res.setHeader("Content-Type", "video/mp4");
  if (range && (range[1] || range[2])) {
    const start = range[1] ? Number(range[1]) : size - Number(range[2]);
    const end = range[1] && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
    if (start >= size || start > end) {
      res.status(416).setHeader("Content-Range", `bytes */${size}`).end();
      return;
    }
    res.status(206);
    res.setHeader("Content-Range", `bytes ${start}-${end}/${size}`);
    res.setHeader("Content-Length", String(end - start + 1));
    file.createReadStream({ start, end }).pipe(res);
    return;
  }
  res.setHeader("Content-Length", String(size));
  file.createReadStream().pipe(res);
}

/** PUT /api/recordings/upload/:name?k=<camera key> — the emulator's stand-in for a signed URL. */
export async function emulatorUpload(cam: DocumentReference, req: Request, res: Response): Promise<void> {
  if (!emulated()) throw new FnError("not-found", "uploads go to the signed Cloud Storage URL");
  const name = safeName(req.params.name);
  if (!name) throw new FnError("invalid-argument", "bad recording name");
  // The functions emulator has already read the body into rawBody.
  const body: Buffer = (req as any).rawBody ?? (Buffer.isBuffer(req.body) ? req.body : Buffer.alloc(0));
  await bucket().file(objectPath(cam.id, name)).save(body, { contentType: contentType(name), resumable: false });
  res.json({ result: { name, bytes: body.length } });
}
