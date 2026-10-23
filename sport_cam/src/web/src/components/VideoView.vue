<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { LIVE_STATES, type StateSnapshot } from "../lib/api";
import { drawBoxes, LIVE_HOLD_MS, prepareCanvas, type LiveBoxes } from "../lib/boxes";
import { useShowBoxes } from "../lib/showBoxes";
import BoxesToggle from "./BoxesToggle.vue";

const props = defineProps<{
  cam: StateSnapshot & { connected: boolean; previewUrl: string | null; liveBoxes: LiveBoxes | null };
}>();

// WHEP (WebRTC) when the camera advertises a URL this page can reach (its
// own Wi-Fi); otherwise the low-rate preview the camera posts to Firestore
// while someone is watching.
const videoEl = ref<HTMLVideoElement | null>(null);
const whepActive = ref(false);
let pc: RTCPeerConnection | null = null;

async function startWhep(url: string): Promise<void> {
  try {
    pc = new RTCPeerConnection();
    pc.addTransceiver("video", { direction: "recvonly" });
    pc.ontrack = (ev) => {
      if (videoEl.value) videoEl.value.srcObject = ev.streams[0];
    };
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/sdp" },
      body: offer.sdp,
    });
    if (!res.ok) throw new Error(`WHEP ${res.status}`);
    await pc.setRemoteDescription({ type: "answer", sdp: await res.text() });
    whepActive.value = true;
  } catch {
    stopWhep(); // fall back to the preview
  }
}

function stopWhep(): void {
  pc?.close();
  pc = null;
  whepActive.value = false;
}

watch(
  () => props.cam.whepUrl,
  (url) => (url ? startWhep(url) : stopWhep()),
  { immediate: true },
);
onBeforeUnmount(stopWhep);

// No picture outside awake, initiate recording and recording: asleep the
// camera's sensor is off.
const showPlaceholder = computed(
  () => !LIVE_STATES.includes(props.cam.state) || !props.cam.deviceOnline,
);

// ---- person boxes over the picture -------------------------------------------
// They arrive with each preview frame (useCameraState). Over WebRTC the video
// runs at full rate but the boxes still come once a second, with the preview.
const root = ref<HTMLDivElement | null>(null);
const imgEl = ref<HTMLImageElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);
const { show, toggle } = useShowBoxes("sportcam.showLiveBoxes");
const showingPicture = computed(
  () => !showPlaceholder.value && (whepActive.value || !!props.cam.previewUrl),
);

function draw(): void {
  const c = canvas.value;
  const el = root.value;
  if (!c || !el) return;
  const g = prepareCanvas(c, el.clientWidth, el.clientHeight);
  const live = props.cam.liveBoxes;
  if (!g || !show.value || !showingPicture.value || !live) return;
  if (Date.now() - live.receivedAt > LIVE_HOLD_MS) return;
  const v = videoEl.value;
  const [pw, ph] = whepActive.value && v
    ? [v.videoWidth, v.videoHeight]
    : [imgEl.value?.naturalWidth ?? 0, imgEl.value?.naturalHeight ?? 0];
  if (!pw || !ph) return;
  drawBoxes(g, el.clientWidth, el.clientHeight, pw, ph, live.size, live.boxes);
}

watch(() => [props.cam.liveBoxes, show.value, showingPicture.value], draw);
let resize: ResizeObserver | null = null;
let staleTimer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  resize = new ResizeObserver(draw);
  if (root.value) resize.observe(root.value);
  staleTimer = setInterval(draw, 500);   // drops boxes once frames stop coming
});
onBeforeUnmount(() => {
  resize?.disconnect();
  clearInterval(staleTimer);
});
</script>

<template>
  <div ref="root" class="video">
    <video v-if="whepActive && !showPlaceholder" ref="videoEl" autoplay playsinline muted @loadedmetadata="draw" />
    <img v-else-if="!showPlaceholder && cam.previewUrl" ref="imgEl" :src="cam.previewUrl" alt="live preview" @load="draw" />
    <div v-else class="placeholder">
      <p v-if="!cam.connected">Connecting…</p>
      <p v-else-if="!cam.deviceOnline">Camera is offline</p>
      <p v-else-if="cam.state === 'off'">Camera is starting up…</p>
      <p v-else-if="cam.state === 'sleep'">Camera is asleep — wake it up or record to see the picture</p>
      <p v-else>Waiting for the picture…</p>
    </div>
    <canvas ref="canvas" class="boxes" aria-hidden="true" />
    <BoxesToggle v-if="showingPicture" class="live-toggle" :show="show" @toggle="toggle" />
  </div>
</template>

<style scoped>
.video,
.video video,
.video img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
}
.boxes {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
/* under the recordings button, top-left */
.live-toggle {
  position: absolute;
  top: calc(60px + env(safe-area-inset-top));
  left: 14px;
}
.placeholder {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--muted);
  font-size: 18px;
}
</style>
