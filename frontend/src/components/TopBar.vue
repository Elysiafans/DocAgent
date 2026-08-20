<script setup>
defineProps({
  authed: { type: Boolean, default: false },
  active: { type: String, default: '' },
  email: { type: String, default: '' },
})
defineEmits(['nav', 'login', 'logout'])

const NAVS = [
  { key: 'home', label: '首页' },
  { key: 'kb', label: '知识库' },
  { key: 'chat', label: '对话' },
  { key: 'tasks', label: '任务' },
]
</script>

<template>
  <header class="tb">
    <button class="brand" @click="$emit('nav', 'home')"><b>DA</b>DocAgent</button>
    <nav v-if="authed" class="nv">
      <button
        v-for="n in NAVS"
        :key="n.key"
        :class="['nv-btn', { on: active === n.key }]"
        @click="$emit('nav', n.key)"
      >
        {{ n.label }}
      </button>
    </nav>
    <span class="sp" />
    <span v-if="authed" class="muted who">{{ email }}</span>
    <button v-if="authed" class="ghost danger" @click="$emit('logout')">退出</button>
    <button v-else class="btn-solid" @click="$emit('login')">登录 / 注册</button>
  </header>
</template>

<style scoped>
.tb {
  display: flex; align-items: center; gap: 16px;
  padding: 10px 20px;
  background: var(--surface);
  border-bottom: var(--hairline-w) solid var(--hairline);
  position: sticky; top: 0; z-index: 10;
}
.brand {
  display: inline-flex; align-items: center; gap: 7px;
  background: none; border: none; padding: 0;
  font-family: var(--font-display);
  font-size: 16px; font-weight: 700; color: var(--ink);
}
.brand:hover { background: none; border: none; color: var(--ink); }
.brand b {
  display: inline-flex; width: 20px; height: 20px;
  align-items: center; justify-content: center;
  border: var(--hairline-w) solid var(--cobalt);
  color: var(--cobalt); border-radius: var(--radius-sm);
  font-size: 10px; font-weight: 600;
}
.nv { display: flex; gap: 4px; flex: 1; }
.nv-btn {
  background: none; border: none; color: var(--dim);
  font-size: 13px; padding: 4px 10px; border-radius: var(--radius-sm);
}
.nv-btn:hover { border: none; color: var(--ink); background: var(--cobalt-tint); }
.nv-btn.on { color: var(--cobalt); font-weight: 600; }
.nv-btn.on:hover { color: var(--cobalt); }
.sp { flex: 1; }
.who { font-size: 13px; }
.btn-solid {
  background: var(--cobalt-strong); border-color: var(--cobalt-strong);
  color: #fff; font-weight: 600;
}
.btn-solid:hover { background: var(--cobalt); border-color: var(--cobalt); }
</style>
