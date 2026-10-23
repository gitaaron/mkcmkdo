<script setup lang="ts">
import { computed } from "vue";
import type { StateSnapshot } from "../lib/api";
import { modeText } from "../lib/modeText";

const props = defineProps<{ cam: StateSnapshot & { connected: boolean } }>();

// Same colours as the physical LED ring on the base.
const color = computed(() =>
  ({
    off: "var(--off)",
    sleep: "var(--sleep)",
    awake: "var(--awake)",
    tracking: "var(--tracking)",
    recording: "var(--recording)",
  })[props.cam.state],
);

// Same patterns as the LED ring, per sub-state (telemetry `phase`):
//   sleep        solid, dim (the LED shows one dim pixel)
//   awake        solid, or a slow breath with a person in frame
//   tracking     search: a quick blink (the LED chases round; with UWB the
//                camera is turning to the tag, without UWB sweeping the room).
//                found: solid (the LED fills round over the 3 s countdown)
//   recording    solid
const phase = computed(() => props.cam.telemetry?.phase);
const awakePerson = computed(() => props.cam.state === "awake" && phase.value === "person-in-frame");
const searching = computed(() => props.cam.state === "tracking" && phase.value === "search");
const found = computed(() => props.cam.state === "tracking" && phase.value === "found");

// Awake's sub-state: is anyone in frame? (older cameras don't report it)
const awakeLabel = computed(() => {
  if (phase.value === "person-in-frame") return "Awake — person in frame";
  if (phase.value === "no-person-in-frame") return "Awake — no one in frame";
  return "Awake — not recording";
});

const trackingLabel = computed(() => {
  if (searching.value) return modeText(props.cam.mode).searching;
  if (found.value) return `Found you — recording in ${props.cam.telemetry?.countdown || 1}…`;
  return "Tracking";
});

const label = computed(
  () =>
    ({
      off: "Off",
      sleep: "Asleep — camera off",
      awake: awakeLabel.value,
      tracking: trackingLabel.value,
      recording: "Recording",
    })[props.cam.state],
);
</script>

<template>
  <div
    class="ring"
    :class="{ breathing: awakePerson, searching, hollow: !cam.connected }"
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
.ring.breathing {
  /* awake with a person in frame: the LED ring breathes slowly */
  animation: pulse 2.4s ease-in-out infinite;
}
.ring.searching {
  /* the LED ring chases round while searching; a quick blink stands in */
  animation: pulse 0.5s ease-in-out infinite;
}
.ring.hollow {
  background: transparent;
  border-color: var(--c);
}
</style>
