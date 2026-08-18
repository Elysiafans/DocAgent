"""JSON-RPC 2.0 信封工具(MCP / A2A 共用)。

标准错误码:-32700 Parse error / -32600 Invalid Request / -32601 Method not found /
-32602 Invalid params / -32000 Server error。
"""
from __future__ import annotations

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32000


class JsonRpcError(Exception):
    """携带 JSON-RPC 标准错误码的异常。"""

    def __init__(self, code: int, message: str, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def success(id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def error(id, code: int, message: str, data=None) -> dict:
    e: dict = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": e}


def parse_request(obj) -> tuple[str, object, dict]:
    """解析单请求,返回 (method, id, params);结构非法抛 JsonRpcError。"""
    if not isinstance(obj, dict):
        raise JsonRpcError(INVALID_REQUEST, "Invalid Request")
    if obj.get("jsonrpc") != "2.0":
        raise JsonRpcError(INVALID_REQUEST, "Invalid Request")
    method = obj.get("method")
    if not isinstance(method, str) or not method:
        raise JsonRpcError(INVALID_REQUEST, "Invalid Request")
    params = obj.get("params")
    if params is None:
        params = {}
    return method, obj.get("id"), params
