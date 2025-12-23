# app/middlewares/logging.py
"""请求/响应日志中间件 - 记录详细的请求参数和响应内容

注意：使用纯 ASGI 中间件而非 BaseHTTPMiddleware，避免 Python 3.11+ 中的
ExceptionGroup 兼容性问题。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable, Awaitable

from starlette.types import ASGIApp, Receive, Scope, Send, Message

logger = logging.getLogger("api.access")
logger.setLevel(logging.DEBUG)

# 如果没有 handler，添加一个控制台输出
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))
    logger.addHandler(handler)


class LoggingMiddleware:
    """
    记录请求参数和响应内容的中间件
    
    使用纯 ASGI 实现，避免 BaseHTTPMiddleware 在 Python 3.11+ 中的兼容性问题
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # 只处理 HTTP 请求
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        method = scope.get("method", "")
        path = scope.get("path", "")
        query_string = scope.get("query_string", b"").decode("utf-8")
        
        # 解析查询参数
        query_params = {}
        if query_string:
            for param in query_string.split("&"):
                if "=" in param:
                    k, v = param.split("=", 1)
                    query_params[k] = v

        # 收集请求体
        body_parts: list[bytes] = []
        
        async def receive_wrapper() -> Message:
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if body:
                    body_parts.append(body)
            return message

        # 记录请求（在调用应用之前）
        req_log = f">>> {method} {path}"
        if query_params:
            req_log += f" | Query: {json.dumps(query_params, ensure_ascii=False)}"
        
        # 收集响应
        response_status = 0
        response_body_parts: list[bytes] = []
        
        async def send_wrapper(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message.get("status", 0)
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    response_body_parts.append(body)
            await send(message)

        # 先记录请求开始
        logger.info(req_log)

        try:
            # 调用应用
            await self.app(scope, receive_wrapper, send_wrapper)
        finally:
            # 计算耗时
            duration = time.time() - start_time
            
            # 记录请求体（如果有）
            if body_parts and method in ("POST", "PUT", "PATCH"):
                try:
                    body_bytes = b"".join(body_parts)
                    body = json.loads(body_bytes.decode("utf-8"))
                    # 隐藏敏感字段
                    if isinstance(body, dict) and "password" in body:
                        body = {**body, "password": "***"}
                    logger.debug(f"    Body: {json.dumps(body, ensure_ascii=False)}")
                except Exception:
                    pass
            
            # 尝试解析响应 JSON
            resp_content = None
            if response_body_parts:
                try:
                    response_body = b"".join(response_body_parts)
                    resp_content = json.loads(response_body.decode("utf-8"))
                except Exception:
                    resp_content = None

            # 记录响应
            resp_log = f"<<< {method} {path} | Status: {response_status} | Time: {duration:.3f}s"
            if resp_content:
                resp_json = json.dumps(resp_content, ensure_ascii=False, indent=2) if isinstance(resp_content, (dict, list)) else str(resp_content)
                # 截断过长的响应
                if len(resp_json) > 2000:
                    resp_json = resp_json[:2000] + "...[截断]"
                resp_log += f"\n{resp_json}"
            
            logger.info(resp_log)
