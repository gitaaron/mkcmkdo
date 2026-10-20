<script setup lang="ts">
import { ref } from "vue";
import { setCameraKey } from "../lib/cameraKey";

// Shown when this browser has no camera key yet. Normally you never see it:
// the link the setup prints carries the key (…/#key=…).
const value = ref("");
const bad = ref(false);

function submit(): void {
  bad.value = !setCameraKey(value.value);
}
</script>

<template>
  <form class="prompt" @submit.prevent="submit">
    <h1>Connect to your camera</h1>
    <p>
      Open the link from the camera's setup, or paste its camera key here.
      It's <code>CAMERA_KEY</code> in the camera's <code>config.py</code>.
    </p>
    <input v-model="value" placeholder="camera key" autocomplete="off" spellcheck="false" />
    <p v-if="bad" class="err">That doesn't look like a camera key (8–64 letters, digits, - or _).</p>
    <button type="submit">Connect</button>
  </form>
</template>

<style scoped>
.prompt {
  margin: auto;
  max-width: 420px;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: var(--text, #e6edf3);
}
h1 { font-size: 22px; margin: 0; }
p { color: var(--muted, #9aa4b2); margin: 0; line-height: 1.4; }
input {
  font: inherit;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid #334;
  background: #0d1420;
  color: inherit;
}
button {
  font: inherit;
  padding: 12px;
  border: 0;
  border-radius: 10px;
  background: #2f6feb;
  color: #fff;
}
.err { color: #f85149; }
</style>
