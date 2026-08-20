<script setup>
import StatusBadge from './StatusBadge.vue'

defineProps({
  no: { type: String, default: '' },
  name: { type: String, default: '' },
  meta: { type: String, default: '' },
  status: { type: String, default: '' },
  statusLabel: { type: String, default: '' },
  selected: { type: Boolean, default: false },
  removable: { type: Boolean, default: false },
})
defineEmits(['select', 'remove'])
</script>

<template>
  <div :class="['archive', { selected }]" @click="$emit('select')">
    <div class="head">
      <span class="no">{{ no }}</span>
      <button v-if="removable" class="ghost danger x" title="删除" @click.stop="$emit('remove')">×</button>
    </div>
    <div class="name">{{ name }}</div>
    <div class="meta">{{ meta }}</div>
    <StatusBadge v-if="status" :status="status" :label="statusLabel" />
  </div>
</template>

<style scoped>
.archive {
  border: var(--hairline-w) solid var(--hairline);
  background: var(--surface);
  border-radius: var(--radius);
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color var(--dur) var(--ease);
}
.archive:hover { border-color: var(--border-hover); }
.archive.selected { border-color: var(--cobalt); }
.head { display: flex; align-items: center; justify-content: space-between; }
.no {
  font-family: var(--mono); font-size: 11px; color: var(--cobalt);
  letter-spacing: 0.5px;
}
.name { margin: 3px 0 2px; font-family: var(--font-display); font-size: 15px; color: var(--ink); }
.meta { font-size: 12px; color: var(--dim); margin-bottom: 6px; }
.x { padding: 0 6px; font-size: 14px; }
</style>
