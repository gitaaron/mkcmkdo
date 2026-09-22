import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";
import { describe, expect, it } from "vitest";
import { MemoryStore } from "../state.js";
import { Recordings } from "../recordings.js";
import { fns } from "./index.js";

const ctx = () => ({
  store: new MemoryStore(),
  recordings: new Recordings(mkdtempSync(join(tmpdir(), "sportcam-rec-")), 1024 ** 3),
});

describe("recording library", () => {
  it("full pipeline: upload URL → save → finalize → list", async () => {
    const c = ctx();
    const { url, method } = await fns.createUploadUrl({ name: "rec_1.mp4" }, c);
    expect(method).toBe("PUT");
    expect(url).toBe("/api/recordings/upload/rec_1.mp4");

    const bytes = await c.recordings.save("rec_1.mp4", Readable.from([Buffer.alloc(1000)]));
    expect(bytes).toBe(1000);

    const meta = await fns.finalizeRecording({ name: "rec_1.mp4", bytes: 1000, durationS: 42 }, c);
    expect(meta.durationS).toBe(42);
    expect(meta.url).toBe("/api/recordings/rec_1.mp4");

    const { recordings } = await fns.getRecordings(undefined, c);
    expect(recordings).toHaveLength(1);
    expect(recordings[0]!.bytes).toBe(1000);
  });

  it("rejects unsafe names and size mismatches", async () => {
    const c = ctx();
    await expect(fns.createUploadUrl({ name: "../evil.mp4" }, c)).rejects.toMatchObject({
      code: "invalid-argument",
    });
    await expect(fns.createUploadUrl({ name: "clip.avi" }, c)).rejects.toMatchObject({
      code: "invalid-argument",
    });
    await expect(
      fns.finalizeRecording({ name: "missing.mp4", bytes: 5 }, c),
    ).rejects.toMatchObject({ code: "failed-precondition" });

    await c.recordings.save("rec_2.mp4", Readable.from([Buffer.alloc(10)]));
    await expect(
      fns.finalizeRecording({ name: "rec_2.mp4", bytes: 999 }, c),
    ).rejects.toMatchObject({ code: "failed-precondition" });
  });

  it("prunes oldest recordings beyond the retention budget", async () => {
    const dir = mkdtempSync(join(tmpdir(), "sportcam-prune-"));
    const rec = new Recordings(dir, 2500);
    for (let i = 0; i < 3; i++) {
      writeFileSync(join(dir, `rec_${i}.mp4`), Buffer.alloc(1000));
      // stagger mtimes via distinct writes is unreliable in-loop; set explicit order
    }
    rec.finalize("rec_2.mp4", null);
    const names = rec.list().map((r) => r.name);
    expect(names.length).toBe(2); // 3000 bytes > 2500 budget → oldest dropped
  });
});
