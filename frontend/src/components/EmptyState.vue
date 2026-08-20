<script setup>
defineProps({
  title: { type: String, default: '这里还空着' },
  hint: { type: String, default: '' },
})
</script>

<template>
  <div class="empty-state">
    <p class="title">{{ title }}</p>
    <p v-if="hint" class="hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.empty-state { text-align: center; color: var(--dim); padding: 28px 0; }
.empty-state .title { margin: 0 0 4px; font-size: 14px; }
.empty-state .hint { margin: 0; font-size: 12.5px; opacity: 0.85; }
</style>
