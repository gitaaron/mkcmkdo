<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { RecordingMeta } from "../lib/api";
import { boxesAt, drawBoxes, parseBoxTrack, prepareCanvas, type BoxTrack } from "../lib/boxes";
import { useShowBoxes } from "../lib/showBoxes";
import BoxesToggle from "./BoxesToggle.vue";
import BoxLegend from "./BoxLegend.vue";

const props = defineProps<{ recording: RecordingMeta }>();

const wrap = ref<HTMLDivElement | null>(null);
const video = ref<HTMLVideoElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);
const track = ref<BoxTrack | null>(null);
const { show, toggle } = useShowBoxes("sportcam.showBoxes");
const canFullscreen = typeof document !== "undefined" && !!document.fullscreenEnabled;
const hasBoxes = computed(() => !!track.value);
watch(show, () => draw());

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
  const g = prepareCanvas(c, v.clientWidth, v.clientHeight);
  const t = track.value;
  if (!g || !show.value || !t || !v.videoWidth) return;
  drawBoxes(g, v.clientWidth, v.clientHeight, v.videoWidth, v.videoHeight, t.size,
    boxesAt(t, v.currentTime));
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
      <BoxesToggle v-if="hasBoxes" :show="show" @toggle="toggle" />
      <button v-if="canFullscreen" class="tool" title="Full screen" aria-label="Full screen" @click="fullscreen">
        ⛶
      </button>
    </div>
  </div>
  <BoxLegend v-if="hasBoxes && show" />
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
</style>
