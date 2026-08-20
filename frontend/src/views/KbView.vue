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
import ArchiveCard from '../components/ArchiveCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'

const emit = defineEmits(['select-kb'])

const kbs = ref([])
const selectedId = ref(null)
const name = ref('')
const creating = ref(false)
const err = ref('')

const docs = ref([])
const uploading = ref(false)
const fileInput = ref(null)
let pollTimer = null

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
    err.value = '上传失败:解析失败。支持 txt / md / pdf / docx,重试或换格式。'
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

      <div v-if="kbs.length === 0">
        <EmptyState title="还没有归档文献" hint="上传第一份 PDF / Markdown,开始建立你的档案库。" />
      </div>
      <div v-else class="list kb-list">
        <ArchiveCard
          v-for="(kb, i) in kbs"
          :key="kb.id"
          :no="`KB-${String(i + 1).padStart(2, '0')}`"
          :name="kb.name"
          :meta="`${kb.chunk_strategy} · ${kb.chunk_size} 字`"
          :selected="kb.id === selectedId"
          removable
          @select="selectKb(kb.id)"
          @remove="removeKb(kb.id)"
        />
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

        <div v-if="docs.length === 0">
          <EmptyState title="该库还没有文档" hint="点击上方「上传文档」开始。" />
        </div>

        <div class="list">
          <div v-for="d in docs" :key="d.id" class="item">
            <div class="name">
              {{ d.name }}
              <span class="sub">· {{ d.size }}B · {{ d.chunk_count }} 块</span>
            </div>
            <StatusBadge :status="d.status" :progress="d.progress" />
            <button class="ghost danger" @click="removeDoc(d.id)">删除</button>
          </div>
        </div>
      </template>
      <div v-else>
        <EmptyState title="选择一个知识库" hint="← 从左侧选择一个库查看其文档。" />
      </div>
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
</style>
