import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import type { Store } from "./state.js";
import type { FrameBus } from "./stream.js";

const FRAMES_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "sim", "frames");

/**
 * Device simulator (SIM=1): plays pre-rendered test frames into the MJPEG
 * relay and feeds plausible telemetry, so the whole app works with no
 * hardware attached. Regenerate frames with `python3 server/sim/gen_frames.py`.
 */
export function startSimulator(store: Store, frames: FrameBus): void {
  let jpegs: Buffer[] = [];
  try {
    jpegs = readdirSync(FRAMES_DIR)
      .filter((f) => f.endsWith(".jpg"))
      .sort()
      .map((f) => readFileSync(join(FRAMES_DIR, f)));
  } catch {
    // no frames generated — simulator still provides telemetry
  }
  console.log(`[sim] device simulator on (${jpegs.length} test frames)`);
  store.patch({ deviceOnline: true });

  let i = 0;
  let pan = 0;
  setInterval(() => {
    if (store.get().state === "off") return;
    if (jpegs.length) frames.push(jpegs[i++ % jpegs.length]!);
  }, 125);

  setInterval(() => {
    const s = store.get().state;
    if (s === "off") return;
    if (s === "tracking" || s === "recording") pan = (pan + 3.6) % 360;
    store.patch({
      telemetry: {
        pan: Math.round(pan * 10) / 10,
        tilt: 12,
        zoomMm: 11.5,
        dist: 4.2 + Math.sin(Date.now() / 3000),
        battery: 0.82,
      },
    });
  }, 1000);
}
