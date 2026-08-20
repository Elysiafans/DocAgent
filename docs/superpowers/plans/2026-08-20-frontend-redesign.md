# DocAgent 前端重新制作(方向 B「实验室档案」)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把前端从"手写深色 CSS + 大视图"重做为"设计 token + 组件化 + 纸本钴蓝编辑风",功能行为不变。

**Architecture:** 新增 `styles/tokens.css`(9 个命名色 token + 字体三件套)与 `styles/base.css`(元素默认样式),通过「语义别名」让旧 `var(--bg-panel)` 等直接映射到新配色,低风险全局换肤;随后抽取 6 个可复用组件(TopBar/ArchiveCard/StatusBadge/MessageBubble/SourcePanel/EmptyState),视图改用组件,`ChatView` 重构为「左对话 + 右来源栏」双栏。不引入 Router/Pinia/测试框架。

**Tech Stack:** Vue 3 `<script setup>` + Vite 6,纯手写 CSS(无组件库),Node 20 构建。

## Global Constraints

- **命令执行环境(Windows 主机 + WSL 代码目录,务必遵守):** 本机 shell 是 Git Bash,当前会话 cwd 是 `\\wsl.localhost\Ubuntu-22.04\home\sjx_0\project\shixi`(UNC)。**所有 Linux 侧命令**(node/npm/ruff/git commit/push)用 `wsl -d Ubuntu-22.04 -- bash -lc '<cmd>'` 包裹并在 WSL 内 `cd /home/sjx_0/project/shixi`;git 提交/推送统一走 WSL git(SSH 密钥在 WSL,`Elysiafans` 身份已配置)。不要用 Windows 侧 node/npm(模块为 Linux 构建,会报 `@rollup/rollup-win32-x64-msvc` 缺失)。
- **构建命令**(Linux Node 20,必须用此 PATH):
  ```bash
  export PATH="/home/sjx_0/tools/node-v20.20.2-linux-x64/bin:$PATH"
  cd /home/sjx_0/project/shixi/frontend && npm run build
  ```
  Expected: `✓ built in X.XXs`。完整调用:`wsl -d Ubuntu-22.04 -- bash -lc 'export PATH="/home/sjx_0/tools/node-v20.20.2-linux-x64/bin:$PATH"; cd /home/sjx_0/project/shixi/frontend && npm run build'`。
- **无头渲染验证**(Windows Chrome;依赖 dev server 在 5173 运行):
  ```bash
  "/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu --no-sandbox --disable-dev-shm-usage --dump-dom --virtual-time-budget=8000 --user-data-dir="$TEMP/chrome-redesign" http://localhost:5173/ > /tmp/dom.html 2>/dev/null
  ```
  然后用 `grep` 校验页面内容。dev server 若未运行:`export PATH=... && cd /home/sjx_0/project/shixi/frontend && npm run dev -- --host --port 5173`。
- **不新增前端测试框架**;每个任务以「build 通过」+「无头渲染探针」作为测试门。
- **配色与字体唯一来源**是 `styles/tokens.css`;任何视图/组件**不得再出现**深色硬编码(`#0d1117`、`#161b22`、`#30363d`、`#58a6ff`、`#8b949e` 等)。
- **提交身份**:`Elysiafans <sjx_0702@qq.com>`(本地 git config 已设置);推 GitHub 走 WSL git+ssh。
- **文案原则**:错误不道歉、空态邀请行动;界面动词一致(按钮「发送」,状态「已归档」)。
- 提交路径的 commit 分组:①tokens ②components ③views,按每个任务末尾标注执行。

---

### Task 1: 设计 token + 基础样式(全站换肤)

**Files:**
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/base.css`
- Delete: `frontend/src/style.css`
- Modify: `frontend/src/main.js`

**Interfaces:**
- Consumes: 无(第一批)。
- Produces: 全局 CSS 变量(`--paper --surface --ink --dim --hairline --cobalt --cobalt-strong --cobalt-tint --clay --sage --mustard`)+ 语义别名(`--bg --bg-panel --bg-input --border --border-hover --text --text-dim --accent --accent-strong --green --yellow --red --purple --radius --mono`)+ 基础元素/组件类(`.card .row .list .item .badge .empty .spin .page` 等)。后续所有任务都消费这些。

- [ ] **Step 1: 创建 `styles/tokens.css`**

```css
/* DocAgent 设计 token —— 方向 B「实验室档案」
   配色/字体/几何/动效的唯一来源。旧语义变量(--bg 等)作为别名映射到新配色,
   让存量视图无需逐处改动即完成换肤;新代码优先直接使用 --paper/--surface/--ink 等。 */
