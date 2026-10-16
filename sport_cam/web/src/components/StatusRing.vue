<script setup lang="ts">
import { computed } from "vue";
import type { StateSnapshot } from "../lib/api";

const props = defineProps<{ cam: StateSnapshot & { connected: boolean } }>();

// Same colours as the physical LED ring on the base.
const color = computed(() =>
  ({
    off: "var(--off)",
    idle: "var(--idle)",
    tracking: "var(--tracking)",
    recording: "var(--recording)",
  })[props.cam.state],
);

// Tag switched on, camera still turning to find the subject.
const acquiring = computed(
  () => props.cam.state === "tracking" && props.cam.telemetry?.phase === "acquiring",
);

const label = computed(() =>
  acquiring.value
    ? "Acquiring subject…"
    : ({
        off: "Off",
        idle: "On — not tracking",
        tracking: "Tracking",
        recording: "Recording",
      })[props.cam.state],
);
</script>

<template>
  <div
    class="ring"
    :class="{ pulsing: cam.state === 'recording', acquiring, hollow: !cam.connected }"
    :style="{ '--c': color }"
    :title="label"
    role="status"
    :aria-label="label"
  />
</template>

<style scoped>
.ring {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--c);
  border: 3px solid rgba(255, 255, 255, 0.85);
  box-shadow: 0 0 12px color-mix(in srgb, var(--c) 60%, transparent);
}
.ring.pulsing {
  animation: pulse 1.2s ease-in-out infinite;
}
.ring.acquiring {
  /* the LED ring chases round while acquiring; a quick blink stands in */
  animation: pulse 0.5s ease-in-out infinite;
}
.ring.hollow {
  background: transparent;
  border-color: var(--c);
}
</style>
