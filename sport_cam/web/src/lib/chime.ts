/**
 * Recording start/stop chimes, synthesised with Web Audio — no files.
 *
 * Start rises (C6 → G6), stop falls (G6 → C6): two soft bell-like notes, a
 * sine with a quiet octave partial, fast attack and a gentle exponential
 * decay. Same notes as the native app's sounds, so the two agree.
 *
 * Browsers only allow audio after the user has interacted with the page, so
 * the context is created (or resumed) on the first tap or key press. A
 * background tab on a desktop still plays; a phone browser suspends pages in
 * the background, which is what the native app is for.
 */
let ctx: AudioContext | null = null;

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

function note(freq: number, at: number, peak = 0.22): void {
  if (!ctx) return;
  const t = ctx.currentTime + at;
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.0001, t);
  gain.gain.exponentialRampToValueAtTime(peak, t + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.55);
  gain.connect(ctx.destination);
  for (const [mult, level] of [[1, 1], [2, 0.18]] as const) {
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq * mult;
    g.gain.value = level;
    osc.connect(g).connect(gain);
    osc.start(t);
    osc.stop(t + 0.6);
  }
}

const C6 = 1046.5;
const G6 = 1568.0;

export function chime(kind: "start" | "stop"): void {
  unlock();
  if (!ctx) return;
  if (kind === "start") {
    note(C6, 0);
    note(G6, 0.16);
  } else {
    note(G6, 0);
    note(C6, 0.16);
  }
}
