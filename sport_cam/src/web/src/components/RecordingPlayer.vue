<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { RecordingMeta } from "../lib/api";
import { BOX_COLOURS, boxesAt, parseBoxTrack, type BoxTrack } from "../lib/boxes";

const props = defineProps<{ recording: RecordingMeta }>();

const STORAGE = "sportcam.showBoxes";
const wrap = ref<HTMLDivElement | null>(null);
const video = ref<HTMLVideoElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);
const track = ref<BoxTrack | null>(null);
const show = ref(readShow());
const canFullscreen = typeof document !== "undefined" && !!document.fullscreenEnabled;
const hasBoxes = computed(() => !!track.value);

function readShow(): boolean {
  try {
    return localStorage.getItem(STORAGE) !== "0";
  } catch {
    return true;
  }
}

function toggle(): void {
  show.value = !show.value;
  try {
    localStorage.setItem(STORAGE, show.value ? "1" : "0");
  } catch {
    /* storage blocked: lasts for this visit */
  }
  draw();
}

async function load(url: string | null): Promise<void> {
  track.value = null;
  if (!url) return;
  try {
    const res = await fetch(url);
    if (res.ok) track.value = parseBoxTrack(await res.json());
  } catch {
    /* no boxes: the video plays without them */
  }
  draw();
}

/** Draw the boxes for the frame on screen, inside the letterboxed picture. */
function draw(): void {
  const v = video.value;
  const c = canvas.value;
  if (!v || !c) return;
  const dpr = window.devicePixelRatio || 1;
  const cw = v.clientWidth;
  const ch = v.clientHeight;
  if (c.width !== Math.round(cw * dpr) || c.height !== Math.round(ch * dpr)) {
    c.width = Math.round(cw * dpr);
    c.height = Math.round(ch * dpr);
  }
  const g = c.getContext("2d");
  if (!g) return;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, cw, ch);
  const t = track.value;
  if (!show.value || !t || !v.videoWidth) return;

  // object-fit: contain — where the picture actually sits in the element
  const scale = Math.min(cw / v.videoWidth, ch / v.videoHeight);
  const pw = v.videoWidth * scale;
  const ph = v.videoHeight * scale;
  const ox = (cw - pw) / 2;
  const oy = (ch - ph) / 2;
  const sx = pw / t.size[0];
  const sy = ph / t.size[1];
  g.lineWidth = 2.5;
  for (const [x, y, w, h, label] of boxesAt(t, v.currentTime)) {
    g.strokeStyle = BOX_COLOURS[label] ?? BOX_COLOURS.unsure;
    g.strokeRect(ox + x * sx, oy + y * sy, w * sx, h * sy);
  }
}

// Redraw on every video frame while playing, and on seeks and resizes.
let frameHandle = 0;
function loop(): void {
  draw();
  const v = video.value;
  if (!v || v.paused || v.ended) return;
  if ("requestVideoFrameCallback" in v) {
    frameHandle = (v as HTMLVideoElement & { requestVideoFrameCallback(cb: () => void): number })
      .requestVideoFrameCallback(loop);
  } else {
    frameHandle = requestAnimationFrame(loop);
  }
}

function fullscreen(): void {
  if (document.fullscreenElement) void document.exitFullscreen();
  else void wrap.value?.requestFullscreen();
}

let resize: ResizeObserver | null = null;
onMounted(() => {
  void load(props.recording.boxesUrl);
  resize = new ResizeObserver(draw);
  if (video.value) resize.observe(video.value);
});
onBeforeUnmount(() => {
  resize?.disconnect();
  cancelAnimationFrame(frameHandle);
});
watch(() => props.recording.boxesUrl, (url) => void load(url));
</script>

<template>
  <div ref="wrap" class="player">
    <!-- range-capable endpoint → seeking works on phones. The browser's own
         fullscreen would take the video alone and leave the boxes behind, so
         fullscreen is this player's button instead. -->
    <video
      ref="video"
      :src="recording.url"
      controls
      autoplay
      playsinline
      controlslist="nofullscreen"
      disablepictureinpicture
      @play="loop"
      @seeked="draw"
      @loadedmetadata="draw"
      @timeupdate="draw"
    />
    <canvas ref="canvas" aria-hidden="true" />
    <div class="tools">
      <button
        v-if="hasBoxes"
        class="tool"
        :aria-pressed="show"
        :title="show ? 'Hide the boxes' : 'Show the boxes'"
        @click="toggle"
      >
        <span class="swatch" />{{ show ? "Boxes on" : "Boxes off" }}
      </button>
      <button v-if="canFullscreen" class="tool" title="Full screen" aria-label="Full screen" @click="fullscreen">
        ⛶
      </button>
    </div>
  </div>
  <p v-if="hasBoxes && show" class="legend">
    <span><i :style="{ borderColor: BOX_COLOURS.climber }" />climber</span>
    <span><i :style="{ borderColor: BOX_COLOURS.other }" />someone else</span>
    <span><i :style="{ borderColor: BOX_COLOURS.unsure }" />can't tell yet</span>
  </p>
</template>

<style scoped>
.player {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  background: #000;
  border-radius: 10px;
  overflow: hidden;
}
video { flex: 1; width: 100%; min-height: 0; background: #000; }
canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.tools {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  gap: 6px;
}
.tool {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(13, 20, 32, 0.7);
  color: var(--ink);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 13px;
  cursor: pointer;
}
.swatch {
  width: 12px;
  height: 12px;
  border: 2px solid #34c759;
  border-radius: 2px;
}
.tool[aria-pressed="false"] .swatch { border-color: var(--muted); }
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 8px;
  color: var(--muted);
  font-size: 12.5px;
}
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { width: 12px; height: 12px; border: 2px solid; border-radius: 2px; }
</style>
