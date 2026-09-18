import express from "express";
import { createServer } from "node:http";
import { MemoryStore } from "./state.js";
import { fns } from "./functions/index.js";
import { mountLocal } from "./lib/adapters.js";
import { Hub } from "./hub.js";
import { FrameBus } from "./stream.js";
import { startSimulator } from "./sim.js";

const PORT = Number(process.env.PORT ?? 8787);
const SIM = process.env.SIM !== "0"; // simulator on by default in dev

const store = new MemoryStore();
const frames = new FrameBus();

const app = express();
app.use(express.json());

mountLocal(app, fns, { store });
app.get("/api/stream.mjpeg", frames.handler);
app.get("/api/health", (_req, res) => res.json({ ok: true, state: store.get().state }));

const server = createServer(app);
const hub = new Hub(store, frames);
hub.attach(server);

store.on("change", (s) => console.log(`[state] ${s.state}`));

server.listen(PORT, () => {
  console.log(`[api] listening on http://localhost:${PORT}`);
  if (SIM) {
    // Give a real head unit a moment to connect before starting the simulator.
    setTimeout(() => {
      if (!hub.hasRealHead()) startSimulator(store, frames);
    }, 2000);
  }
});
