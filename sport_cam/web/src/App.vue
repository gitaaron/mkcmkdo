<script setup lang="ts">
import { ref } from "vue";
import VideoView from "./components/VideoView.vue";
import StatusRing from "./components/StatusRing.vue";
import ControlBar from "./components/ControlBar.vue";
import LibraryView from "./components/LibraryView.vue";
import { useCameraState, dismissToast } from "./lib/useCameraState";

// Opening the app starts streaming: VideoView mounts immediately and the
// WS state connection begins here.
const cam = useCameraState();
const showLibrary = ref(false);

function openFromToast(): void {
  dismissToast();
  showLibrary.value = true;
}
</script>

<template>
  <div class="screen">
    <VideoView :cam="cam" />
    <StatusRing :cam="cam" class="ring" />

    <button class="library-btn" aria-label="Recordings" @click="showLibrary = true">
      ▶<span v-if="cam.recordings.length" class="badge">{{ cam.recordings.length }}</span>
    </button>

    <div v-if="cam.state === 'tracking' && cam.telemetry.acquireStalled" class="hint" role="status">
      Can't see you — step into view, facing the camera
    </div>

    <div v-if="cam.upload" class="upload">
      Uploading… {{ Math.round((cam.upload.sent / cam.upload.total) * 100) }}%
    </div>
    <button v-else-if="cam.lastSaved" class="toast" @click="openFromToast">
      Recording saved — watch now
    </button>

    <ControlBar :cam="cam" class="bar" />
    <LibraryView v-if="showLibrary" :recordings="cam.recordings" @close="showLibrary = false" />
  </div>
</template>

<style scoped>
.screen {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.ring {
  position: absolute;
  top: calc(14px + env(safe-area-inset-top));
  right: 14px;
}
.library-btn {
  position: absolute;
  top: calc(10px + env(safe-area-inset-top));
  left: 14px;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  border: 1px solid #2a3850;
  background: rgba(19, 28, 44, 0.85);
  color: var(--ink);
  font-size: 14px;
  cursor: pointer;
}
.badge {
  position: absolute;
  top: -6px;
  right: -6px;
  background: var(--idle);
  color: #fff;
  border-radius: 9px;
  font-size: 10.5px;
  padding: 1px 5px;
}
.hint {
  position: absolute;
  top: calc(60px + env(safe-area-inset-top));
  left: 50%;
  transform: translateX(-50%);
  padding: 8px 14px;
  border-radius: 10px;
  background: rgba(19, 28, 44, 0.9);
  border: 1px solid var(--tracking);
  color: var(--ink);
  font-size: 14px;
  white-space: nowrap;
}
.upload,
.toast {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  bottom: 96px;
  background: var(--panel);
  color: var(--ink);
  border: 1px solid #2a3850;
  border-radius: 999px;
  padding: 9px 18px;
  font-size: 13.5px;
}
.toast {
  cursor: pointer;
  border-color: var(--tracking);
  color: #d9f5e5;
}
.bar {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
}
</style>
