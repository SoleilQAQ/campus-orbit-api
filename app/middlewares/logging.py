# app/middlewares/logging.py
"""请求/响应日志中间件 - 记录详细的请求参数和响应内容"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message

logger = logging.getLogger("api.access")
logger.setLevel(logging.DEBUG)

# 如果没有 handler，添加一个控制台输出
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))
    logger.addHandler(handler)


class LoggingMiddleware(BaseHTTPMiddleware):
    """记录请求参数和响应内容的中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # 获取请求信息
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        headers = dict(request.headers)
        
        # 读取请求体（仅对 POST/PUT/PATCH）
        body = None
        if method in ("POST", "PUT", "PATCH"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    try:
                        body = json.loads(body_bytes.decode("utf-8"))
                        # 隐藏敏感字段
                        if isinstance(body, dict) and "password" in body:
                            body = {**body, "password": "***"}
                    except json.JSONDecodeError:
                        body = body_bytes.decode("utf-8")[:500]
            except Exception:
                body = "<读取失败>"

        # 记录请求
        req_log = f">>> {method} {path}"
        if query_params:
            req_log += f" | Query: {json.dumps(query_params, ensure_ascii=False)}"
        if body:
            req_log += f" | Body: {json.dumps(body, ensure_ascii=False) if isinstance(body, dict) else body}"
        
        logger.info(req_log)

        # 调用下一个中间件/路由
        response = await call_next(request)
        
        # 计算耗时
        duration = time.time() - start_time
        
        # 读取响应体
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        # 尝试解析响应 JSON
        resp_content = None
        try:
            resp_content = json.loads(response_body.decode("utf-8"))
        except Exception:
            resp_content = response_body.decode("utf-8")[:500] if response_body else None

        # 记录响应
        resp_log = f"<<< {method} {path} | Status: {response.status_code} | Time: {duration:.3f}s"
        if resp_content:
            resp_json = json.dumps(resp_content, ensure_ascii=False, indent=2) if isinstance(resp_content, (dict, list)) else resp_content
            # 截断过长的响应
            if len(resp_json) > 2000:
                resp_json = resp_json[:2000] + "...[截断]"
            resp_log += f"\n{resp_json}"
        
        logger.info(resp_log)

        # 重新构建响应
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
