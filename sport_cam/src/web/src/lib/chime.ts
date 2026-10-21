/**
 * Session sounds, synthesised with Web Audio — no files.
 *
 * Start rises (C6 → G6), stop falls (G6 → C6): two soft bell-like notes, a
 * sine with a quiet octave partial, fast attack and a gentle exponential
 * decay. The beep, one per centred detection while the camera locks on, is
 * a single short A5. Same notes as the native app's sounds, so the two agree.
 *
 * Sounds queue rather than overlap: beeps that arrive together play one
 * after another, and the start chime waits for the last beep.
 *
 * Browsers only allow audio after the user has interacted with the page, so
 * the context is created (or resumed) on the first tap or key press. A
 * background tab on a desktop still plays; a phone browser suspends pages in
 * the background, which is what the native app is for.
 */
let ctx: AudioContext | null = null;
let queueEnd = 0;   // context time at which the last queued sound has played

function unlock(): void {
  try {
    ctx ??= new AudioContext();
    if (ctx.state === "suspended") void ctx.resume();
  } catch {
    /* no Web Audio: chimes are a nicety, never an error */
  }
}

if (typeof window !== "undefined") {
  for (const ev of ["pointerdown", "keydown", "touchstart"]) {
    window.addEventListener(ev, unlock, { passive: true });
  }
}

function note(freq: number, t: number, peak = 0.22, decay = 0.55): void {
  if (!ctx) return;
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.0001, t);
  gain.gain.exponentialRampToValueAtTime(peak, t + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + decay);
  gain.connect(ctx.destination);
  for (const [mult, level] of [[1, 1], [2, 0.18]] as const) {
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq * mult;
    g.gain.value = level;
    osc.connect(g).connect(gain);
    osc.start(t);
    osc.stop(t + decay + 0.05);
  }
}

/** Start time for a sound `length` seconds long, after anything still queued. */
function slot(length: number): number | null {
  unlock();
  if (!ctx) return null;
  const t = Math.max(ctx.currentTime, queueEnd);
  queueEnd = t + length;
  return t;
}

const A5 = 880.0;
const C6 = 1046.5;
const G6 = 1568.0;

export function chime(kind: "start" | "stop"): void {
  const t = slot(0.75);
  if (t === null) return;
  if (kind === "start") {
    note(C6, t);
    note(G6, t + 0.16);
  } else {
    note(G6, t);
    note(C6, t + 0.16);
  }
}

/** One centred detection on the way to a lock. */
export function beep(): void {
  const t = slot(0.25);
  if (t !== null) note(A5, t, 0.18, 0.12);
}
