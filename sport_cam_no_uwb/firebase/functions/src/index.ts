/**
 * SportCam cloud backend — one HTTPS function serving the exact same
 * callable protocol as the home server (`POST /api/call/:name`), so the
 * device uploader and the web app work unchanged against either.
 *
 * Cloud scope = the recording library (the "gym workflow"):
 *   createUploadUrl   → V4-signed Cloud Storage PUT URL
 *   finalizeRecording → verify object, write Firestore metadata
 *   getRecordings     → Firestore list + fresh signed GET URLs
 *   GET /api/recordings/:name → 302 to a signed URL (so <video> src works)
 *
 * Live control/streaming stays on the LAN server — those callables return
 * failed-precondition here (documented in docs/08-cloud-gym-workflow.md).
 */
import express, { type Request, type Response } from "express";
import { initializeApp } from "firebase-admin/app";
import { getFirestore, Timestamp } from "firebase-admin/firestore";
import { getStorage } from "firebase-admin/storage";
import { onRequest } from "firebase-functions/v2/https";

initializeApp();

const REGION = "us-central1";
const BUCKET =
  process.env.RECORDINGS_BUCKET ?? `${process.env.GCLOUD_PROJECT}-recordings`;
const SIGNED_PUT_MIN = 30;
const SIGNED_GET_HOURS = 6;

const NAME_RE = /^[A-Za-z0-9._-]+\.mp4$/;
const safeName = (n: unknown): string | null =>
  typeof n === "string" && NAME_RE.test(n) && !n.includes("..") ? n : null;

class FnError extends Error {
  constructor(public code: string, message: string) {
    super(message);
  }
}
const HTTP_BY_CODE: Record<string, number> = {
  "invalid-argument": 400,
  "not-found": 404,
  "failed-precondition": 412,
};

const bucket = () => getStorage().bucket(BUCKET);
const col = () => getFirestore().collection("recordings");
const objectPath = (name: string) => `recordings/${name}`;

// ---- callables -------------------------------------------------------------

type Fn = (data: any) => Promise<unknown>;

const fns: Record<string, Fn> = {
  async createUploadUrl(data) {
    const name = safeName(data?.name);
    if (!name) throw new FnError("invalid-argument", "expected { name: '<file>.mp4' }");
    const [url] = await bucket().file(objectPath(name)).getSignedUrl({
      version: "v4",
      action: "write",
      expires: Date.now() + SIGNED_PUT_MIN * 60_000,
      contentType: "video/mp4",
    });
    return { url, method: "PUT", headers: { "Content-Type": "video/mp4" } };
  },

  async finalizeRecording(data) {
    const name = safeName(data?.name);
    if (!name || typeof data?.bytes !== "number") {
      throw new FnError("invalid-argument", "expected { name, bytes }");
    }
    const file = bucket().file(objectPath(name));
    const [exists] = await file.exists();
    if (!exists) throw new FnError("failed-precondition", `'${name}' was never uploaded`);
    const [meta] = await file.getMetadata();
    const stored = Number(meta.size);
    if (stored !== data.bytes) {
      throw new FnError("failed-precondition", `size mismatch: stored ${stored}, expected ${data.bytes}`);
    }
    const doc = {
      name,
      bytes: stored,
      durationS: data.durationS ?? null,
      createdAt: Timestamp.now(),
    };
    await col().doc(name).set(doc);
    return { ...doc, createdAt: doc.createdAt.toDate().toISOString(), url: `/api/recordings/${name}` };
  },

  async getRecordings() {
    const snap = await col().orderBy("createdAt", "desc").limit(100).get();
    return {
      recordings: snap.docs.map((d) => {
        const r = d.data();
        return {
          name: r.name,
          bytes: r.bytes,
          durationS: r.durationS ?? null,
          createdAt: (r.createdAt as Timestamp).toDate().toISOString(),
          url: `/api/recordings/${r.name}`,
        };
      }),
    };
  },
};

const LIBRARY_ONLY_MSG =
  "cloud deployment is library-only; live camera control runs on the LAN server";

// ---- express app (same adapter shape as server/src/lib/adapters.ts) --------

const app = express();
app.use(express.json());

app.post("/api/call/:name", async (req: Request, res: Response) => {
  const fn = fns[req.params.name];
  if (!fn) {
    const known = ["setPower", "startTracking", "stopTracking", "startRecording", "stopRecording", "getState"];
    if (known.includes(req.params.name)) {
      res.status(412).json({ error: { code: "failed-precondition", message: LIBRARY_ONLY_MSG } });
    } else {
      res.status(404).json({ error: { code: "not-found", message: `no function '${req.params.name}'` } });
    }
    return;
  }
  try {
    res.json({ result: await fn(req.body?.data) });
  } catch (err) {
    if (err instanceof FnError) {
      res.status(HTTP_BY_CODE[err.code] ?? 500).json({ error: { code: err.code, message: err.message } });
    } else {
      console.error(`[fn:${req.params.name}]`, err);
      res.status(500).json({ error: { code: "internal", message: "internal error" } });
    }
  }
});

// Playback: redirect to a fresh signed GET URL. <video> follows the redirect
// and GCS serves range requests, so seeking works on phones.
app.get("/api/recordings/:name", async (req: Request, res: Response) => {
  const name = safeName(req.params.name);
  if (!name) {
    res.status(400).json({ error: { code: "invalid-argument", message: "bad name" } });
    return;
  }
  const file = bucket().file(objectPath(name));
  const [exists] = await file.exists();
  if (!exists) {
    res.status(404).json({ error: { code: "not-found", message: "no such recording" } });
    return;
  }
  const [url] = await file.getSignedUrl({
    version: "v4",
    action: "read",
    expires: Date.now() + SIGNED_GET_HOURS * 3_600_000,
  });
  res.redirect(302, url);
});

app.get("/api/health", (_req, res) => res.json({ ok: true, backend: "firebase" }));

export const api = onRequest({ region: REGION, memory: "256MiB", maxInstances: 4 }, app);
