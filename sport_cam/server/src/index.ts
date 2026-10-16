import express from "express";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { MemoryStore, parseTrackingMode } from "./state.js";
import { fns } from "./functions/index.js";
import { mountLocal } from "./lib/adapters.js";
import { Hub } from "./hub.js";
import { FrameBus } from "./stream.js";
import { Recordings } from "./recordings.js";
import { startSimulator } from "./sim.js";

const PORT = Number(process.env.PORT ?? 8787);
const SIM = process.env.SIM !== "0"; // simulator on by default in dev
// with_uwb | without_uwb — which build the camera is (see README.md)
const TRACKING_MODE = parseTrackingMode(process.env.TRACKING_MODE);
const RECORDINGS_DIR =
  process.env.RECORDINGS_DIR ??
  join(dirname(fileURLToPath(import.meta.url)), "..", "recordings");
const RECORDINGS_MAX_GB = Number(process.env.RECORDINGS_MAX_GB ?? 20);

const store = new MemoryStore(TRACKING_MODE);
const frames = new FrameBus();
const recordings = new Recordings(RECORDINGS_DIR, RECORDINGS_MAX_GB * 1024 ** 3);

const app = express();
app.use(express.json());

mountLocal(app, fns, { store, recordings });
app.get("/api/stream.mjpeg", frames.handler);
app.put("/api/recordings/upload/:name", recordings.uploadHandler);
app.get("/api/recordings/:name", recordings.serveHandler);
app.get("/api/health", (_req, res) =>
  res.json({ ok: true, mode: store.get().mode, state: store.get().state }),
);

const server = createServer(app);
const hub = new Hub(store, frames, recordings);
hub.attach(server);

store.on("change", (s) => console.log(`[state] ${s.state}`));

server.listen(PORT, () => {
  console.log(`[api] listening on http://localhost:${PORT} (mode: ${TRACKING_MODE})`);
  if (SIM) {
    // Give a real head unit a moment to connect before starting the simulator.
    setTimeout(() => {
      if (!hub.hasRealHead()) startSimulator(store, frames, recordings);
    }, 2000);
  }
});
