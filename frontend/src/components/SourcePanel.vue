<script setup>
defineProps({
  sources: { type: Array, default: () => [] },
  inline: { type: Boolean, default: false },
})
</script>

<template>
  <div :class="['sources', { inline }]">
    <h5>引用来源 · {{ sources.length }}</h5>
    <div v-for="(s, j) in sources" :key="j" class="src">
      <span class="idx mono">[{{ j + 1 }}]</span>
      <div class="body">
        <div class="row1">
          <span class="doc">{{ s.doc_name || '文档' }}</span>
          <span class="mono dim">score {{ s.score }}</span>
        </div>
        <div class="text">{{ s.content }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sources { border-top: var(--hairline-w) dashed var(--hairline); margin-top: 10px; padding-top: 8px; }
.sources.inline { margin-top: 8px; }
.sources h5 {
  margin: 0 0 6px; font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.5px; color: var(--dim); font-weight: 600;
}
.src { display: flex; gap: 8px; border: var(--hairline-w) solid var(--hairline); background: var(--paper); border-radius: var(--radius-sm); padding: 6px 8px; margin-bottom: 6px; }
.idx { color: var(--cobalt); font-weight: 700; font-size: 11px; padding-top: 1px; }
.body { min-width: 0; }
.row1 { display: flex; align-items: baseline; gap: 8px; }
.doc { font-weight: 600; font-size: 12.5px; }
.dim { color: var(--dim); font-size: 11px; }
.text { margin-top: 2px; font-size: 12px; color: var(--dim); max-height: 60px; overflow-y: auto; white-space: pre-wrap; }
</style>
