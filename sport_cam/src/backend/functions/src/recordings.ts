/**
 * The recording library: MP4s in Cloud Storage, metadata in Firestore.
 *
 *   createUploadUrl({name})                            → { url, method, headers }
 *   finalizeRecording({name, bytes, durationS, boxes}) → RecordingMeta
 *   getRecordings()                                    → { recordings: RecordingMeta[] }
 *
 * The camera uploads straight to Cloud Storage on a V4-signed PUT URL, so the
 * video never passes through a function. Playback is a 302 to a signed GET
 * URL; Cloud Storage serves range requests, so phones can seek.
 *
 * Beside each clip the camera may upload `<clip>.boxes.json`: the people it
 * detected while recording, for the players to draw over the video (the
 * device's boxlog.py has the format). `boxes: true` on finalize says it did.
 * It is small and fetched by script, so it is always streamed through here:
 * a redirect to Cloud Storage would need CORS on the bucket.
 *
 * Under the emulator there is nothing to sign with, so the upload URL points
 * back at this function (PUT /api/recordings/upload/:name), and playback
 * streams the object through it, honouring Range.
 */
import type { Request, Response } from "express";
import { Timestamp, type DocumentReference } from "firebase-admin/firestore";
import { getStorage } from "firebase-admin/storage";
import { FnError } from "./errors.js";

export interface RecordingMeta {
  name: string;
  bytes: number;
  createdAt: string;
  durationS: number | null;
  url: string; // app-facing playback URL (range-capable)
  boxesUrl: string | null; // the person boxes to draw over it, if the camera sent them
}

const SIGNED_PUT_MIN = 30;
const SIGNED_GET_HOURS = 6;
const NAME_RE = /^[A-Za-z0-9._-]+\.(mp4|boxes\.json)$/;
const isBoxes = (name: string) => name.endsWith(".boxes.json");
const contentType = (name: string) => (isBoxes(name) ? "application/json" : "video/mp4");
export const boxesName = (clip: string) => clip.replace(/\.mp4$/, ".boxes.json");

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
const objectPath = (cam: DocumentReference, name: string) => `recordings/${cam.id}/${name}`;
const playbackUrl = (cam: DocumentReference, name: string) =>
  `/api/recordings/${name}?k=${encodeURIComponent(cam.id)}`;
const boxesUrl = (cam: DocumentReference, clip: string, has: unknown) =>
  has === true ? playbackUrl(cam, boxesName(clip)) : null;

export async function createUploadUrl(cam: DocumentReference, data: any) {
  const name = safeName(data?.name);
  if (!name) throw new FnError("invalid-argument", "expected { name: '<file>.mp4' or '<file>.boxes.json' }");
  if (!(await cam.get()).exists) throw new FnError("not-found", "no camera with that key");
  const headers = { "Content-Type": contentType(name) };
  if (emulated()) {
    return { url: `/api/recordings/upload/${name}?k=${encodeURIComponent(cam.id)}`, method: "PUT", headers };
  }
  const [url] = await bucket().file(objectPath(cam, name)).getSignedUrl({
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
  const file = bucket().file(objectPath(cam, name));
  const [exists] = await file.exists();
  if (!exists) throw new FnError("failed-precondition", `recording '${name}' was never uploaded`);
  const [meta] = await file.getMetadata();
  const stored = Number(meta.size);
  if (stored !== data.bytes) {
    throw new FnError("failed-precondition", `size mismatch: stored ${stored}, expected ${data.bytes}`);
  }
  const boxes = data.boxes === true;
  if (boxes && !(await bucket().file(objectPath(cam, boxesName(name))).exists())[0]) {
    throw new FnError("failed-precondition", `boxes for '${name}' were never uploaded`);
  }
  const doc = { name, bytes: stored, durationS: data.durationS ?? null, boxes, createdAt: Timestamp.now() };
  await cam.collection("recordings").doc(name).set(doc);
  // clears the app's "uploading…" bar
  await cam.update({ upload: null });
  return {
    name, bytes: stored, durationS: doc.durationS,
    createdAt: doc.createdAt.toDate().toISOString(),
    url: playbackUrl(cam, name), boxesUrl: boxesUrl(cam, name, boxes),
  };
}

export async function getRecordings(cam: DocumentReference): Promise<{ recordings: RecordingMeta[] }> {
  const snap = await cam.collection("recordings").orderBy("createdAt", "desc").limit(100).get();
  return {
    recordings: snap.docs.map((d) => {
      const r = d.data();
      return {
        name: r.name,
        bytes: r.bytes,
        durationS: r.durationS ?? null,
        createdAt: (r.createdAt as Timestamp).toDate().toISOString(),
        url: playbackUrl(cam, r.name),
        boxesUrl: boxesUrl(cam, r.name, r.boxes),
      };
    }),
  };
}

/** GET /api/recordings/:name?k=<camera key> — playback, or a clip's boxes. */
export async function serve(cam: DocumentReference, req: Request, res: Response): Promise<void> {
  const name = safeName(req.params.name);
  if (!name) throw new FnError("invalid-argument", "bad recording name");
  const file = bucket().file(objectPath(cam, name));
  const [exists] = await file.exists();
  if (!exists) throw new FnError("not-found", "no such recording");

  if (isBoxes(name)) {
    res.setHeader("Content-Type", "application/json");
    file.createReadStream().pipe(res);
    return;
  }
  if (!emulated()) {
    const [url] = await file.getSignedUrl({
      version: "v4",
      action: "read",
      expires: Date.now() + SIGNED_GET_HOURS * 3_600_000,
    });
    res.redirect(302, url);
    return;
  }

  const [meta] = await file.getMetadata();
  const size = Number(meta.size);
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
  await bucket().file(objectPath(cam, name)).save(body, { contentType: contentType(name), resumable: false });
  res.json({ result: { name, bytes: body.length } });
}
