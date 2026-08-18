<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import {
  listKbs,
  createKb,
  deleteDoc,
  deleteKb,
  listDocs,
  uploadDoc,
} from '../api.js'

const emit = defineEmits(['select-kb'])

const kbs = ref([])
const selectedId = ref(null)
const name = ref('')
const creating = ref(false)
const err = ref('')
const msg = ref('')

const docs = ref([])
const uploading = ref(false)
const fileInput = ref(null)
let pollTimer = null

const STATUS_LABEL = {
  uploading: '上传中',
  parsing: '解析中',
  chunking: '分块中',
  embedding: '向量化',
  ready: '就绪',
  failed: '失败',
}
const STATUS_CLS = {
  ready: 'ok',
  failed: 'err',
}

async function load() {
  try {
    kbs.value = await listKbs()
  } catch (e) {
    err.value = e.message
  }
}

async function selectKb(id) {
  selectedId.value = id
  err.value = ''
  stopPoll()
  await loadDocs()
}

async function loadDocs() {
  if (!selectedId.value) return
  try {
    docs.value = await listDocs(selectedId.value)
  } catch (e) {
    err.value = e.message
  }
}

async function create() {
  if (!name.value.trim()) return
  creating.value = true
  err.value = ''
  try {
    const kb = await createKb(name.value.trim())
    name.value = ''
    await load()
    await selectKb(kb.id)
  } catch (e) {
    err.value = e.message
  } finally {
    creating.value = false
  }
}

function onPickFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  upload(file)
  e.target.value = ''
}

async function upload(file) {
  uploading.value = true
  err.value = ''
  try {
    await uploadDoc(selectedId.value, file)
    await loadDocs()
    startPoll() // 轮询直到所有文档终态
  } catch (e) {
    err.value = e.message
  } finally {
    uploading.value = false
  }
}

function startPoll() {
  stopPoll()
  pollTimer = setInterval(async () => {
    await loadDocs()
    const pending = docs.value.filter((d) =>
      ['uploading', 'parsing', 'chunking', 'embedding'].includes(d.status)
    )
    if (pending.length === 0) stopPoll()
  }, 1500)
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function removeDoc(id) {
  try {
    await deleteDoc(id)
    await loadDocs()
  } catch (e) {
    err.value = e.message
  }
}

async function removeKb(id) {
  if (!confirm('删除知识库及其全部文档?此操作不可恢复。')) return
  try {
    await deleteKb(id)
    if (selectedId.value === id) {
      selectedId.value = null
      docs.value = []
      stopPoll()
    }
    await load()
  } catch (e) {
    err.value = e.message
  }
}

function goChat() {
  if (!selectedId.value) return
  emit('select-kb', selectedId.value)
}

onMounted(load)
onBeforeUnmount(stopPoll)
</script>

<template>
  <div class="kb-layout">
    <!-- 左:知识库列表 -->
    <section class="card kb-list-card">
      <h3>知识库</h3>
      <form class="row" @submit.prevent="create">
        <input
          v-model="name"
          class="grow"
          type="text"
          placeholder="新建知识库名称"
        />
        <button class="primary" type="submit" :disabled="creating || !name.trim()">
          {{ creating ? '…' : '新建' }}
        </button>
      </form>

      <p v-if="err" class="err">{{ err }}</p>
      <p v-if="msg" class="ok">{{ msg }}</p>

      <div v-if="kbs.length === 0" class="empty">
        暂无知识库,在上方新建一个。
      </div>

      <div class="list kb-list">
        <div
          v-for="kb in kbs"
          :key="kb.id"
          :class="['item', { selected: kb.id === selectedId }]"
          @click="selectKb(kb.id)"
        >
          <div class="name">{{ kb.name }}</div>
          <div class="sub">{{ kb.chunk_strategy }} · {{ kb.chunk_size }}字</div>
          <button class="ghost danger" title="删除知识库" @click.stop="removeKb(kb.id)">×</button>
        </div>
      </div>
    </section>

    <!-- 右:选中库的文档 -->
    <section class="card doc-card">
      <template v-if="selectedId">
        <h3>
          文档
          <button class="ghost" style="margin-left: auto" @click="goChat">
            去问答 →
          </button>
        </h3>

        <div class="row" style="margin-bottom: 12px">
          <input
            ref="fileInput"
            type="file"
            style="display: none"
            accept=".txt,.md,.markdown,.pdf,.docx"
            @change="onPickFile"
          />
          <button
            class="primary"
            :disabled="uploading"
            @click="fileInput?.click()"
          >
            {{ uploading ? '上传中…' : '上传文档' }}
          </button>
          <span class="muted">支持 txt / md / pdf / docx</span>
        </div>

        <div v-if="docs.length === 0" class="empty">该库还没有文档。</div>

        <div class="list">
          <div v-for="d in docs" :key="d.id" class="item">
            <div class="name">
              {{ d.name }}
              <span class="sub">· {{ d.size }}B · {{ d.chunk_count }} 块</span>
            </div>
            <span :class="['badge', STATUS_CLS[d.status]]">
              <span v-if="['uploading','parsing','chunking','embedding'].includes(d.status)" class="spin" />
              {{ STATUS_LABEL[d.status] || d.status }}{{ d.progress ? ` ${d.progress}%` : '' }}
            </span>
            <button class="ghost danger" @click="removeDoc(d.id)">删除</button>
          </div>
        </div>
      </template>
      <div v-else class="empty">← 左侧选择一个知识库</div>
    </section>
  </div>
</template>

<style scoped>
.kb-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  align-items: start;
}
.kb-list-card h3,
.doc-card h3 {
  display: flex;
  align-items: center;
}
.kb-list {
  margin-top: 12px;
  max-height: 60vh;
  overflow-y: auto;
}
.kb-list .item {
  cursor: pointer;
}
.kb-list .item:hover {
  border-color: var(--border-hover);
}
</style>
