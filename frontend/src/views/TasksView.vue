<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { listTaskRuns, getTaskRun } from '../api.js'

const runs = ref([])
const selectedId = ref(null)
const detail = ref(null) // TaskRunOut with trace.events
const err = ref('')
let timer = null

const TYPE_LABEL = { agent: '多智能体对话', ingestion: '文档入库' }
const STATUS_CLS = { success: 'ok', failed: 'err', running: 'phase' }

const EVENT_ICON = {
  route: '🧭',
  node: '⛓️',
  token: '✏️',
  tool: '🔧',
  tool_result: '📥',
  answer: '💬',
  sources: '📚',
  done: '✅',
  error: '❌',
}

function fmt(t) {
  if (!t) return '—'
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  return d.toLocaleString()
}

function fmtShort(t) {
  if (!t) return '—'
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

async function load() {
  try {
    runs.value = await listTaskRuns()
  } catch (e) {
    err.value = e.message
  }
}

async function select(id) {
  selectedId.value = id
  detail.value = null
  try {
    detail.value = await getTaskRun(id)
  } catch (e) {
    err.value = e.message
  }
}

function evText(ev) {
  switch (ev.type) {
    case 'token':
      return ev.content
    case 'tool':
      return `${ev.name}(${JSON.stringify(ev.args || {})})`
    case 'tool_result':
      return ev.content
    case 'route':
      return `route → ${ev.route}`
    case 'node':
      return ev.node
    case 'answer':
      return ev.content
    case 'error':
      return ev.message
    case 'done':
      return `run #${ev.run_id} · conv #${ev.conversation_id}`
    default:
      return JSON.stringify(ev)
  }
}

onMounted(() => {
  load()
  // 对话进行时自动刷新
  timer = setInterval(load, 3000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="tasks-layout">
    <!-- 左:任务列表 -->
    <section class="card">
      <h3>
        任务运行
        <button class="ghost" style="margin-left: auto" @click="load">刷新</button>
      </h3>
      <p v-if="err" class="err">{{ err }}</p>
      <div v-if="runs.length === 0" class="empty">暂无任务。</div>
      <div class="list" style="max-height: 62vh; overflow-y: auto">
        <div
          v-for="r in runs"
          :key="r.id"
          :class="['item', { selected: r.id === selectedId }]"
          @click="select(r.id)"
        >
          <div class="name">
            {{ TYPE_LABEL[r.type] || r.type }} #{{ r.id }}
            <span class="sub">
              {{ fmtShort(r.started_at) }}
              <template v-if="r.finished_at"> → {{ fmtShort(r.finished_at) }}</template>
            </span>
          </div>
          <span :class="['badge', STATUS_CLS[r.status]]">{{ r.status }}</span>
          <div v-if="r.error" class="sub err" style="flex-basis: 100%">{{ r.error }}</div>
        </div>
      </div>
    </section>

    <!-- 右:trace 时间线 -->
    <section class="card">
      <template v-if="selectedId">
        <h3>
          运行 #{{ selectedId }} · trace
          <span v-if="detail" class="muted" style="margin-left: auto; font-size: 12px">
            {{ fmt(detail.started_at) }} → {{ fmt(detail.finished_at) }}
          </span>
        </h3>

        <div v-if="!detail" class="empty">加载中…</div>

        <div v-else class="timeline">
          <div v-if="!detail.trace || !detail.trace.events || detail.trace.events.length === 0" class="empty">
            无事件(该运行无 trace)。
          </div>
          <div
            v-for="(ev, i) in (detail.trace?.events || [])"
            :key="i"
            class="tl-item"
          >
            <div class="tl-dot">{{ EVENT_ICON[ev.type] || '·' }}</div>
            <div class="tl-body">
              <div class="tl-head">
                <span class="badge phase">{{ ev.type }}</span>
                <span v-if="ev.node" class="mono muted">{{ ev.node }}</span>
              </div>
              <div class="tl-text mono">{{ evText(ev) }}</div>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="empty">← 选择一条任务查看 trace 事件时间线</div>
    </section>
  </div>
</template>

<style scoped>
.tasks-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  align-items: start;
}
.tasks-layout h3 { display: flex; align-items: center; gap: 8px; }
.tasks-layout .item { cursor: pointer; flex-wrap: wrap; }
.tasks-layout .item:hover { border-color: var(--border-hover); }

.timeline { display: flex; flex-direction: column; }
.tl-item {
  display: flex;
  gap: 10px;
  padding: 6px 0;
  border-left: 1px solid var(--border);
  margin-left: 8px;
}
.tl-dot {
  width: 22px;
  height: 22px;
  margin-left: -12px;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  flex-shrink: 0;
}
.tl-body { flex: 1; min-width: 0; }
.tl-head { display: flex; gap: 6px; align-items: center; margin-bottom: 2px; }
.tl-text {
  color: var(--text-dim);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 90px;
  overflow-y: auto;
}
</style>
