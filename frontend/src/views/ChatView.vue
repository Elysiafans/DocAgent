<script setup>
import { ref, onMounted } from 'vue'
import { listKbs, streamChat, renderCard } from '../api.js'

const props = defineProps({
  kbId: { type: [Number, String], default: null },
})

const kbs = ref([])
const selectedKbId = ref(props.kbId ? Number(props.kbId) : null)
const route = ref('') // '' = auto, 其余 rag/summary/compare/utility
const question = ref('')
const sending = ref(false)
const msgs = ref([]) // {role, content, sources, runId, convId}
// 当前流式累积
const cur = ref({ content: '', sources: [], route: '', node: '', tools: [] })
const err = ref('')

const cardOpen = ref(false)
const cardLoading = ref(false)
const cardData = ref(null)
const cardErr = ref('')

const ROUTES = [
  { value: '', label: '自动路由' },
  { value: 'rag', label: '知识库问答' },
  { value: 'summary', label: '文档总结' },
  { value: 'compare', label: '对比分析' },
  { value: 'utility', label: '实用工具' },
]

const NODE_LABEL = {
  route: '路由决策',
  rag_agent: 'RAG 检索',
  summary_agent: '总结',
  compare_agent: '对比',
  utility_agent: '工具',
  supervisor: '编排',
  end: '完成',
  tools: '工具调用',
}

onMounted(async () => {
  try {
    kbs.value = await listKbs()
    if (!selectedKbId.value && kbs.value.length > 0) selectedKbId.value = kbs.value[0].id
  } catch (e) {
    err.value = e.message
  }
})

function resetCur() {
  cur.value = { content: '', sources: [], route: '', node: '', tools: [] }
}

async function send() {
  const q = question.value.trim()
  if (!q || !selectedKbId.value || sending.value) return
  err.value = ''
  msgs.value.push({ role: 'user', content: q })
  question.value = ''
  resetCur()
  sending.value = true
  try {
    await streamChat(selectedKbId.value, q, route.value, (ev) => {
      switch (ev.type) {
        case 'route':
          cur.value.route = ev.route
          break
        case 'node':
          cur.value.node = ev.node
          break
        case 'token':
          cur.value.content += ev.content
          break
        case 'tool':
          cur.value.tools.push({ name: ev.name, args: ev.args })
          break
        case 'answer':
          cur.value.content = ev.content
          break
        case 'sources':
          cur.value.sources = ev.sources || []
          break
        case 'done':
          finalize(ev.answer || cur.value.content, ev.sources || cur.value.sources, ev.conversation_id, ev.run_id)
          break
        case 'error':
          err.value = ev.message
          if (cur.value.content) finalize(cur.value.content, cur.value.sources, null, null)
          break
      }
    })
  } catch (e) {
    err.value = e.message
    if (cur.value.content) finalize(cur.value.content, cur.value.sources, null, null)
  } finally {
    sending.value = false
  }
}

function finalize(content, sources, convId, runId) {
  msgs.value.push({
    role: 'assistant',
    content,
    sources: sources || [],
    convId,
    runId,
  })
  resetCur()
}

async function toggleCard() {
  if (!selectedKbId.value) return
  if (cardOpen.value) {
    cardOpen.value = false
    return
  }
  cardOpen.value = true
  cardLoading.value = true
  cardErr.value = ''
  cardData.value = null
  const q = msgs.value[msgs.value.length - 1]?.role === 'user'
    ? msgs.value[msgs.value.length - 1].content
    : question.value
  if (!q.trim()) {
    cardErr.value = '请先输入问题'
    cardLoading.value = false
    return
  }
  try {
    cardData.value = await renderCard(selectedKbId.value, q.trim(), route.value)
  } catch (e) {
    cardErr.value = e.message
  } finally {
    cardLoading.value = false
  }
}
</script>

