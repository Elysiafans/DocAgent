<script setup>
import { ref } from 'vue'
import { login, register, me, setToken } from '../api.js'

const emit = defineEmits(['auth', 'back'])

const mode = ref('login') // login | register
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    let token
    if (mode.value === 'login') {
      token = (await login(email.value, password.value)).access_token
    } else {
      // register 返回 UserOut(无 token),注册成功后走登录
      await register(email.value, password.value)
      token = (await login(email.value, password.value)).access_token
    }
    setToken(token)
    const user = await me() // 拿 email/id 显示到顶栏
    emit('auth', token, user)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-wrap">
    <div class="auth-box">
      <button class="ghost back" @click="$emit('back')">← 返回首页</button>
      <div class="card auth-card">
        <div class="auth-brand">DocAgent</div>
      <p class="muted auth-sub">多智能体知识库问答平台 · 登录以继续</p>

      <div class="row auth-tabs">
        <button
          :class="['grow', { active: mode === 'login' }]"
          @click="mode = 'login'"
        >
          登录
        </button>
        <button
          :class="['grow', { active: mode === 'register' }]"
          @click="mode = 'register'"
        >
          注册
        </button>
      </div>

      <form @submit.prevent="submit">
        <div class="field">
          <label>邮箱</label>
          <input
            v-model="email"
            type="email"
            required
            placeholder="you@example.com"
            autocomplete="email"
          />
        </div>
        <div class="field">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            required
            minlength="6"
            placeholder="至少 6 位"
            autocomplete="current-password"
          />
        </div>

        <p v-if="error" class="err">{{ error }}</p>

        <button
          class="primary auth-submit"
          type="submit"
          :disabled="loading || !email || !password"
        >
          {{ loading ? '提交中…' : mode === 'login' ? '登录' : '注册并登录' }}
        </button>
      </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 20px;
}
.auth-box {
  width: 100%;
  max-width: 380px;
}
.auth-box .back {
  margin-bottom: 8px;
  color: var(--text-dim);
}
.auth-card {
  width: 100%;
  padding: 28px 24px;
}
.auth-brand {
  font-size: 26px;
  font-weight: 700;
  color: var(--accent);
  text-align: center;
}
.auth-sub {
  text-align: center;
  margin: 4px 0 20px;
}
.auth-tabs {
  margin-bottom: 16px;
}
.auth-tabs button {
  padding: 8px;
  font-size: 14px;
}
.auth-submit {
  width: 100%;
  padding: 10px;
  font-size: 14px;
}
</style>
