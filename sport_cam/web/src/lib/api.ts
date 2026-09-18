export type CamState = "off" | "idle" | "tracking" | "recording";

export interface Telemetry {
  pan?: number;
  tilt?: number;
  zoomMm?: number;
  dist?: number;
  battery?: number;
}

export interface StateSnapshot {
  state: CamState;
  telemetry: Telemetry;
  deviceOnline: boolean;
  whepUrl: string | null;
  updatedAt: string;
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

/**
 * Single entry point for API calls. On Firebase this becomes
 * `httpsCallable(functions, name)(data)` — nothing else in the app changes.
 */
export async function call<R = StateSnapshot, D = unknown>(name: string, data?: D): Promise<R> {
  const res = await fetch(`${BASE}/api/call/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data: data ?? null }),
  });
  const body = await res.json();
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
};
