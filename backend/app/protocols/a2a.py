"""自研 A2A(Agent2Agent)协议服务端核心。

JSON-RPC 2.0 信封;实现方法:`agent/get`(AgentCard)、`message/send`(接收
文本消息 → 跑 DocAgent Supervisor 图,返回 taskId + agent 消息)、
`tasks/get`(按 run_id 查任务状态)。业务适配(鉴权/库归属)由 `app/api/a2a.py`
以 adapter 注入。
"""
from __future__ import annotations

from app.protocols.jsonrpc import (
    METHOD_NOT_FOUND,
    JsonRpcError,
    error,
    parse_request,
    success,
)


class A2aError(JsonRpcError):
    """A2A 业务错误(消息缺字段等),映射为 JSON-RPC error。"""


class A2aServer:
    def __init__(self, adapter):
        self._adapter = adapter  # 提供 agent_card() / ask(params) / get_task(params)

    def handle(self, req) -> dict:
        try:
            method, rid, params = parse_request(req)
        except JsonRpcError as e:
            rid = req.get("id") if isinstance(req, dict) else None
            return error(rid, e.code, e.message)
        try:
            if method == "agent/get":
                return success(rid, self._adapter.agent_card())
            if method == "message/send":
                return success(rid, self._adapter.ask(params))
            if method == "tasks/get":
                return success(rid, self._adapter.get_task(params))
            raise JsonRpcError(METHOD_NOT_FOUND, f"Method not found: {method}")
        except JsonRpcError as e:
            return error(rid, e.code, e.message)
        except Exception as e:
            return error(rid, -32000, f"{type(e).__name__}: {e}")
