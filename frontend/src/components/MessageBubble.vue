<script setup>
import { computed } from 'vue'
import SourcePanel from './SourcePanel.vue'

const props = defineProps({
  msg: { type: Object, required: true }, // { role, content, sources, convId, runId }
})

const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  )

// 助手消息:转义后把 [n] 包成上标引用
const rendered = computed(() =>
  props.msg.role === 'assistant'
    ? esc(props.msg.content).replace(/\[(\d+)\]/g, '<sup class="cite">[$1]</sup>')
    : null
)
</script>

<template>
  <div :class="['msg', msg.role]">
    <div class="bubble">
      <div v-if="msg.role === 'assistant'" class="meta mono">
        <span v-if="msg.runId" class="dim">run #{{ msg.runId }}</span>
        <span v-if="msg.convId" class="dim">会话 #{{ msg.convId }}</span>
      </div>
      <p v-if="msg.role === 'user'" class="content">{{ msg.content }}</p>
      <div v-else class="content" v-html="rendered" />
      <SourcePanel
        v-if="msg.role === 'assistant' && msg.sources && msg.sources.length"
        :sources="msg.sources"
        inline
      />
    </div>
  </div>
</template>

<style scoped>
.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.bubble {
  max-width: 86%;
  background: var(--surface);
  border: var(--hairline-w) solid var(--hairline);
  border-radius: var(--radius);
  padding: 10px 14px;
}
.msg.user .bubble { background: var(--cobalt); border-color: var(--cobalt); }
.msg.user .content { color: #fff; margin: 0; }
.content { margin: 0; white-space: pre-wrap; word-break: break-word; }
.content :deep(.cite) { color: var(--cobalt); font-weight: 700; }
.msg.user .content :deep(.cite) { color: #fff; }
.meta { display: flex; gap: 6px; margin-bottom: 6px; font-size: 11px; }
</style>