<template>
  <div class="chat-layout">
    <!-- 顶部控制条 -->
    <div class="card controls">
      <div class="row">
        <select v-model="selectedKbId" class="grow" style="max-width: 240px">
          <option v-for="kb in kbs" :key="kb.id" :value="kb.id">
            {{ kb.name }}
          </option>
        </select>
        <select v-model="route" style="max-width: 160px">
          <option v-for="r in ROUTES" :key="r.value" :value="r.value">
            {{ r.label }}
          </option>
        </select>
        <button :class="{ active: cardOpen }" @click="toggleCard">
          {{ cardLoading ? '生成中…' : cardOpen ? '关闭卡片' : '卡片视图' }}
        </button>
        <span class="muted">SSE 流式 · 多智能体编排</span>
      </div>
    </div>

    <!-- 对话区 -->
    <div class="chat-log">
      <div v-if="msgs.length === 0 && !sending" class="empty">
        向你的知识库提问吧。示例:「总结最近上传的文档」「对比两个方案的优劣」。
      </div>

      <template v-for="(m, i) in msgs" :key="i">
        <div class="msg user">
          <div class="bubble">{{ m.content }}</div>
        </div>
        <div class="msg assistant">
          <div class="bubble">
            <div class="stream-meta" v-if="m.convId">
              <span class="badge ok">run #{{ m.runId }}</span>
              <span class="badge">会话 #{{ m.convId }}</span>
            </div>
            <div class="content">{{ m.content }}</div>

            <!-- 溯源:编号与回答中的 [i] 对应 -->
            <div v-if="m.sources && m.sources.length" class="sources">
              <div class="sources-title">溯源 {{ m.sources.length }} 条</div>
              <div v-for="(s, j) in m.sources" :key="j" class="source">
                <span class="badge">[{{ j + 1 }}]</span>
                <span class="src-name">{{ s.doc_name || '文档' }}</span>
                <span class="muted mono">score {{ s.score }}</span>
                <div class="src-text">{{ s.content }}</div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- 流式中 -->
      <div v-if="sending" class="msg assistant">
        <div class="bubble">
          <div class="stream-meta">
            <span v-if="cur.route" class="badge route">route: {{ cur.route }}</span>
            <span v-if="cur.node" class="badge phase">
              {{ NODE_LABEL[cur.node] || cur.node }}
            </span>
            <span class="spin" style="margin-left: 4px" />
          </div>

          <div v-if="cur.tools.length" class="tools">
            <div v-for="(t, j) in cur.tools" :key="j" class="tool-chip mono">
              🔧 {{ t.name }}<span v-if="t.args && t.args.query">: "{{ t.args.query }}"</span>
            </div>
          </div>

          <div class="content">{{ cur.content }}<span class="caret">▍</span></div>
        </div>
      </div>

      <p v-if="err" class="err" style="padding: 4px 8px">{{ err }}</p>
    </div>

    <!-- A2UI 卡片 JSON 预览 -->
    <div v-if="cardOpen" class="card">
      <h3>A2UI 卡片(D6 协议渲染)</h3>
      <p v-if="cardLoading" class="muted">正在生成卡片(同步执行 agent 图)…</p>
      <p v-if="cardErr" class="err">{{ cardErr }}</p>
      <pre v-if="cardData" class="card-json">{{ JSON.stringify(cardData, null, 2) }}</pre>
    </div>

    <!-- 输入 -->
    <form class="card input-bar" @submit.prevent="send">
      <textarea
        v-model="question"
        rows="1"
        placeholder="输入问题,Enter 发送,Shift+Enter 换行"
        @keydown.enter.exact.prevent="send"
      />
      <button
        class="primary"
        type="submit"
        :disabled="sending || !selectedKbId || !question.trim()"
      >
        {{ sending ? '生成中…' : '发送' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.chat-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: calc(100vh - 120px);
}
.controls .row { flex-wrap: wrap; }

.chat-log {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px 2px;
}
.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }

.bubble {
  max-width: 86%;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
}
.msg.user .bubble {
  background: var(--accent-strong);
  border-color: var(--accent-strong);
}
.msg.user .bubble .content { color: #fff; }

.stream-meta {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.content { white-space: pre-wrap; word-break: break-word; }
.caret { color: var(--accent); animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }

.tools { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
.tool-chip {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 8px;
  color: var(--purple);
  width: fit-content;
}

.sources { margin-top: 12px; border-top: 1px dashed var(--border); padding-top: 8px; }
.sources-title { font-size: 12px; color: var(--text-dim); margin-bottom: 6px; }
.source {
  border: 1px solid var(--border);
  background: var(--bg);
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 6px;
}
.src-name { font-weight: 600; margin: 0 8px; }
.src-text {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-dim);
  max-height: 60px;
  overflow-y: auto;
  white-space: pre-wrap;
}

.card-json {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  max-height: 320px;
  overflow: auto;
  font-family: var(--mono);
  font-size: 12px;
}

.input-bar { display: flex; gap: 8px; align-items: flex-end; margin-bottom: 0; }
.input-bar textarea { flex: 1; }
.input-bar button { white-space: nowrap; }
</style>