:root {
  /* 命名色 */
  --paper: #f6f3ec;
  --surface: #fdfbf6;
  --ink: #1b1a16;
  --dim: #6e6a5e;
  --hairline: #dad4c5;
  --cobalt: #1d5fc9;
  --cobalt-strong: #164a9e;
  --cobalt-tint: #e8effb;
  --clay: #c9381c;
  --sage: #5b8a4a;
  --mustard: #b98a1e;

  /* 语义别名(兼容旧变量引用) */
  --bg: var(--paper);
  --bg-panel: var(--surface);
  --bg-input: var(--surface);
  --border: var(--hairline);
  --border-hover: #b9b2a0;
  --text: var(--ink);
  --text-dim: var(--dim);
  --accent: var(--cobalt);
  --accent-strong: var(--cobalt-strong);
  --green: var(--sage);
  --yellow: var(--mustard);
  --red: var(--clay);
  --purple: var(--cobalt);

  /* 字体三件套 */
  --font-display: Georgia, 'Noto Serif SC', 'Songti SC', serif;
  --font-body: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --mono: 'JetBrains Mono', ui-monospace, 'SFMono-Regular', Consolas, monospace;

  /* 几何 / 动效 */
  --radius: 8px;
  --radius-sm: 4px;
  --hairline-w: 1px;
  --dur: 150ms;
  --ease: ease;
  --focus-ring: 0 0 0 2px var(--paper), 0 0 0 4px var(--cobalt);
}
```

- [ ] **Step 2: 创建 `styles/base.css`**(迁移并重肤原 `style.css`)

```css
/* DocAgent 基础样式 —— 全部引用 tokens.css。 */
* { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font-body);
  font-size: 14px;
  line-height: 1.6;
}

#app { min-height: 100vh; display: flex; flex-direction: column; }

a { color: var(--cobalt); text-decoration: none; }
a:hover { text-decoration: underline; }

/* 交互元素焦点(键盘可达) */
:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
  border-radius: var(--radius-sm);
}

