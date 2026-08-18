"""自研 MCP(Model Context Protocol)服务端核心。

实现 streamable HTTP 传输的服务端协议面:JSON-RPC 2.0 信封 +
`initialize` 握手 + `tools/list` + `tools/call`。传输层(JSON/SSE)由
`app/api/mcp.py` 处理;这里只负责协议逻辑,便于单测。
"""
from __future__ import annotations

from typing import Any, Callable

from app.protocols.jsonrpc import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    JsonRpcError,
    error,
    parse_request,
    success,
)

# MCP 客户端(Claude Desktop / 自研 client)调用工具时传入的上下文构造器:
# ctx_factory(kb_id) -> AgentContext(已做归属校验)
CtxFactory = Callable[[int], Any]


class McpServer:
    NAME = "docagent-mcp"
    VERSION = "0.1.0"
    PROTOCOL_VERSION = "2025-03-26"
    SUPPORTED_VERSIONS = {"2025-03-26", "2025-06-18"}

    def __init__(self, tool_specs: list[dict], ctx_factory: CtxFactory | None = None):
        self._tools: dict[str, dict] = {s["name"]: s for s in tool_specs}
        self._ctx_factory = ctx_factory

    def handle(self, req) -> dict | list:
        """处理单个或批量(数组)JSON-RPC 请求,返回对应信封。"""
        if isinstance(req, list):
            return [self._handle_single(r) for r in req]
        return self._handle_single(req)

    def _handle_single(self, req) -> dict:
        try:
            method, rid, params = parse_request(req)
        except JsonRpcError as e:
            rid = req.get("id") if isinstance(req, dict) else None
            return error(rid, e.code, e.message)
        try:
            if method == "initialize":
                return success(rid, self._initialize(params))
            if method == "notifications/initialized":
                return success(rid, {})
            if method == "tools/list":
                return success(rid, self._list_tools())
            if method == "tools/call":
                return success(rid, self._call_tool(params))
            raise JsonRpcError(METHOD_NOT_FOUND, f"Method not found: {method}")
        except JsonRpcError as e:
            return error(rid, e.code, e.message)
        except Exception as e:  # noqa: BLE001
            return error(rid, INTERNAL_ERROR, f"{type(e).__name__}: {e}")

    # ---- 协议方法 ----
    def _initialize(self, params: dict) -> dict:
        ver = params.get("protocolVersion")
        if ver not in self.SUPPORTED_VERSIONS:
            ver = self.PROTOCOL_VERSION
        return {
            "protocolVersion": ver,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": self.NAME, "version": self.VERSION},
        }

    def _list_tools(self) -> dict:
        return {
            "tools": [
                {
                    "name": s["name"],
                    "description": s["description"],
                    "inputSchema": s["inputSchema"],
                }
                for s in self._tools.values()
            ]
        }

    def _call_tool(self, params: dict) -> dict:
        name = params.get("name")
        spec = self._tools.get(name)
        if spec is None:
            raise JsonRpcError(METHOD_NOT_FOUND, f"Unknown tool: {name}")
        arguments = dict(params.get("arguments") or {})

        ctx = None
        if spec.get("needs_kb"):
            kb_id = arguments.get("kb_id")
            if kb_id is None or self._ctx_factory is None:
                raise JsonRpcError(INVALID_PARAMS, "kb_id is required")
            ctx = self._ctx_factory(int(kb_id))
        try:
            text = spec["call"](ctx, arguments)
        except KeyError as e:
            raise JsonRpcError(INVALID_PARAMS, f"Missing argument: {e.args[0]}") from e
        except Exception as e:  # noqa: BLE001
            raise JsonRpcError(INTERNAL_ERROR, f"{type(e).__name__}: {e}") from e
        return {"content": [{"type": "text", "text": str(text)}], "isError": False}
