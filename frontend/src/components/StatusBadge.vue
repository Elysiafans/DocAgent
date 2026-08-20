<script setup>
defineProps({
  status: { type: String, default: '' },
  label: { type: String, default: '' },
  progress: { type: [Number, String], default: '' },
})

const LABELS = {
  uploading: '上传中',
  parsing: '解析中',
  chunking: '分块中',
  embedding: '向量化',
  ready: '就绪',
  failed: '失败',
  success: '成功',
  running: '运行中',
}
const CLS = { ready: 'ok', success: 'ok', failed: 'err', running: 'phase' }
const IN_PROGRESS = ['uploading', 'parsing', 'chunking', 'embedding', 'running']
</script>

<template>
  <span :class="['badge', CLS[status] || '']">
    <span v-if="IN_PROGRESS.includes(status)" class="spin" />
    {{ label || LABELS[status] || status }}{{ progress ? ` ${progress}%` : '' }}
  </span>
</template>
