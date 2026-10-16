import { EventEmitter } from "node:events";
import {
  createWriteStream, existsSync, mkdirSync, readFileSync, readdirSync,
  renameSync, statSync, unlinkSync, writeFileSync,
} from "node:fs";
import { join } from "node:path";
import type { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import type { Request, Response } from "express";

export interface RecordingMeta {
  name: string;
  bytes: number;
  createdAt: string;
  durationS: number | null;
  url: string; // app-facing playback URL (range-capable)
}

const NAME_RE = /^[A-Za-z0-9._-]+\.mp4$/;

export function safeName(name: unknown): string | null {
  return typeof name === "string" && NAME_RE.test(name) && !name.includes("..") ? name : null;
}

/**
 * Local recordings store: MP4s uploaded by the head unit land in a directory,
 * with a JSON sidecar per file for metadata. The Firebase deployment replaces
 * this with Cloud Storage + Firestore behind the same callable API.
 */
export class Recordings extends EventEmitter {
  constructor(
    private dir: string,
    private maxBytes: number, // retention: prune oldest beyond this
  ) {
    super();
    mkdirSync(dir, { recursive: true });
  }

  path(name: string): string {
    return join(this.dir, name);
  }

  list(): RecordingMeta[] {
    return readdirSync(this.dir)
      .filter((f) => NAME_RE.test(f))
      .map((name) => {
        const st = statSync(this.path(name));
        let durationS: number | null = null;
        try {
          durationS = JSON.parse(readFileSync(this.path(name) + ".json", "utf8")).durationS ?? null;
        } catch {
          /* no sidecar */
        }
        return {
          name,
          bytes: st.size,
          createdAt: st.mtime.toISOString(),
          durationS,
          url: `/api/recordings/${name}`,
        };
      })
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  /** Stream an upload to disk (via a temp file so partial uploads never list). */
  async save(name: string, body: Readable): Promise<number> {
    const tmp = this.path(name) + ".part";
    await pipeline(body, createWriteStream(tmp));
    renameSync(tmp, this.path(name));
    return statSync(this.path(name)).size;
  }

  finalize(name: string, durationS: number | null): RecordingMeta {
    writeFileSync(this.path(name) + ".json", JSON.stringify({ durationS }));
    this.prune();
    const meta = this.list().find((r) => r.name === name)!;
    this.emit("change", this.list());
    return meta;
  }

  exists(name: string): boolean {
    return existsSync(this.path(name));
  }

  size(name: string): number {
    return statSync(this.path(name)).size;
  }

  /** Drop oldest recordings until total size fits the retention budget. */
  prune(): void {
    const all = this.list();
    let total = all.reduce((s, r) => s + r.bytes, 0);
    for (const r of [...all].reverse()) {
      if (total <= this.maxBytes) break;
      try {
        unlinkSync(this.path(r.name));
        unlinkSync(this.path(r.name) + ".json");
      } catch { /* sidecar may not exist */ }
      total -= r.bytes;
    }
  }

  /** PUT /api/recordings/upload/:name — raw MP4 body streamed to disk. */
  uploadHandler = async (req: Request, res: Response): Promise<void> => {
    const name = safeName(req.params.name);
    if (!name) {
      res.status(400).json({ error: { code: "invalid-argument", message: "bad recording name" } });
      return;
    }
    try {
      const bytes = await this.save(name, req);
      res.json({ result: { name, bytes } });
    } catch (err) {
      console.error("[recordings] upload failed:", err);
      res.status(500).json({ error: { code: "internal", message: "upload failed" } });
    }
  };

  /** GET /api/recordings/:name — range-capable playback (phone <video> seeks). */
  serveHandler = (req: Request, res: Response): void => {
    const name = safeName(req.params.name);
    if (!name || !this.exists(name)) {
      res.status(404).json({ error: { code: "not-found", message: "no such recording" } });
      return;
    }
    // Express sendFile handles Range/If-Range/HEAD for us.
    res.sendFile(this.path(name), { root: undefined, acceptRanges: true, cacheControl: false });
  };
}
