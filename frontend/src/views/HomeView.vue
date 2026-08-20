<script setup>
// 首页导航:未登录首屏。入口按钮已登录直接进入,未登录先去登录(由 App.vue 处理)。
defineProps({ authed: { type: Boolean, default: false } })
defineEmits(['enter', 'login'])

const entries = [
  {
    key: 'kb',
    icon: '📚',
    title: '知识库管理',
    desc: '上传 PDF / DOCX / Markdown / TXT,自动解析分块、嵌入入库,构建稠密 + 稀疏混合检索的 RAG 知识库。',
  },
  {
    key: 'chat',
    icon: '💬',
    title: '智能对话',
    desc: 'Supervisor 编排 rag / summary / compare / utility 四类智能体流式作答,路由决策、工具调用、引用溯源实时可见。',
  },
  {
    key: 'tasks',
    icon: '🧩',
    title: '任务中心',
    desc: '每次问答都是一条可观测任务:agent 路由、节点执行、工具调用、token 流全程留痕,便于排查与复盘。',
  },
]

const stack = ['FastAPI', 'LangGraph', 'Qdrant', 'PostgreSQL', 'Vue 3', 'SSE 流式', 'MCP', 'A2A']
</script>

<template>
  <div class="home">
    <header class="home-top">
      <div class="brand">DocAgent<span> · 多智能体知识库问答</span></div>
      <div class="spacer" />
      <button v-if="authed" class="ghost" @click="$emit('enter', 'kb')">进入控制台 →</button>
      <button v-else class="primary" @click="$emit('login')">登录 / 注册</button>
    </header>

    <main class="page home-body">
      <section class="hero">
        <h1>多智能体知识库问答平台</h1>
        <p class="muted hero-sub">
          上传文档 → 解析分块入库 → 混合检索 + 重排 → <b>Supervisor</b> 编排四类智能体流式作答。
          原生支持 <b>MCP</b> / <b>A2A</b> / <b>A2UI</b> / <b>Skills</b> / <b>长期记忆</b> 等 Agent 互操作协议。
        </p>
        <div class="hero-actions">
          <button
            v-for="e in entries"
            :key="e.key"
            class="primary"
            @click="$emit('enter', e.key)"
          >
            {{ e.icon }} {{ e.title }}
          </button>
        </div>
      </section>

      <section class="grid">
        <div v-for="e in entries" :key="e.key" class="card">
          <h3>{{ e.icon }} {{ e.title }}</h3>
          <p class="muted">{{ e.desc }}</p>
          <button class="ghost" @click="$emit('enter', e.key)">进入 →</button>
        </div>
      </section>

      <section class="card tech">
        <h3>技术栈</h3>
        <div class="chips">
          <span v-for="t in stack" :key="t" class="badge">{{ t }}</span>
        </div>
        <p class="muted mono small">
          完整 README 与架构说明:
          <a href="https://github.com/Elysiafans/DocAgent" target="_blank" rel="noopener">
            github.com/Elysiafans/DocAgent
          </a>
        </p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.home {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
.home-top {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 20px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
}
.home-body {
  padding-top: 44px;
  padding-bottom: 48px;
}
.hero {
  text-align: center;
  padding: 12px 0 36px;
}
.hero h1 {
  margin: 0 0 12px;
  font-size: 30px;
  letter-spacing: 0.5px;
}
.hero-sub {
  max-width: 720px;
  margin: 0 auto 24px;
  font-size: 15px;
}
.hero-sub b { color: var(--text); }
.hero-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}
.hero-actions button {
  padding: 10px 20px;
  font-size: 14px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.grid .card h3 { margin-bottom: 8px; }
.grid .card p { min-height: 66px; margin-bottom: 12px; }
.tech h3 { margin-bottom: 10px; }
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}
.small { margin: 0; }
</style>
