<script setup lang="ts">
import { computed, ref } from "vue";
import { api, type StateSnapshot } from "../lib/api";
import { modeText } from "../lib/modeText";

const props = defineProps<{ cam: StateSnapshot & { connected: boolean } }>();
const busy = ref(false);

interface Btn {
  label: string;
  kind: "neutral" | "primary";
  action: () => Promise<unknown>;
}

async function run(action: () => Promise<unknown>): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  try {
    await action(); // UI updates when the state broadcast arrives
  } catch (err) {
    console.error(err);
  } finally {
    busy.value = false;
  }
}

const stopTrackingWithConfirm = async () => {
  // From 'recording' this also stops and saves the recording.
  if (props.cam.state === "recording" && !confirm("Stop tracking? This also stops the recording.")) {
    return;
  }
  await api.stopTracking();
};

const buttons = computed<Btn[]>(() => {
  const text = modeText(props.cam.mode);
  switch (props.cam.state) {
    case "off":
      return [{ label: "Turn on", kind: "primary", action: () => api.setPower(true) }];
    case "idle":
      return [
        { label: "Turn off", kind: "neutral", action: () => api.setPower(false) },
        { label: text.startTracking, kind: "primary", action: () => api.startTracking() },
      ];
    case "tracking":
      return [
        { label: "Turn off", kind: "neutral", action: () => api.setPower(false) },
        { label: text.startRecording, kind: "primary", action: () => api.startRecording() },
      ];
    case "recording":
      return [
        { label: "Stop recording", kind: "neutral", action: () => api.stopRecording() },
        { label: "Stop tracking", kind: "primary", action: stopTrackingWithConfirm },
      ];
  }
});
</script>

<template>
  <div class="bar" :data-state="cam.state">
    <button
      v-for="b in buttons"
      :key="b.label"
      :class="b.kind"
      :disabled="busy || !cam.connected"
      @click="run(b.action)"
    >
      {{ b.label }}
    </button>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  gap: 10px;
  padding: 14px 14px calc(14px + env(safe-area-inset-bottom));
  background: linear-gradient(transparent, rgba(13, 20, 32, 0.92) 40%);
}
button {
  flex: 1;
  padding: 15px 10px;
  border-radius: 12px;
  border: 1px solid transparent;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: filter 0.15s;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
button:not(:disabled):active {
  filter: brightness(1.2);
}
.neutral {
  background: var(--panel);
  color: var(--ink);
  border-color: #2a3850;
}
[data-state="idle"] .primary {
  background: var(--idle);
  color: #fff;
}
[data-state="tracking"] .primary {
  background: var(--tracking);
  color: #fff;
}
[data-state="recording"] .primary {
  background: var(--recording);
  color: #fff;
}
[data-state="off"] .primary {
  background: var(--idle);
  color: #fff;
}
</style>
