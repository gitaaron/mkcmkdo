/**
 * The SportCam API — one Express app, served as a single HTTPS function.
 *
 *   POST /api/call/:name             body { data } → 200 { result } | 4xx/5xx { error }
 *   GET  /api/recordings/:name?c=    the caller's own clip (302 to a signed URL; streamed under
 *                                    the emulator), or its <clip>.boxes.json (always streamed)
 *   PUT  /api/recordings/upload/:name?k=   emulator only: stand-in for the signed upload URL
 *   GET  /api/health
 *
 * Two kinds of caller:
 *
 *   the camera     names itself with its camera key, in an `X-Camera-Key`
 *                  header (or `?k=` on the emulator's upload URL), to upload
 *                  and finalize recordings
 *   a person       signed in to the phone app: `Authorization: Bearer <Firebase
 *                  ID token>` on every call (auth.ts), plus the camera key for
 *                  the calls that drive a camera
 *
 * Hosting rewrites /api/** here, so the app and the camera reach it at
 * https://<project>.web.app/api/…; under the emulator, at the functions
 * emulator's URL for `api`.
 *
 * It is the same protocol the camera's own local API speaks
 * (<build>/device/sportcam/local_api.py), so the app is one client with two
 * backends: the camera directly on its Wi-Fi, or this from anywhere.
 */
import express, { type Request, type Response } from "express";
import type { DocumentReference } from "firebase-admin/firestore";
import { createUser, listUsers, userOf, type User } from "./auth.js";
import { cameraRef, getPreview, getState, requestState, watch, type CamState } from "./camera.js";
import { FnError, HTTP_BY_CODE } from "./errors.js";
import * as rec from "./recordings.js";
import { claimRecordings, secretsOf } from "./sessions.js";

/** What a call can learn about its caller; each is checked only when asked for. */
interface Ctx {
  cam(): DocumentReference;
  user(): Promise<User>;
}

type Callable = (ctx: Ctx, data: any) => Promise<unknown>;

/** A person driving a camera: signed in first, then the camera. */
const withCam = (fn: (cam: DocumentReference, user: User, data: any) => Promise<unknown>): Callable =>
  async (ctx, data) => {
    const user = await ctx.user();
    return fn(ctx.cam(), user, data);
  };

const ask = (cam: DocumentReference, user: User, data: any, pick: (cur: CamState) => CamState | null) =>
  requestState(cam, pick, { user, secrets: secretsOf(data), pairing: data?.pairing });

const go = (to: CamState): Callable => withCam((cam, user, data) => ask(cam, user, data, () => to));

export const callables: Record<string, Callable> = {
  setPower: withCam((cam, user, data) => {
    if (typeof data?.on !== "boolean") throw new FnError("invalid-argument", "expected { on: boolean }");
    // on wakes a sleeping camera; off puts it to sleep from any awake state,
    // stopping a recording with it
    return ask(cam, user, data, (cur) =>
      data.on ? (cur === "sleep" ? "awake" : null) : cur === "sleep" || cur === "off" ? null : "sleep");
  }),
  startTracking: go("tracking"),
  stopTracking: go("awake"),
  startRecording: go("recording"),
  stopRecording: go("awake"),      // saves the clip and ends the session
  getState: withCam((cam) => getState(cam)),
  watch: withCam((cam) => watch(cam)),
  getPreview: withCam((cam) => getPreview(cam)),
  // the camera's
  createUploadUrl: async (ctx, data) => rec.createUploadUrl(ctx.cam(), data),
  finalizeRecording: async (ctx, data) => rec.finalizeRecording(ctx.cam(), data),
  // a person's own library, from every camera
  getRecordings: async (ctx) => rec.getRecordings(await ctx.user()),
  getPlaybackUrl: async (ctx, data) => rec.getPlaybackUrl(await ctx.user(), data),
  claimRecordings: async (ctx, data) => claimRecordings(await ctx.user(), data),
  // admins
  createUser: async (ctx, data) => createUser(await ctx.user(), data),
  listUsers: async (ctx) => listUsers(await ctx.user()),
};

function sendError(res: Response, err: unknown, where: string): void {
  if (err instanceof FnError) {
    res.status(HTTP_BY_CODE[err.code] ?? 500).json({ error: { code: err.code, message: err.message } });
  } else {
    console.error(`[${where}]`, err);
    res.status(500).json({ error: { code: "internal", message: "internal error" } });
  }
}

const keyOf = (req: Request) => req.header("x-camera-key") ?? (req.query.k as string | undefined);

function ctxOf(req: Request): Ctx {
  let user: Promise<User> | undefined;
  return {
    cam: () => cameraRef(keyOf(req)),
    user: () => (user ??= userOf(req)),
  };
}

export function createApp(): express.Express {
  const app = express();

  // Phones on the camera's own page (or a dev server) call cross-origin.
  app.use((req, res, next) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Camera-Key, Range");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS");
    if (req.method === "OPTIONS") {
      res.status(204).end();
      return;
    }
    next();
  });

  app.post("/api/call/:name", express.json(), async (req: Request, res: Response) => {
    const fn = callables[req.params.name!];
    if (!fn) {
      res.status(404).json({ error: { code: "not-found", message: `no function '${req.params.name}'` } });
      return;
    }
    try {
      res.json({ result: await fn(ctxOf(req), req.body?.data) });
    } catch (err) {
      sendError(res, err, `fn:${req.params.name}`);
    }
  });

  app.put(
    "/api/recordings/upload/:name",
    express.raw({ type: () => true, limit: "2gb" }),
    async (req: Request, res: Response) => {
      try {
        await rec.emulatorUpload(cameraRef(keyOf(req)), req, res);
      } catch (err) {
        sendError(res, err, "upload");
      }
    },
  );

  app.get("/api/recordings/:name", async (req: Request, res: Response) => {
    try {
      await rec.serve(await userOf(req), req, res);
    } catch (err) {
      sendError(res, err, "playback");
    }
  });

  app.get("/api/health", (_req, res) => res.json({ ok: true, backend: "firebase", emulated: rec.emulated() }));

  return app;
}
