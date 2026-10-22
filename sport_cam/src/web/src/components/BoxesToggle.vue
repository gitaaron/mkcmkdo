<script setup lang="ts">
// The Boxes on / off button, the same over a recording and over the live view.
defineProps<{ show: boolean }>();
defineEmits<{ toggle: [] }>();
</script>

<template>
  <button
    class="boxes-toggle"
    :aria-pressed="show"
    :title="show ? 'Hide the person boxes' : 'Show the person boxes'"
    @click="$emit('toggle')"
  >
    <span class="swatch" />{{ show ? "Boxes on" : "Boxes off" }}
  </button>
</template>

<style scoped>
.boxes-toggle {
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
.swatch {
  width: 12px;
  height: 12px;
  border: 2px solid #34c759;
  border-radius: 2px;
}
.boxes-toggle[aria-pressed="false"] .swatch { border-color: var(--muted); }
</style>
