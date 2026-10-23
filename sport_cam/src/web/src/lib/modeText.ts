import type { TrackingMode } from "./api.js";

/**
 * Wording that differs between the two builds. Everything else in the app —
 * states, colours, buttons' actions — is the same for both.
 *   with_uwb     the subject wears a tag; the camera turns to where it says
 *   without_uwb  no tag; the camera sweeps the room for a person
 */
export interface ModeText {
  startTracking: string;   // primary button in awake
  searching: string;       // status label while tracking, in search
  stalled: string;         // hint when tracking has gone on too long without recording
}

export const MODE_TEXT: Record<TrackingMode, ModeText> = {
  with_uwb: {
    startTracking: "Start tracking",
    searching: "Turning to your tag…",
    stalled: "Can't pick you out — step into view, away from anyone else",
  },
  without_uwb: {
    startTracking: "Track & record",
    searching: "Looking for a person…",
    stalled: "Can't find anyone — step into the room, facing the camera",
  },
};

export function modeText(mode: TrackingMode | undefined): ModeText {
  return MODE_TEXT[mode ?? "with_uwb"] ?? MODE_TEXT.with_uwb;
}
