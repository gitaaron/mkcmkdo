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
