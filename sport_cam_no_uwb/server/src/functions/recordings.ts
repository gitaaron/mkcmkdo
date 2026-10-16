import { FnError } from "../state.js";
import { safeName, type RecordingMeta } from "../recordings.js";
import type { CallableFn } from "./index.js";

/**
 * Recording-library callables. Identical protocol on the local server and the
 * Firebase deployment (firebase/functions) — the device and app never care
 * which one they're talking to:
 *
 *   createUploadUrl({name})               → { url, method, headers }
 *   finalizeRecording({name, bytes, durationS}) → RecordingMeta
 *   getRecordings()                       → { recordings: RecordingMeta[] }
 *
 * Locally the upload URL is our own PUT endpoint; on Firebase it is a
 * V4-signed Cloud Storage URL.
 */
export const createUploadUrl: CallableFn<
  { name: string },
  { url: string; method: string; headers: Record<string, string> }
> = async (data, _ctx) => {
  const name = safeName(data?.name);
  if (!name) throw new FnError("invalid-argument", "expected { name: '<file>.mp4' }");
  return {
    url: `/api/recordings/upload/${name}`,
    method: "PUT",
    headers: { "Content-Type": "video/mp4" },
  };
};

export const finalizeRecording: CallableFn<
  { name: string; bytes: number; durationS?: number | null },
  RecordingMeta
> = async (data, ctx) => {
  const name = safeName(data?.name);
  if (!name || typeof data?.bytes !== "number") {
    throw new FnError("invalid-argument", "expected { name, bytes }");
  }
  if (!ctx.recordings.exists(name)) {
    throw new FnError("failed-precondition", `recording '${name}' was never uploaded`);
  }
  const stored = ctx.recordings.size(name);
  if (stored !== data.bytes) {
    throw new FnError("failed-precondition", `size mismatch: stored ${stored}, expected ${data.bytes}`);
  }
  return ctx.recordings.finalize(name, data.durationS ?? null);
};

export const getRecordings: CallableFn<void, { recordings: RecordingMeta[] }> = async (_d, ctx) => {
  return { recordings: ctx.recordings.list() };
};