button {
  background: var(--bg-input);
  color: var(--ink);
  border: var(--hairline-w) solid var(--border);
  border-radius: var(--radius);
  padding: 6px 14px;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: border-color var(--dur) var(--ease), background var(--dur) var(--ease);
}
button:hover:not(:disabled) { border-color: var(--border-hover); background: #f0ecdf; }
button:disabled { opacity: 0.5; cursor: not-allowed; }

button.primary {
  background: var(--cobalt-strong);
  border-color: var(--cobalt-strong);
  color: #fff;
  font-weight: 600;
}
button.primary:hover:not(:disabled) { background: var(--cobalt); border-color: var(--cobalt); }

button.ghost { background: transparent; border-color: transparent; color: var(--dim); }
button.ghost:hover:not(:disabled) { border-color: var(--border-hover); color: var(--ink); background: transparent; }

button.danger:hover:not(:disabled) { border-color: var(--clay); color: var(--clay); }

button.active { background: var(--cobalt-strong); border-color: var(--cobalt-strong); color: #fff; }

input[type="text"], input[type="password"], input[type="email"], textarea, select {
  background: var(--bg-input);
  color: var(--ink);
  border: var(--hairline-w) solid var(--border);
  border-radius: var(--radius);
  padding: 8px 10px;
  font-size: 13px;
  font-family: inherit;
  width: 100%;
  outline: none;
}
input:focus, textarea:focus, select:focus { border-color: var(--cobalt); box-shadow: var(--focus-ring); }

textarea { resize: vertical; min-height: 60px; }

label { font-size: 12px; color: var(--dim); display: block; margin-bottom: 4px; }

/* ---- 布局 ---- */
.page { flex: 1; width: 100%; max-width: 960px; margin: 0 auto; padding: 24px 20px 64px; }

/* ---- 组件类 ---- */
.card {
  background: var(--surface);
  border: var(--hairline-w) solid var(--hairline);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 16px;
}
.card h3 { margin: 0 0 12px; font-family: var(--font-display); font-size: 16px; }

.muted { color: var(--dim); }
.mono { font-family: var(--mono); font-size: 12px; }
.err { color: var(--clay); }
.ok { color: var(--sage); }
.warn { color: var(--mustard); }

.badge {
  display: inline-flex; align-items: center; gap: 4px;
  border: var(--hairline-w) solid var(--border);
  border-radius: 999px;
  padding: 1px 10px;
  font-size: 12px;
  color: var(--dim);
  background: var(--surface);
}
.badge.ok { color: var(--sage); border-color: var(--sage); }
.badge.err { color: var(--clay); border-color: var(--clay); }
.badge.phase { color: var(--mustard); border-color: var(--mustard); }
.badge.route { color: var(--cobalt); border-color: var(--cobalt); }

.field { margin-bottom: 12px; }
.row { display: flex; gap: 8px; align-items: center; }
.row .grow { flex: 1; }

.list { display: flex; flex-direction: column; gap: 8px; }
.item {
  display: flex; align-items: center; gap: 10px;
  background: var(--surface);
  border: var(--hairline-w) solid var(--border);
  border-radius: var(--radius);
  padding: 10px 12px;
}
.item.selected { border-color: var(--cobalt); }
.item .name { flex: 1; font-weight: 500; }
.item .sub { color: var(--dim); font-size: 12px; }

/* 空态:邀请行动 */
.empty { text-align: center; color: var(--dim); padding: 32px 0; }

/* 加载 */
.spin {
  display: inline-block; width: 14px; height: 14px;
  border: 2px solid var(--border);
  border-top-color: var(--cobalt);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 滚动条 */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-track { background: transparent; }

/* 顶栏(过渡样式:App.vue 登录态目前无 scoped,靠这里;Task 2 迁入 TopBar 组件后移除) */
.topbar {
  display: flex; align-items: center; gap: 16px;
  padding: 10px 20px;
  background: var(--surface);
  border-bottom: var(--hairline-w) solid var(--hairline);
  position: sticky; top: 0; z-index: 10;
}
.topbar .brand { font-family: var(--font-display); font-size: 16px; font-weight: 700; color: var(--ink); }
.topbar .brand span { color: var(--dim); font-size: 13px; font-weight: 400; }
.topbar .nav { display: flex; gap: 4px; flex: 1; }
.topbar .spacer { flex: 1; }

/* 动效偏好:减少动态 */
@media (prefers-reduced-motion: reduce) {
  .spin, .caret { animation: none; }
  * { transition-duration: 0.01ms !important; }
}
```

- [ ] **Step 3: 更新 `main.js` 引入新样式,删除旧文件**

`frontend/src/main.js` 全文替换为:

```js
import { createApp } from 'vue'
import App from './App.vue'
import './styles/tokens.css'
import './styles/base.css'

createApp(App).mount('#app')
```

删除:`rm frontend/src/style.css`

- [ ] **Step 4: 验证构建**

Run: `export PATH="/home/sjx_0/tools/node-v20.20.2-linux-x64/bin:$PATH" && cd /home/sjx_0/project/shixi/frontend && npm run build`
Expected: `✓ built`。同时确认无 `style.css` 引用报错。

- [ ] **Step 5: 无头渲染验证换肤生效**

确保 dev server 在 5173,跑 Global Constraints 的无头命令,然后:
`grep -oE "(#f6f3ec|#1d5fc9|background: var\(--paper\))" /tmp/dom.html | head`
Expected: 至少出现 `#f6f3ec`(纸本底)。同时 `grep -c "0d1117" /tmp/dom.html` Expected: 0(无旧深色残留)。

- [ ] **Step 6: 提交**(commit 分组 ①)

```bash
cd /home/sjx_0/project/shixi
git add frontend/src/styles frontend/src/main.js
git rm --cached frontend/src/style.css 2>/dev/null || true
rm -f frontend/src/style.css
git add -A frontend/src
git commit -m "feat(frontend): add lab-archive design tokens and base styles"
```

---

### Task 2: TopBar 组件

**Files:**
- Create: `frontend/src/components/TopBar.vue`
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/styles/base.css`(移除 `.topbar`/`.brand`/`.nav`/`.spacer` 样式,已迁入组件)

**Interfaces:**
- Consumes: tokens.css 变量。
- Produces: `<TopBar :authed :active :email @nav @login @logout />`。`nav` 事件携带视图 key;`active` 为当前高亮 key。

- [ ] **Step 1: 创建 `components/TopBar.vue`**

```vue
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
.sp { flex: 1; }
.who { font-size: 13px; }
.btn-solid {
  background: var(--cobalt-strong); border-color: var(--cobalt-strong);
  color: #fff; font-weight: 600;
}
</style>
```

- [ ] **Step 2: 改 `HomeView.vue` 用 TopBar**

删除 `<script setup>` 里 `defineEmits` 不变;模板顶部的 `.home-top` header 整段替换为 `<TopBar :authed="authed" @nav="(k) => $emit('enter', k)" @login="$emit('login')" />`;scoped 样式删除 `.home-top` 块(保留 `.home`、hero、grid、tech)。

替换后 `HomeView.vue` 的 template 首部:

```html
<template>
  <div class="home">
    <TopBar :authed="authed" @nav="(k) => $emit('enter', k)" @login="$emit('login')" />
    <main class="page home-body">
      …(其余 hero / grid / tech 不变)…
```

并在 `<script setup>` 顶部加入 `import TopBar from '../components/TopBar.vue'`。

- [ ] **Step 3: 改 `App.vue` 登录态模板用 TopBar**

`<script setup>` 新增函数:

```js
function onNav(key) {
  if (key === 'home') goHome()
  else go(key)
}
```

模板中 `<header class="topbar">…</header>` 整块替换为:

```html
<TopBar
  :authed="true"
  :active="currentView"
  :email="user?.email"
  @nav="onNav"
  @logout="logout"
/>
```

并 `import TopBar from './components/TopBar.vue'`。

- [ ] **Step 4: 从 `base.css` 移除已迁出的顶栏样式**

删除 `base.css` 中 `.topbar`、`.topbar .brand`、`.topbar .nav`、`.topbar .spacer` 相关规则(它们只被 Task 1 暂时保留,现已无使用点)。

- [ ] **Step 5: 验证**

Run build + 无头首页渲染:`grep -oE "DocAgent" /tmp/dom.html | head -1` Expected 命中;`grep -c "登录 / 注册" /tmp/dom.html` Expected ≥1(未登录态 TopBar 按钮)。
(登录态顶栏由同一组件 props 驱动,以 build + 代码审阅为准。)

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/TopBar.vue frontend/src/views/HomeView.vue frontend/src/App.vue frontend/src/styles/base.css
git commit -m "feat(frontend): extract shared TopBar component"
```

---

### Task 3: StatusBadge / EmptyState / ArchiveCard 组件

**Files:**
- Create: `frontend/src/components/StatusBadge.vue`
- Create: `frontend/src/components/EmptyState.vue`
- Create: `frontend/src/components/ArchiveCard.vue`

**Interfaces:**
- Consumes: tokens.css;`StatusBadge`。
- Produces:
  - `<StatusBadge :status :label :progress />` — 内置状态文案映射(uploading/parsing/chunking/embedding/ready/failed/success/running),进行中态自动带 spinner。
  - `<EmptyState :title :hint />` — 空态引导文案。
  - `<ArchiveCard :no :name :meta :status :statusLabel :selected :removable @select @remove />` — 档案卡(编号 + 衬线名称 + 元信息 + 状态),`removable` 显示删除。

- [ ] **Step 1: 创建 `components/StatusBadge.vue`**

```vue
<script setup>
defineProps({
  status: { type: String, default: '' },
  label: { type: String, default: '' },
  progress: { type: [Number, String], default: '' },
})

const LABELS = {
  uploading: '上传中',
  parsing: '解析中',
  chunking: '分块中',
  embedding: '向量化',
  ready: '就绪',
  failed: '失败',
  success: '成功',
  running: '运行中',
}
const CLS = { ready: 'ok', success: 'ok', failed: 'err', running: 'phase' }
const IN_PROGRESS = ['uploading', 'parsing', 'chunking', 'embedding', 'running']
</script>

<template>
  <span :class="['badge', CLS[status] || '']">
    <span v-if="IN_PROGRESS.includes(status)" class="spin" />
    {{ label || LABELS[status] || status }}{{ progress ? ` ${progress}%` : '' }}
  </span>
</template>
```

- [ ] **Step 2: 创建 `components/EmptyState.vue`**

```vue
<script setup>
defineProps({
  title: { type: String, default: '这里还空着' },
  hint: { type: String, default: '' },
})
</script>

<template>
  <div class="empty-state">
    <p class="title">{{ title }}</p>
    <p v-if="hint" class="hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.empty-state { text-align: center; color: var(--dim); padding: 28px 0; }
.empty-state .title { margin: 0 0 4px; font-size: 14px; }
.empty-state .hint { margin: 0; font-size: 12.5px; opacity: 0.85; }
</style>
```

- [ ] **Step 3: 创建 `components/ArchiveCard.vue`**

```vue
<script setup>
import StatusBadge from './StatusBadge.vue'

defineProps({
  no: { type: String, default: '' },
  name: { type: String, default: '' },
  meta: { type: String, default: '' },
  status: { type: String, default: '' },
  statusLabel: { type: String, default: '' },
  selected: { type: Boolean, default: false },
  removable: { type: Boolean, default: false },
})
defineEmits(['select', 'remove'])
</script>

<template>
  <div :class="['archive', { selected }]" @click="$emit('select')">
    <div class="head">
      <span class="no">{{ no }}</span>
      <button v-if="removable" class="ghost danger x" title="删除" @click.stop="$emit('remove')">×</button>
    </div>
    <div class="name">{{ name }}</div>
    <div class="meta">{{ meta }}</div>
    <StatusBadge v-if="status" :status="status" :label="statusLabel" />
  </div>
</template>

<style scoped>
.archive {
  border: var(--hairline-w) solid var(--hairline);
  background: var(--surface);
  border-radius: var(--radius);
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color var(--dur) var(--ease);
}
.archive:hover { border-color: var(--border-hover); }
.archive.selected { border-color: var(--cobalt); }
.head { display: flex; align-items: center; justify-content: space-between; }
.no {
  font-family: var(--mono); font-size: 11px; color: var(--cobalt);
  letter-spacing: 0.5px;
}
.name { margin: 3px 0 2px; font-family: var(--font-display); font-size: 15px; color: var(--ink); }
.meta { font-size: 12px; color: var(--dim); margin-bottom: 6px; }
.x { padding: 0 6px; font-size: 14px; }
</style>
```

- [ ] **Step 4: 验证**

Run build(组件单独创建,先不接线):Expected `✓ built`。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components
git commit -m "feat(frontend): add StatusBadge, EmptyState and ArchiveCard components"
```

---

### Task 4: HomeView 与 KbView 接入组件

**Files:**
- Modify: `frontend/src/views/HomeView.vue`(归档卡改用 `ArchiveCard`)
- Modify: `frontend/src/views/KbView.vue`(知识库列表用 `ArchiveCard`,文档状态用 `StatusBadge`,空态用 `EmptyState`)

**Interfaces:**
- Consumes: `ArchiveCard`/`StatusBadge`/`EmptyState`。

- [ ] **Step 1: 改 `HomeView.vue` 归档卡**

`<script setup>` 加入 `import ArchiveCard from '../components/ArchiveCard.vue'`。模板 `.grid` 内三张 `.card` 卡替换为:

```html
<section class="grid">
  <ArchiveCard
    v-for="(e, i) in entries"
    :key="e.key"
    :no="'KB-0' + (i + 1)"
    :name="e.title"
    :meta="e.desc"
    @select="$emit('enter', e.key)"
  />
</section>
```

说明:首页三张卡是功能入口,ArchiveCard 整卡可点(`@select` → `enter`),与「档案编号」隐喻统一;emoji 图标不再渲染(B 方向无图标装饰,靠编号 + 衬线标题 + dim 元信息分层)。`entries` 数组保持原样(`icon` 字段不再被模板引用,留作数据即可)。

scoped 样式:删除 `.grid .card h3`、`.grid .card p`(不再命中 ArchiveCard);保留 `.grid` 网格布局,并追加响应式(对应 spec §4.1):

```css
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
@media (max-width: 480px) {
  .hero h1 { font-size: 22px; }
  .hero-actions button { padding: 8px 14px; font-size: 13px; }
}
```

- [ ] **Step 2: 改 `KbView.vue`**

`<script setup>` 加入:

```js
import ArchiveCard from '../components/ArchiveCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'
```

新增文档计数与删除回调逻辑(原逻辑保留,仅渲染层换):

- 左侧知识库列表 `<div class="list kb-list">…</div>` 替换为:

```html
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
```

- 右侧文档列表的状态徽标 `<span :class="['badge', STATUS_CLS[d.status]]">…` 整段替换为:

```html
<StatusBadge :status="d.status" :progress="d.progress" />
```

- 文档空态(精确替换现有文本):「暂无知识库,在上方新建一个。」→ `<EmptyState title="还没有归档文献" hint="上传第一份 PDF / Markdown,开始建立你的档案库。" />`;「该库还没有文档。」→ `<EmptyState title="该库还没有文档" hint="点击上方「上传文档」开始。" />`;「← 左侧选择一个知识库」→ `<EmptyState title="选择一个知识库" hint="← 从左侧选择一个库查看其文档。" />`。

- 上传失败文案遵循 spec §4.3 写作原则:将 `upload` 函数的 catch 分支 `err.value = e.message` 改为
  `err.value = '上传失败:解析失败。支持 txt / md / pdf / docx,重试或换格式。'`(覆盖后端原始错误即可,失败码以实际后端为准)。

- scoped 样式:删除 `.kb-list .item`、`.kb-list .item:hover`(ArchiveCard 自带 hover,列表内不再有 `.item` 元素)。

- `STATUS_CLS` 与 `STATUS_LABEL` 删除(StatusBadge 已内置映射);`msg` ref 本就无赋值,可一并删除。

- [ ] **Step 3: 验证**

Run build + 无头首页渲染:`grep -oE "KB-0[0-9]" /tmp/dom.html | sort -u` Expected 含 `KB-01`;`grep -c "还没有归档文献" /tmp/dom.html`(仅未登录首页不显示,此项以代码审阅为准)。

- [ ] **Step 4: 提交**(commit 分组 ②)

```bash
git add frontend/src/views/HomeView.vue frontend/src/views/KbView.vue
git commit -m "feat(frontend): wire ArchiveCard/StatusBadge/EmptyState into Home and Kb views"
```

---

### Task 5: ChatView 重构 —— MessageBubble + SourcePanel 双栏

**Files:**
- Create: `frontend/src/components/MessageBubble.vue`
- Create: `frontend/src/components/SourcePanel.vue`
- Modify: `frontend/src/views/ChatView.vue`(模板 + scoped 样式重写,脚本逻辑保留)

**Interfaces:**
- Consumes: `EmptyState`/`SourcePanel`;tokens。
- Produces:
  - `<MessageBubble :msg="{role, content, sources, convId, runId}" />` — 助手内容渲染为「转义后把 [n] 包成钴蓝上标」的 v-html。
  - `<SourcePanel :sources :inline />` — 来源脚注列表;`inline` 为消息内折叠块形态。

- [ ] **Step 1: 创建 `components/SourcePanel.vue`**

```vue
<script setup>
defineProps({
  sources: { type: Array, default: () => [] },
  inline: { type: Boolean, default: false },
})
</script>

<template>
  <div :class="['sources', { inline }]">
    <h5>引用来源 · {{ sources.length }}</h5>
    <div v-for="(s, j) in sources" :key="j" class="src">
      <span class="idx mono">[{{ j + 1 }}]</span>
      <div class="body">
        <div class="row1">
          <span class="doc">{{ s.doc_name || '文档' }}</span>
          <span class="mono dim">score {{ s.score }}</span>
        </div>
        <div class="text">{{ s.content }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sources { border-top: var(--hairline-w) dashed var(--hairline); margin-top: 10px; padding-top: 8px; }
.sources.inline { margin-top: 8px; }
.sources h5 {
  margin: 0 0 6px; font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.5px; color: var(--dim); font-weight: 600;
}
.src { display: flex; gap: 8px; border: var(--hairline-w) solid var(--hairline); background: var(--paper); border-radius: var(--radius-sm); padding: 6px 8px; margin-bottom: 6px; }
.idx { color: var(--cobalt); font-weight: 700; font-size: 11px; padding-top: 1px; }
.body { min-width: 0; }
.row1 { display: flex; align-items: baseline; gap: 8px; }
.doc { font-weight: 600; font-size: 12.5px; }
.dim { color: var(--dim); font-size: 11px; }
.text { margin-top: 2px; font-size: 12px; color: var(--dim); max-height: 60px; overflow-y: auto; white-space: pre-wrap; }
</style>
```

- [ ] **Step 2: 创建 `components/MessageBubble.vue`**

```vue
<script setup>
import { computed } from 'vue'
import SourcePanel from './SourcePanel.vue'

const props = defineProps({
  msg: { type: Object, required: true }, // { role, content, sources, convId, runId }
})

const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  )

// 助手消息:转义后把 [n] 包成上标引用
const rendered = computed(() =>
  props.msg.role === 'assistant'
    ? esc(props.msg.content).replace(/\[(\d+)\]/g, '<sup class="cite">[$1]</sup>')
    : null
)
</script>

<template>
  <div :class="['msg', msg.role]">
    <div class="bubble">
      <div v-if="msg.role === 'assistant'" class="meta mono">
        <span v-if="msg.runId" class="dim">run #{{ msg.runId }}</span>
        <span v-if="msg.convId" class="dim">会话 #{{ msg.convId }}</span>
      </div>
      <p v-if="msg.role === 'user'" class="content">{{ msg.content }}</p>
      <div v-else class="content" v-html="rendered" />
      <SourcePanel
        v-if="msg.role === 'assistant' && msg.sources && msg.sources.length"
        :sources="msg.sources"
        inline
      />
    </div>
  </div>
</template>

<style scoped>
.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.bubble {
  max-width: 86%;
  background: var(--surface);
  border: var(--hairline-w) solid var(--hairline);
  border-radius: var(--radius);
  padding: 10px 14px;
}
.msg.user .bubble { background: var(--cobalt); border-color: var(--cobalt); }
.msg.user .content { color: #fff; margin: 0; }
.content { margin: 0; white-space: pre-wrap; word-break: break-word; }
.content :deep(.cite) { color: var(--cobalt); font-weight: 700; }
.msg.user .content :deep(.cite) { color: #fff; }
.meta { display: flex; gap: 6px; margin-bottom: 6px; font-size: 11px; }
</style>
```

- [ ] **Step 3: 重写 `ChatView.vue` 模板 + scoped 样式**(脚本区除新增两行外不动)

`<script setup>` 顶部改为:

```js
import { ref, computed, onMounted } from 'vue'
import { listKbs, streamChat, renderCard } from '../api.js'
import MessageBubble from '../components/MessageBubble.vue'
import SourcePanel from '../components/SourcePanel.vue'
import EmptyState from '../components/EmptyState.vue'
```

(其余状态、`send`、`finalize`、`toggleCard`、`ROUTES`、`NODE_LABEL` 原样保留。)在 `finalize` 之后新增:

```js
// 最近一条助手消息的溯源(右侧来源栏)
const activeSources = computed(() => {
  for (let i = msgs.value.length - 1; i >= 0; i--) {
    const m = msgs.value[i]
    if (m.role === 'assistant' && m.sources && m.sources.length) return m.sources
  }
  return []
})
```

模板整体替换为:

```html
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
        <h5>引用来源</h5>
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
```

scoped 样式整体替换为:

```css
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
```

- [ ] **Step 4: 验证**

Run build Expected `✓ built`。无头渲染对话页需登录态,跳过;以 build + 代码审阅 + 后端全链路手动回归(Task 7)为准。

> **关于「来源折叠」(spec §4.1):** MessageBubble 每条助手消息内都渲染 inline `SourcePanel`,即「回答下方的脚注块」——它全宽度常驻。右侧 `source-col` 是宽屏的额外「当前答案溯源栏」,≤900px 隐藏后,脚注仍然以内联块形式出现在回答下方,语义与 spec 一致。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/MessageBubble.vue frontend/src/components/SourcePanel.vue frontend/src/views/ChatView.vue
git commit -m "feat(frontend): rebuild chat view with MessageBubble and source column"
```

---

### Task 6: AuthView / TasksView 换肤与收尾

**Files:**
- Modify: `frontend/src/views/AuthView.vue`
- Modify: `frontend/src/views/TasksView.vue`

**Interfaces:**
- Consumes: tokens、`StatusBadge`/`EmptyState`。

- [ ] **Step 1: 改 `AuthView.vue` 品牌与卡片**

scoped 样式中 `.auth-brand` 改为衬线 + 墨黑(保留配色一致性):

```css
.auth-brand {
  font-size: 26px;
  font-weight: 700;
  font-family: var(--font-display);
  color: var(--ink);
  text-align: center;
}
.auth-brand::before {
  content: 'DA';
  display: inline-block;
  width: 24px; height: 24px; margin-right: 8px;
  border: var(--hairline-w) solid var(--cobalt);
  color: var(--cobalt); border-radius: var(--radius-sm);
  font-size: 11px; font-weight: 600; line-height: 22px; vertical-align: 3px;
}
```

模板其余不动(卡片/输入已由 tokens 换肤)。

- [ ] **Step 2: 改 `TasksView.vue`**

`<script setup>` 加入 `import StatusBadge from '../components/StatusBadge.vue'`、`import EmptyState from '../components/EmptyState.vue'`。

- 任务状态徽标 `<span :class="['badge', STATUS_CLS[r.status]]">{{ r.status }}</span>` 替换为 `<StatusBadge :status="r.status" />`;`STATUS_CLS` 若不再使用则删除。
- 空态(精确替换现有文本):「暂无任务。」→ `<EmptyState title="暂无任务" hint="发起一次对话或上传文档后,这里会出现运行记录。" />`;「加载中…」→ `<EmptyState title="加载中…" />`;「← 选择一条任务查看 trace 事件时间线」→ `<EmptyState title="选择一条任务" hint="← 从左侧选择一条任务查看 trace 事件时间线。" />`;「无事件(该运行无 trace)。」→ `<EmptyState title="无事件" hint="该运行没有 trace 事件,可能为空跑。" />`。
- scoped 样式中 `--bg-panel`/`--border` 等已由 token 别名接管,无需手改;若存在硬编码深色值则一并清除。

- [ ] **Step 3: 全站硬编码检查**

```bash
grep -rnE "#(0d1117|161b22|30363d|58a6ff|8b949e|1c2128|21262d)" frontend/src || echo "CLEAN"
```
Expected: `CLEAN`(或仅剩用户消息白字 `#fff` 等有意为之的纯色)。

- [ ] **Step 4: 验证构建 + 无头渲染**

Run build;无头渲染首页:`grep -oE "多智能体知识库问答平台" /tmp/dom.html` Expected 命中。

- [ ] **Step 5: 提交**(commit 分组 ③)

```bash
git add frontend/src/views/AuthView.vue frontend/src/views/TasksView.vue
git commit -m "feat(frontend): restyle auth and tasks views with lab-archive tokens"
```

---

### Task 7: 全链路回归、README 微调、推送

**Files:**
- Modify: `README.md`(可选:前端描述加一句视觉方向)
- 不改动其他。

- [ ] **Step 1: 全链路手动回归(后端 8000 + 前端 5173 需在跑)**

浏览器走一遍:首页(未登录 TopBar)→ 登录/注册 → 知识库(建库、上传一份 md)→ 对话(提问、确认流式输出 + 右侧来源栏 + 消息内 [n] 上标)→ 任务(看 trace)→ 退出回首页。

- [ ] **Step 2: 无头渲染最终校验**

跑 Global Constraints 无头命令,断言:
- `grep -c "0d1117" /tmp/dom.html` = 0;
- `grep -oE "#f6f3ec" /tmp/dom.html | head -1` 命中。

- [ ] **Step 3: README 微调**(若想体现新视觉)

`README.md`「前端对接 / SSE 流式」一行的描述追加:",视觉为定制「实验室档案」纸本编辑风(设计 token + 组件化)"。

- [ ] **Step 4: 提交与推送**

```bash
cd /home/sjx_0/project/shixi
git add README.md
git commit -m "docs: note lab-archive frontend visual direction"
git push --force-with-lease origin main
```
Expected: `main -> main` 推送成功;`git log --format="%h %an" -1` 作者为 `Elysiafans`。

---

## 自评记录

- **Spec 覆盖**:tokens/base(Task 1)、TopBar(Task 2)、ArchiveCard/StatusBadge/EmptyState(Task 3-4)、MessageBubble/SourcePanel/ChatView 双栏(Task 5)、Auth/Tasks 换肤(Task 6)、响应式≤900 隐藏来源栏(Task 5 CSS)、焦点描边与 reduced-motion(Task 1 base.css)、错误/空态文案(组件 + 视图)、验证与推送(Task 7)、不引入路由/测试框架(全局约束) —— 全部有对应任务。
- **占位符扫描**:无 TBD/TODO;每个步骤含完整代码或精确命令。
- **类型一致性**:组件 props/emits 命名跨任务一致(TopBar `authed/active/email` + `nav/login/logout`;ArchiveCard `no/name/meta/status/statusLabel/selected/removable` + `select/remove`;SourcePanel `sources/inline`;MessageBubble `msg`;StatusBadge `status/label/progress`;EmptyState `title/hint`),`activeSources`/`onNav` 等内部符号在同一任务内定义即用。
