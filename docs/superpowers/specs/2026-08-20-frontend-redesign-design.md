# DocAgent 前端重新制作 · 设计文档

- **日期**:2026-08-20
- **状态**:已评审,待实现
- **目标读者**:实现者(下一阶段写实现计划)
- **主题**:用 Anthropic 官方 `frontend-design` 技能方法论,对前端做「视觉重设计 + 结构重构」。已通过视觉伴侣在浏览器里选型并逐节确认。

---

## 1. 背景与目标

当前前端(6 视图 + 手写深色 CSS)功能完整但视觉平淡、结构松散(`ChatView` 334 行、`KbView` 261 行,样式全部堆在 `style.css` 和视图 scoped 里)。本次目标是:

1. **换一套有辨识度的视觉身份** —— 方向 B「实验室档案」:暖纸白 + 钴蓝的编辑/文献气质,与"知识库 + 引用溯源"的产品内核同构;刻意区别于常见 AI 模板风。
2. **结构重构** —— 拆出可复用组件、把 `style.css` 重组为设计 token + 元素基础样式,让前端代码像后端一样"分层可读"。
3. **保持行为不变** —— 登录态、视图切换、SSE 流式问答、溯源渲染全部照旧,只换壳与结构。

## 2. 视觉系统(方向 B · 实验室档案)

### 2.1 颜色 token

| Token | 值 | 用途 |
| --- | --- | --- |
| `--paper` | `#F6F3EC` | 页面背景(暖纸白) |
| `--surface` | `#FDFBF6` | 卡片 / 输入 / 消息表面(米白) |
| `--ink` | `#1B1A16` | 主文字(墨黑) |
| `--dim` | `#6E6A5E` | 次级文字 |
| `--hairline` | `#DAD4C5` | 边框 / 分隔细线 |
| `--cobalt` | `#1D5FC9` | 主强调色(链接 / 按钮 / 上标引用 / 档案编号) |
| `--clay` | `#C9381C` | 错误 / 危险 |
| `--sage` | `#5B8A4A` | 成功 / 就绪状态(低饱和纸本绿) |
| `--mustard` | `#B98A1E` | 进行中 / 警告状态(低饱和芥末黄) |

### 2.2 字体 token

- 显示 / 标题:`Georgia, 'Noto Serif SC', 'Songti SC', serif`
- 正文:`'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif`
- 等宽(标签 / 引用 / 路由 / 编号):`'JetBrains Mono', ui-monospace, 'SFMono-Regular', Consolas, monospace`
- 类型刻度:hero 28 / 节标题 18-20(衬线)/ 正文 14 / 辅助 12 / mono 标签 11 大写 + 字距。

### 2.3 布局与标志性元素

- **编辑风细线** 分层:hairline 分隔线替代深色阴影;留白分级,弱化高亮。
- **标志性元素 =「回答即脚注」**:助手消息中钴蓝上标 `[1][2]`,右侧(或小屏折叠到回答下方)`SourcePanel` 呈现引用来源;知识库以 `KB-0X` 档案编号标识。这是整套设计的记忆点。
- **mono eyebrow**:每条助手消息上方一行 mono 元信息(`compare · 检索 12 分块 · 重排`),取代现在的彩色 badge 堆叠,与编辑风格统一。

## 3. 结构重构

### 3.1 文件布局

```
frontend/src/
├── styles/
│   ├── tokens.css        # 设计 token(§2 全部值)
│   └── base.css          # button/input/link/scrollbar/badge/empty 等元素默认样式,全部引用 token
├── components/
│   ├── TopBar.vue        # 顶栏:DA 索引品牌标 + 导航 + 用户 + 退出/登录(props: authed, activeView)
│   ├── ArchiveCard.vue   # 知识库档案卡(编号 + 名称 + 元信息 + StatusBadge)
│   ├── StatusBadge.vue   # 状态徽标(已归档/摄取中/失败…)
│   ├── MessageBubble.vue # 对话消息;助手含 eyebrow + 内容 + 上标引用 + 折叠来源
│   ├── SourcePanel.vue   # 右侧「引用来源」脚注栏(对话屏标志布局)
│   └── EmptyState.vue    # 空态(邀请行动文案)
├── views/                # Home / Auth / Kb / Chat / Tasks 保留,套新 token + 用组件
└── App.vue / api.js / main.js
```

