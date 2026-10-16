<script setup lang="ts">
import { ref } from "vue";
import { recordingUrl, type RecordingMeta } from "../lib/api";

defineProps<{ recordings: readonly RecordingMeta[] }>();
const emit = defineEmits<{ close: [] }>();

const playing = ref<RecordingMeta | null>(null);

function fmtSize(b: number): string {
  return b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(b / 1e6))} MB`;
}
function fmtWhen(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
function fmtDur(s: number | null): string {
  if (s == null) return "";
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.round(s % 60)).padStart(2, "0")}`;
}
</script>

<template>
  <div class="overlay">
    <template v-if="!playing">
      <div class="bar">
        <h2>Recordings</h2>
        <button class="close" aria-label="Close library" @click="emit('close')">✕</button>
      </div>
      <p v-if="recordings.length === 0" class="empty">No recordings yet.</p>
      <ul>
        <li v-for="r in recordings" :key="r.name">
          <button class="row" @click="playing = r">
            <span class="play">▶</span>
            <span class="meta">
              <span class="when">{{ fmtWhen(r.createdAt) }}</span>
              <span class="sub">{{ fmtDur(r.durationS) }} · {{ fmtSize(r.bytes) }}</span>
            </span>
          </button>
        </li>
      </ul>
    </template>

    <template v-else>
      <div class="bar">
        <h2>{{ fmtWhen(playing.createdAt) }}</h2>
        <button class="close" aria-label="Back to list" @click="playing = null">✕</button>
      </div>
      <!-- range-capable endpoint → seeking works on phones -->
      <video :src="recordingUrl(playing)" controls autoplay playsinline />
    </template>
  </div>
</template>

<style scoped>
.overlay {
  position: absolute;
  inset: 0;
  background: rgba(13, 20, 32, 0.97);
  z-index: 10;
  display: flex;
  flex-direction: column;
  padding: calc(10px + env(safe-area-inset-top)) 14px 14px;
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
h2 { font-size: 17px; }
.close {
  background: var(--panel);
  color: var(--ink);
  border: 1px solid #2a3850;
  border-radius: 10px;
  width: 38px;
  height: 38px;
  font-size: 15px;
  cursor: pointer;
}
.empty { color: var(--muted); padding: 24px 4px; }
ul { list-style: none; overflow-y: auto; }
.row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  text-align: left;
  background: var(--panel);
  color: var(--ink);
  border: 1px solid #223046;
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 8px;
  cursor: pointer;
  font-size: 15px;
}
.play { color: var(--idle); font-size: 13px; }
.meta { display: flex; flex-direction: column; gap: 2px; }
.sub { color: var(--muted); font-size: 12.5px; }
video { flex: 1; width: 100%; min-height: 0; background: #000; border-radius: 10px; }
</style>
