<script setup lang="ts">
import VideoView from "./components/VideoView.vue";
import StatusRing from "./components/StatusRing.vue";
import ControlBar from "./components/ControlBar.vue";
import { useCameraState } from "./lib/useCameraState";

// Opening the app starts streaming: VideoView mounts immediately and the
// WS state connection begins here.
const cam = useCameraState();
</script>

<template>
  <div class="screen">
    <VideoView :cam="cam" />
    <StatusRing :cam="cam" class="ring" />
    <ControlBar :cam="cam" class="bar" />
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
.bar {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
}
</style>
