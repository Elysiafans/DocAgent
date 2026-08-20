<script setup>
import { ref, computed, onMounted } from 'vue'
import { listKbs, streamChat, renderCard } from '../api.js'
import MessageBubble from '../components/MessageBubble.vue'
import SourcePanel from '../components/SourcePanel.vue'
import EmptyState from '../components/EmptyState.vue'

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

// 最近一条助手消息的溯源(右侧来源栏)
const activeSources = computed(() => {
  for (let i = msgs.value.length - 1; i >= 0; i--) {
    const m = msgs.value[i]
    if (m.role === 'assistant' && m.sources && m.sources.length) return m.sources
  }
  return []
})

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
          <option v-for="kb in kbs" :key="kb.id" :value="kb.id">{{ kb.name }}</option>
        </select>
        <select v-model="route" style="max-width: 160px">
          <option v-for="r in ROUTES" :key="r.value" :value="r.value">{{ r.label }}</option>
        </select>
        <button :class="{ active: cardOpen }" @click="toggleCard">
          {{ cardLoading ? '生成中…' : cardOpen ? '关闭卡片' : '卡片视图' }}
        </button>
        <span class="muted">SSE 流式 · 多智能体编排</span>
      </div>
    </div>

    <div class="chat-main">
      <!-- 左:对话 -->
      <div class="conv-col">
        <div class="chat-log">
          <EmptyState
            v-if="msgs.length === 0 && !sending"
            title="向知识库提问"
            hint="示例:「总结最近上传的文档」「对比两个方案的优劣」。"
          />
          <MessageBubble v-for="(m, i) in msgs" :key="i" :msg="m" />

          <!-- 流式中 -->
          <div v-if="sending" class="msg assistant">
            <div class="bubble">
              <div class="meta mono">
                <span v-if="cur.route">route: {{ cur.route }}</span>
                <span v-if="cur.node">{{ NODE_LABEL[cur.node] || cur.node }}</span>
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

      <!-- 右:引用来源(≤900px 隐藏) -->
      <aside class="source-col">
        <SourcePanel v-if="activeSources.length" :sources="activeSources" />
        <EmptyState v-else title="暂无引用" hint="发起问答后,这里会展示回答的溯源脚注。" />
      </aside>
    </div>

    <!-- A2UI 卡片 JSON 预览 -->
    <div v-if="cardOpen" class="card">
      <h3>A2UI 卡片(协议渲染)</h3>
      <p v-if="cardLoading" class="muted">正在生成卡片(同步执行 agent 图)…</p>
      <p v-if="cardErr" class="err">{{ cardErr }}</p>
      <pre v-if="cardData" class="card-json">{{ JSON.stringify(cardData, null, 2) }}</pre>
    </div>
  </div>
</template>

<style scoped>
.chat-layout { display: flex; flex-direction: column; gap: 12px; height: calc(100vh - 120px); }
.controls .row { flex-wrap: wrap; }

.chat-main { flex: 1; min-height: 0; display: flex; gap: 16px; }
.conv-col { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 12px; }

.chat-log {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px 2px;
}
.msg { display: flex; }
.msg.assistant { justify-content: flex-start; }
.bubble {
  max-width: 86%;
  background: var(--surface);
  border: var(--hairline-w) solid var(--hairline);
  border-radius: var(--radius);
  padding: 12px 14px;
}
.meta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; font-size: 12px; color: var(--dim); }
.content { white-space: pre-wrap; word-break: break-word; }
.caret { color: var(--cobalt); animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }

.tools { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
.tool-chip {
  background: var(--paper);
  border: var(--hairline-w) solid var(--border);
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  color: var(--cobalt);
  width: fit-content;
}

.card-json {
  background: var(--paper);
  border: var(--hairline-w) solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
  max-height: 320px;
  overflow: auto;
  font-family: var(--mono);
  font-size: 12px;
}

.input-bar { display: flex; gap: 8px; align-items: flex-end; margin-bottom: 0; }
.input-bar textarea { flex: 1; }
.input-bar button { white-space: nowrap; }

/* 右侧来源栏 */
.source-col {
  width: 240px;
  flex-shrink: 0;
  border-left: var(--hairline-w) solid var(--hairline);
  padding-left: 16px;
  overflow-y: auto;
}
.source-col h5 {
  margin: 0 0 8px; font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.5px; color: var(--dim); font-weight: 600;
}

/* 窄屏:隐藏右侧来源栏(消息内 inline 来源保留) */
@media (max-width: 900px) {
  .source-col { display: none; }
}
</style>
