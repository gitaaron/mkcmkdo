import { cameraKey } from "./cameraKey";

export type CamState = "off" | "idle" | "tracking" | "recording";

/** Which hardware build the camera is — the camera reports it. */
export type TrackingMode = "with_uwb" | "without_uwb";

export interface Telemetry {
  pan?: number;
  tilt?: number;
  zoomMm?: number;
  dist?: number | null;
  phase?: "person-in-frame" | "no-person-in-frame" | "acquiring" | "acquired" | null;
  centred?: number;  // consecutive centred detections toward the lock; the app beeps per step up
  searching?: boolean;  // in SEARCH (turning to the tag / sweeping); the app pings every 3 s
  acquireStalled?: boolean;
  battery?: number;
}

export interface StateSnapshot {
  mode?: TrackingMode;   // absent until the camera first connects → treated as with_uwb
  state: CamState;
  telemetry: Telemetry;
  deviceOnline: boolean;
  whepUrl: string | null;
  updatedAt: string;
}

export interface RecordingMeta {
  name: string;
  bytes: number;
  createdAt: string;
  durationS: number | null;
  url: string;
}

/**
 * Single entry point for API calls: the `api` function on Firebase (same
 * origin through Hosting's /api rewrite; proxied to the emulator in dev).
 */
export async function call<R = StateSnapshot, D = unknown>(name: string, data?: D): Promise<R> {
  const res = await fetch(`/api/call/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Camera-Key": cameraKey.value ?? "" },
    body: JSON.stringify({ data: data ?? null }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body?.error?.message ?? `call ${name} failed (${res.status})`);
  }
  return body.result as R;
}

export const api = {
  setPower: (on: boolean) => call("setPower", { on }),
  startTracking: () => call("startTracking"),
  stopTracking: () => call("stopTracking"),
  startRecording: () => call("startRecording"),
  stopRecording: () => call("stopRecording"),
  getState: () => call("getState"),
  watch: () => call<{ ok: true }>("watch"),
};

/** Playback URL for a recording (range-capable). */
export function recordingUrl(name: string): string {
  return `/api/recordings/${encodeURIComponent(name)}?k=${encodeURIComponent(cameraKey.value ?? "")}`;
}
