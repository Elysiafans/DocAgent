// DocAgent 后端 API 客户端:纯 fetch,无 axios。
// token 存 localStorage;SSE 用 ReadableStream 逐帧解析。

const TOKEN_KEY = 'docagent_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

async function request(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (form) {
    body = form // FormData,不设 Content-Type(browser 带 boundary)
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(body)
  }
  const res = await fetch(path, { method, headers, body })
  if (res.status === 204) return null
  let data = null
  const text = await res.text()
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }
  if (!res.ok) {
    const detail = data && (data.detail || data.message)
    throw new Error(
      typeof detail === 'string' ? detail : (detail || `HTTP ${res.status}`)
    )
  }
  return data
}

// ---------- auth ----------
export const login = (email, password) =>
  request('/api/v1/auth/login', { method: 'POST', body: { email, password } })
export const register = (email, password) =>
  request('/api/v1/auth/register', { method: 'POST', body: { email, password } })
export const me = () => request('/api/v1/auth/me')
export const health = () => request('/api/v1/health')

// ---------- 知识库 ----------
export const listKbs = () => request('/api/v1/knowledge_bases')
export const createKb = (name, description = '') =>
  request('/api/v1/knowledge_bases', {
    method: 'POST',
    body: { name, description },
  })
export const deleteKb = (kbId) =>
  request(`/api/v1/knowledge_bases/${kbId}`, { method: 'DELETE' })
export const listDocs = (kbId) =>
  request(`/api/v1/knowledge_bases/${kbId}/documents`)
export const uploadDoc = (kbId, file) => {
  const form = new FormData()
  form.append('file', file)
  return request(`/api/v1/knowledge_bases/${kbId}/documents`, {
    method: 'POST',
    form,
  })
}
export const deleteDoc = (docId) =>
  request(`/api/v1/documents/${docId}`, { method: 'DELETE' })

// ---------- 可观测 ----------
export const listTaskRuns = () => request('/api/v1/task_runs')
export const getTaskRun = (runId) => request(`/api/v1/task_runs/${runId}`)

// ---------- 长期记忆 ----------
export const listMemories = () => request('/api/v1/memories')
export const addMemory = (content, kind = 'note') =>
  request('/api/v1/memories', { method: 'POST', body: { content, kind } })

// ---------- A2UI 卡片 ----------
export const renderCard = (kbId, question, route) =>
  request('/api/v1/a2ui/render', {
    method: 'POST',
    body: { kb_id: kbId, question, route: route || null },
  })

// ---------- SSE 多智能体对话 ----------
// onEvent(ev) 收到 {type: route|node|token|tool|tool_result|answer|sources|done|error,...}
export async function streamChat(kbId, question, route, onEvent) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch('/api/v1/chat/agent', {
    method: 'POST',
    headers,
    body: JSON.stringify({ kb_id: kbId, question, route: route || null }),
  })
  if (!res.ok || !res.body) {
    let msg = `HTTP ${res.status}`
    try {
      const j = await res.json()
      msg = j.detail || msg
    } catch { /* ignore */ }
    throw new Error(msg)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    // SSE 帧以空行分隔;兼容单 data: 行 + 空行
    let idx
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const frame = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      for (const line of frame.split('\n')) {
        if (!line.startsWith('data:')) continue
        const payload = line.slice(5).trim()
        if (!payload || payload === '[DONE]') continue
        try {
          onEvent(JSON.parse(payload))
        } catch { /* 忽略非 JSON 行 */ }
      }
    }
  }
}
