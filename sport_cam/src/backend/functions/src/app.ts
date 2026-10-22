/**
 * The SportCam API — one Express app, served as a single HTTPS function.
 *
 *   POST /api/call/:name             body { data } → 200 { result } | 4xx/5xx { error }
 *   GET  /api/recordings/:name?k=    playback (302 to a signed URL; streamed under the emulator),
 *                                    or <clip>.boxes.json, the person boxes (always streamed)
 *   PUT  /api/recordings/upload/:name?k=   emulator only: stand-in for the signed upload URL
 *   GET  /api/health
 *
 * Every call names its camera with the camera key, in an `X-Camera-Key`
 * header (or `?k=` where a header can't be set, like a <video> src).
 * Hosting rewrites /api/** here, so the app and the camera reach it at
 * https://<project>.web.app/api/…; under the emulator, Vite proxies to it.
 *
 * It is the same protocol the camera's own local API speaks
 * (<build>/device/sportcam/local_api.py), so the apps are one client with two
 * backends: the camera directly on its Wi-Fi, or this from anywhere.
 */
import express, { type Request, type Response } from "express";
import type { DocumentReference } from "firebase-admin/firestore";
import { cameraRef, getPreview, getState, requestState, watch, type CamState } from "./camera.js";
import { FnError, HTTP_BY_CODE } from "./errors.js";
import * as rec from "./recordings.js";

type Callable = (cam: DocumentReference, data: any) => Promise<unknown>;

const go = (to: CamState | ((cur: CamState) => CamState | null)): Callable => (cam) =>
  requestState(cam, typeof to === "function" ? to : () => to);

export const callables: Record<string, Callable> = {
  setPower: (cam, data) => {
    if (typeof data?.on !== "boolean") throw new FnError("invalid-argument", "expected { on: boolean }");
    // turning off is legal from every powered state and stops a recording with it
    return requestState(cam, (cur) => (data.on ? (cur === "off" ? "idle" : null) : cur === "off" ? null : "off"));
  },
  startTracking: go("tracking"),
  stopTracking: go("idle"),
  startRecording: go("recording"),
  stopRecording: go("idle"),      // saves the clip and ends the session
  getState: (cam) => getState(cam),
  watch: (cam) => watch(cam),
  getPreview: (cam) => getPreview(cam),
  createUploadUrl: rec.createUploadUrl,
  finalizeRecording: rec.finalizeRecording,
  getRecordings: (cam) => rec.getRecordings(cam),
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

export function createApp(): express.Express {
  const app = express();

  // Phones on the camera's own page (or a dev server) call cross-origin.
  app.use((req, res, next) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-Camera-Key, Range");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS");
    if (req.method === "OPTIONS") {
      res.status(204).end();
      return;
    }
    next();
  });

  app.post("/api/call/:name", express.json(), async (req: Request, res: Response) => {
    const fn = callables[req.params.name];
    if (!fn) {
      res.status(404).json({ error: { code: "not-found", message: `no function '${req.params.name}'` } });
      return;
    }
    try {
      res.json({ result: await fn(cameraRef(keyOf(req)), req.body?.data) });
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
      await rec.serve(cameraRef(keyOf(req)), req, res);
    } catch (err) {
      sendError(res, err, "playback");
    }
  });

  app.get("/api/health", (_req, res) => res.json({ ok: true, backend: "firebase", emulated: rec.emulated() }));

  return app;
}
