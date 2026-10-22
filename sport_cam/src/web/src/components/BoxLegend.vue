<script setup lang="ts">
import { BOX_COLOURS } from "../lib/boxes";
</script>

<template>
  <p class="legend">
    <span><i :style="{ borderColor: BOX_COLOURS.climber }" />climber</span>
    <span><i :style="{ borderColor: BOX_COLOURS.other }" />someone else</span>
    <span><i :style="{ borderColor: BOX_COLOURS.unsure }" />can't tell yet</span>
  </p>
</template>

<style scoped>
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 8px;
  color: var(--muted);
  font-size: 12.5px;
}
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { width: 12px; height: 12px; border: 2px solid; border-radius: 2px; }
</style>
