/**
 * The person boxes the camera saves beside each clip (`<clip>.boxes.json`,
 * written by the device's boxlog.py), and how to find the ones to draw at a
 * moment of the video.
 *
 *   { "v": 1, "size": [1280, 720],
 *     "frames": [[0.33, [[x, y, w, h, "climber"], ...]], [0.66, []], ...] }
 *
 * One frame per detection, a few a second: seconds from the clip's start,
 * then boxes in pixels of a `size` frame, the same field of view as the video.
 */
export type BoxLabel = "climber" | "other" | "unsure";
export type Box = [x: number, y: number, w: number, h: number, label: BoxLabel];

export interface BoxTrack {
  size: [number, number];
  frames: [t: number, boxes: Box[]][];
}

/** A frame's boxes are shown until the next detection, or this long at most. */
export const HOLD_S = 1.0;

/** green: the climber; yellow: anyone else; red: the camera can't tell yet. */
export const BOX_COLOURS: Record<BoxLabel, string> = {
  climber: "#34c759",
  other: "#ffcc00",
  unsure: "#ff3b30",
};

export const boxesName = (clip: string) => clip.replace(/\.mp4$/, ".boxes.json");

export function parseBoxTrack(json: unknown): BoxTrack | null {
  const j = json as Partial<BoxTrack> & { v?: number };
  if (j?.v !== 1 || !Array.isArray(j.size) || !Array.isArray(j.frames)) return null;
  return { size: j.size, frames: j.frames };
}

/** The boxes on screen at `t` seconds: the last detection at or before it. */
export function boxesAt(track: BoxTrack, t: number): Box[] {
  const f = track.frames;
  let lo = 0;
  let hi = f.length - 1;
  if (hi < 0 || f[0]![0] > t) return [];
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (f[mid]![0] <= t) lo = mid;
    else hi = mid - 1;
  }
  const [at, boxes] = f[lo]!;
  return t - at <= HOLD_S ? boxes : [];
}

/**
 * The live view's boxes: the camera's last detection, as it sent it with the
 * latest preview frame. `size` is the frame they're measured in.
 */
export interface LiveBoxes {
  readonly size: readonly [number, number];
  readonly boxes: readonly Readonly<Box>[];
  readonly receivedAt: number; // Date.now() when they arrived
}

/**
 * Live boxes this old are dropped. The camera sends a fresh list with every
 * preview frame (1 a second), so this only bites when frames stop coming.
 */
export const LIVE_HOLD_MS = 3000;

interface StoredBox { x: number; y: number; w: number; h: number; label: BoxLabel }

/** The boxes stored beside a preview frame (maps: Firestore can't nest arrays). */
export function liveBoxesFromPreview(
  p: { size?: number[]; boxes?: StoredBox[] },
  now = Date.now(),
): LiveBoxes | null {
  if (p.size?.length !== 2 || !Array.isArray(p.boxes)) return null;
  return {
    size: [p.size[0]!, p.size[1]!],
    boxes: p.boxes.map((b) => [b.x, b.y, b.w, b.h, b.label]),
    receivedAt: now,
  };
}

/**
 * Stroke `boxes` (in pixels of a `size` frame) over a picture `picW` × `picH`
 * shown with object-fit: contain in a `cw` × `ch` element.
 */
export function drawBoxes(
  g: CanvasRenderingContext2D,
  cw: number,
  ch: number,
  picW: number,
  picH: number,
  size: readonly [number, number],
  boxes: readonly Readonly<Box>[],
): void {
  const scale = Math.min(cw / picW, ch / picH);
  const pw = picW * scale;
  const ph = picH * scale;
  const ox = (cw - pw) / 2;
  const oy = (ch - ph) / 2;
  const sx = pw / size[0];
  const sy = ph / size[1];
  g.lineWidth = 2.5;
  for (const [x, y, w, h, label] of boxes) {
    g.strokeStyle = BOX_COLOURS[label] ?? BOX_COLOURS.unsure;
    g.strokeRect(ox + x * sx, oy + y * sy, w * sx, h * sy);
  }
}

/** Size a canvas to its element at the device's pixel ratio; its 2D context, cleared. */
export function prepareCanvas(c: HTMLCanvasElement, cw: number, ch: number): CanvasRenderingContext2D | null {
  const dpr = window.devicePixelRatio || 1;
  if (c.width !== Math.round(cw * dpr) || c.height !== Math.round(ch * dpr)) {
    c.width = Math.round(cw * dpr);
    c.height = Math.round(ch * dpr);
  }
  const g = c.getContext("2d");
  if (!g) return null;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, cw, ch);
  return g;
}