### 3.2 组件拆分依据(来自现有代码)

| 新组件 | 从哪抽 | 复用点 |
| --- | --- | --- |
| `TopBar` | `App.vue` 顶栏 + `HomeView` 顶栏 | 登录态不同(props 区分「退出/登录注册」) |
| `ArchiveCard` | `KbView` 的 `.item` + `HomeView` 的归档卡 | 列表与首页共用同一卡片 |
| `StatusBadge` | `KbView` 文档状态徽标、`HomeView` 状态徽标 | 状态文案 + 样式映射集中在组件内 |
| `MessageBubble` | `ChatView` 消息渲染(`msg.user` / `msg.assistant`) | 含流式 caret、eyebrow、上标引用 |
| `SourcePanel` | `ChatView` 的 `.sources` 块 | 编号/文档名/得分/片段;折叠逻辑 |
| `EmptyState` | 各视图 `.empty` | 图标? + 引导文案,不摆"暂无"就完事 |

### 3.3 样式重组

- 删除 `style.css` 中的视图专属样式;保留并迁移通用元素默认值到 `base.css`。
- 所有颜色/字体/间距改为 `tokens.css` 的 CSS 变量。
- 各组件用 scoped 样式,只写本组件的布局细节。

### 3.4 数据流(不变)

- `App.vue` 手写视图切换:`home | auth | kb | chat | tasks`;`pendingView` 支持首页入口登录后回到目标视图(现有逻辑)。
- 登录态:`localStorage`(token + user);`selectedKbId` 事件传 `ChatView`。
- `ChatView` SSE 流式解析逻辑原样保留;`MessageBubble`/`SourcePanel` 只接管渲染。

## 4. 响应式 / 无障碍 / 错误与空态

### 4.1 响应式

- ≤900px:对话屏从「左对话 + 右来源栏」→ 来源折叠为回答下方脚注块;归档卡 3 列 → 1 列;顶栏导航压缩。
- ≤480px:hero 字号降级、输入条按钮收窄;无横向滚动。

### 4.2 无障碍

- 键盘焦点:统一 cobalt 焦点描边(替代隐式 hover)。
- `prefers-reduced-motion`:流式 caret 闪烁、加载动画关闭。
- 对比度:ink 在 paper、cobalt 白底蓝字达 WCAG AA。

### 4.3 错误与空态文案(写作原则:错误不道歉、空态邀请行动)

- 空库:「还没有归档文献 —— 上传第一份 PDF / Markdown,开始建立你的档案库。」
- 上传失败:「上传失败:解析失败。支持 txt / md / pdf / docx,重试或换格式。」
- 流式中断:「回答中断,已保留已生成内容,可重试。」

## 5. 验证

1. `npm run build` 通过(CI `frontend-build` 同步覆盖)。
2. 无头浏览器渲染首页 + 对话屏:核对 B 配色 token 生效、无布局溢出、来源栏折叠行为正确。
3. 手动全链路回归:登录 → 建库 → 上传 → 流式问答 → 溯源 → 任务。
4. 不新增前端测试框架(轻量;后端 pytest 已覆盖业务)。

## 6. 范围外(明确不做)

- 不引入 Vue Router / Pinia(维持手写视图切换)。
- 不改后端 API 与协议。
- 不改动知识库/对话/任务的功能行为。

## 7. 交付与提交

- 提交拆分建议:① `feat(frontend): add design tokens (lab-archive style)` ② `feat(frontend): extract shared components` ③ `feat(frontend): restyle views with new tokens`。
- 以 `Elysiafans <sjx_0702@qq.com>` 身份提交并推送 GitHub(本地 git config 已设置)。

## 8. 验收清单

- [ ] `tokens.css` / `base.css` 就位,全站无硬编码旧深色值残留。
- [ ] 六个组件存在且被视图使用,无重复大段样式。
- [ ] 首页/对话/知识库/任务四个主要页面呈现 B 视觉(纸本 + 钴蓝 + 细线 + 脚注溯源)。
- [ ] 对话屏来源栏:宽屏右侧栏、窄屏折叠到回答下方。
- [ ] 键盘焦点可见、reduced-motion 生效。
- [ ] `npm run build` 通过;无头渲染无溢出;全链路手动回归通过。
