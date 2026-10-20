import type { TrackingMode } from "./api.js";

/**
 * Wording that differs between the two builds. Everything else in the app —
 * states, colours, buttons' actions — is the same for both.
 *   with_uwb     the subject wears a tag; the camera turns to where it says
 *   without_uwb  no tag; the camera sweeps the room for a person
 */
export interface ModeText {
  startTracking: string;   // primary button in idle
  startRecording: string;  // primary button in tracking
  acquiring: string;       // status label while tracking but not locked on
  stalled: string;         // hint when acquiring has gone on too long
}

export const MODE_TEXT: Record<TrackingMode, ModeText> = {
  with_uwb: {
    startTracking: "Start tracking",
    startRecording: "Start recording",
    acquiring: "Acquiring subject…",
    stalled: "Can't see you — step into view, facing the camera",
  },
  without_uwb: {
    startTracking: "Track & record",
    startRecording: "Record now",
    acquiring: "Looking for a person…",
    stalled: "Can't find anyone — step into the room, facing the camera",
  },
};

export function modeText(mode: TrackingMode | undefined): ModeText {
  return MODE_TEXT[mode ?? "with_uwb"] ?? MODE_TEXT.with_uwb;
}
