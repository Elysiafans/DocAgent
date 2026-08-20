<script setup>
import { ref } from 'vue'
import HomeView from './views/HomeView.vue'
import AuthView from './views/AuthView.vue'
import KbView from './views/KbView.vue'
import ChatView from './views/ChatView.vue'
import TasksView from './views/TasksView.vue'

// 全局共享状态(响应式)
const token = ref(localStorage.getItem('docagent_token') || '')
const user = ref(JSON.parse(localStorage.getItem('docagent_user') || 'null'))
// 视图:home(首页导航)| auth(登录注册)| kb | chat | tasks
const currentView = ref(token.value ? 'kb' : 'home')
// 首页入口:未登录先去登录,登录后回到该入口
const pendingView = ref('kb')
// KbView 选中库 → 传给 ChatView
const selectedKbId = ref(null)

function handleAuth(newToken, newUser) {
  token.value = newToken
  user.value = newUser
  localStorage.setItem('docagent_token', newToken)
  localStorage.setItem('docagent_user', JSON.stringify(newUser))
  const target = pendingView.value
  pendingView.value = 'kb'
  go(target)
}

// 首页入口:已登录直接进;未登录先去登录
function onEnter(view) {
  if (token.value) {
    go(view)
  } else {
    pendingView.value = view
    currentView.value = 'auth'
  }
}

function go(view) {
  if (view === 'chat' && !selectedKbId.value) {
    // 没选库则去知识库页选
    currentView.value = 'kb'
    return
  }
  currentView.value = view
}

function goHome() {
  currentView.value = 'home'
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
  currentView.value = 'home'
}
</script>

<template>
  <!-- 首页导航(未登录首屏;登录后也可通过顶栏「首页」返回) -->
  <HomeView
    v-if="currentView === 'home'"
    :authed="!!token"
    @enter="onEnter"
    @login="go('auth')"
  />

  <!-- 登录 / 注册 -->
  <AuthView v-else-if="currentView === 'auth'" :key="'auth'" @auth="handleAuth" @back="goHome" />

  <!-- 已登录主界面 -->
  <template v-else>
    <header class="topbar">
      <div class="brand">DocAgent<span> · 多智能体知识库问答</span></div>
      <nav class="nav">
        <button
          v-for="v in [
            { key: 'home', label: '首页' },
            { key: 'kb', label: '知识库' },
            { key: 'chat', label: '对话' },
            { key: 'tasks', label: '任务' },
          ]"
          :key="v.key"
          :class="['ghost', { active: currentView === v.key }]"
          @click="v.key === 'home' ? goHome() : go(v.key)"
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
