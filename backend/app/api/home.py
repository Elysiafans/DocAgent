"""根路径导航页(GET /)。纯展示页,不属于 /api/v1 API,不进 OpenAPI schema。"""
from string import Template

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.config import get_settings

router = APIRouter()

# 前端地址:本地开发默认;生产由 nginx 同源提供,此处仅作指引。
FRONTEND_URL = "http://localhost:5173"

# CSS 内含大量花括号,故用 string.Template($ 占位)而非 f-string。
_NAV_HTML = Template(
    """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$app_name · 服务导航</title>
<style>
  :root {
    --bg:#0d1117; --panel:#161b22; --border:#30363d;
    --text:#e6edf3; --dim:#8b949e; --accent:#58a6ff;
    --green:#3fb950; --yellow:#d29922; --purple:#bc8cff; --radius:8px;
    --mono:ui-monospace,SFMono-Regular,"Cascadia Code",Consolas,monospace;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; background:var(--bg); color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",Roboto,Helvetica,Arial,sans-serif;
    font-size:14px; line-height:1.6;
  }
  a { color:var(--accent); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .wrap { max-width:960px; margin:0 auto; padding:32px 20px 64px; }
  header { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; }
  .brand { font-size:20px; font-weight:700; color:var(--accent); letter-spacing:.5px; }
  .brand small { color:var(--dim); font-weight:400; }
  h1 { margin:28px 0 8px; font-size:28px; }
  .sub { color:var(--dim); margin:0 0 24px; max-width:680px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:16px; }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:var(--radius); padding:16px; }
  .card h2 { margin:0 0 8px; font-size:15px; }
  .card ul { margin:0; padding:0; list-style:none; }
  .card li { display:flex; align-items:center; gap:10px; flex-wrap:wrap; padding:6px 0; border-bottom:1px dashed var(--border); }
  .card li:last-child { border-bottom:none; }
  .route { font-family:var(--mono); font-size:12px; color:var(--purple); background:rgba(188,140,255,.08); border:1px solid var(--purple); border-radius:999px; padding:1px 10px; white-space:nowrap; }
  .desc { color:var(--dim); font-size:12px; }
  code { font-family:var(--mono); font-size:12px; }
  table { width:100%; border-collapse:collapse; font-size:12.5px; }
  th,td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--border); }
  th { color:var(--dim); font-weight:600; }
  td.method { font-family:var(--mono); color:var(--green); white-space:nowrap; }
  td.mono { font-family:var(--mono); color:var(--accent); }
  .badge { display:inline-block; border:1px solid var(--border); border-radius:999px; padding:1px 10px; font-size:11px; color:var(--dim); }
  .badge.ok { color:var(--green); border-color:var(--green); }
  .footer { margin-top:40px; color:var(--dim); font-size:12px; text-align:center; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand">$app_name<small> · 多智能体知识库问答平台</small></div>
    <a class="badge ok" href="$frontend_url" target="_blank" rel="noopener">打开前端 →</a>
  </header>

  <h1>服务导航</h1>
  <p class="sub">
    后端 API 与协议入口一览。交互式文档见 <a href="/docs">/docs</a>;前端 SPA 见
    <a href="$frontend_url">$frontend_url</a>。统一前缀 <code>$v1</code>,除健康检查与登录注册外
    均需 <code>Authorization: Bearer &lt;token&gt;</code>。
  </p>

  <div class="grid">
    <div class="card">
      <h2>文档与服务状态</h2>
      <ul>
        <li><a class="route" href="/docs">/docs</a><span class="desc">Swagger UI 交互式文档</span></li>
        <li><a class="route" href="/redoc">/redoc</a><span class="desc">ReDoc 文档</span></li>
        <li><a class="route" href="/openapi.json">/openapi.json</a><span class="desc">OpenAPI 规范(JSON)</span></li>
        <li><a class="route" href="$v1/health">$v1/health</a><span class="desc">服务健康检查</span></li>
      </ul>
    </div>

    <div class="card">
      <h2>Agent 协议入口(POST)</h2>
      <ul>
        <li><span class="route">/mcp</span><span class="desc">MCP 服务端(JSON-RPC 2.0 + SSE)</span></li>
        <li><span class="route">/a2a</span><span class="desc">A2A Agent-to-Agent</span></li>
        <li><span class="route">$v1/a2ui/render</span><span class="desc">A2UI 结构化卡片</span></li>
        <li><a class="route" href="$v1/skills">$v1/skills</a><span class="desc">Skills 技能列表</span></li>
      </ul>
    </div>

    <div class="card">
      <h2>业务 API(前缀 $v1)</h2>
      <table>
        <tr><th>方法</th><th>路径</th><th>说明</th></tr>
        <tr><td class="method">POST</td><td class="mono">/auth/register · /auth/login</td><td>注册 / 登录(JWT)</td></tr>
        <tr><td class="method">POST</td><td class="mono">/knowledge_bases</td><td>创建知识库</td></tr>
        <tr><td class="method">POST</td><td class="mono">/knowledge_bases/{id}/documents</td><td>上传文档</td></tr>
        <tr><td class="method">POST</td><td class="mono">/chat/agent</td><td>SSE 多智能体流式问答</td></tr>
        <tr><td class="method">POST</td><td class="mono">/memories</td><td>长期记忆写入</td></tr>
        <tr><td class="method">GET</td><td class="mono">/task_runs</td><td>任务可观测</td></tr>
      </table>
    </div>
  </div>

  <div class="footer">
    $app_name · 技术栈:FastAPI / LangGraph / Qdrant / PostgreSQL / Vue 3 ·
    完整文档见 <a href="https://github.com/Elysiafans/DocAgent" target="_blank" rel="noopener">GitHub</a>
  </div>
</div>
</body>
</html>
"""
)


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> HTMLResponse:
    s = get_settings()
    return HTMLResponse(
        _NAV_HTML.substitute(
            app_name=s.APP_NAME,
            v1=s.API_V1_PREFIX,
            frontend_url=FRONTEND_URL,
        )
    )
