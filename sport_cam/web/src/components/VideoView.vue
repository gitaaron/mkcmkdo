<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import type { StateSnapshot } from "../lib/api";

const props = defineProps<{ cam: StateSnapshot & { connected: boolean } }>();

// WHEP (WebRTC) when the head advertises a URL; MJPEG relay otherwise.
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
    stopWhep(); // fall back to MJPEG
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

const showPlaceholder = computed(
  () => props.cam.state === "off" || !props.cam.deviceOnline,
);
</script>

<template>
  <div class="video">
    <video v-if="whepActive" ref="videoEl" autoplay playsinline muted />
    <img v-else-if="!showPlaceholder" src="/api/stream.mjpeg" alt="live stream" />
    <div v-else class="placeholder">
      <p v-if="!cam.connected">Connecting to server…</p>
      <p v-else-if="cam.state === 'off'">Camera is off</p>
      <p v-else>Waiting for camera…</p>
    </div>
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
.placeholder {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--muted);
  font-size: 18px;
}
</style>
