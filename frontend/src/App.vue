<script setup>
import { ref, shallowRef } from 'vue'
import AuthView from './views/AuthView.vue'
import KbView from './views/KbView.vue'
import ChatView from './views/ChatView.vue'
import TasksView from './views/TasksView.vue'

// 全局共享状态(响应式)
const token = ref(localStorage.getItem('docagent_token') || '')
const user = ref(JSON.parse(localStorage.getItem('docagent_user') || 'null'))
const currentView = ref('kb')
// KbView 选中库 → 传给 ChatView
const selectedKbId = ref(null)

const viewCache = shallowRef({})

function handleAuth(newToken, newUser) {
  token.value = newToken
  user.value = newUser
  localStorage.setItem('docagent_token', newToken)
  localStorage.setItem('docagent_user', JSON.stringify(newUser))
  currentView.value = 'kb'
}

function go(view) {
  if (view === 'chat' && !selectedKbId.value) {
    // 没选库则去知识库页选
    currentView.value = 'kb'
    return
  }
  currentView.value = view
}

function onSelectKb(id) {
  selectedKbId.value = id
  currentView.value = 'chat'
}

function logout() {
  token.value = ''
  user.value = null
  selectedKbId.value = null
  localStorage.removeItem('docagent_token')
  localStorage.removeItem('docagent_user')
  currentView.value = 'kb'
}
</script>

<template>
  <!-- 未登录 → 登录注册页 -->
  <AuthView v-if="!token" :key="'auth'" @auth="handleAuth" />

  <template v-else>
    <header class="topbar">
      <div class="brand">DocAgent<span> · 多智能体知识库问答</span></div>
      <nav class="nav">
        <button
          v-for="v in [
            { key: 'kb', label: '知识库' },
            { key: 'chat', label: '对话' },
            { key: 'tasks', label: '任务' },
          ]"
          :key="v.key"
          :class="['ghost', { active: currentView === v.key }]"
          @click="go(v.key)"
        >
          {{ v.label }}
        </button>
      </nav>
      <div class="spacer" />
      <span class="muted">{{ user?.email }}</span>
      <button class="ghost danger" @click="logout">退出</button>
    </header>

    <main class="page">
      <KbView v-if="currentView === 'kb'" @select-kb="onSelectKb" />
      <ChatView v-else-if="currentView === 'chat'" :kb-id="selectedKbId" />
      <TasksView v-else-if="currentView === 'tasks'" />
    </main>
  </template>
</template>
