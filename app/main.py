# app/main.py
from contextlib import asynccontextmanager

import httpx # httpx/aiohttp/request
from fastapi import FastAPI # django/flask/Sanic/Robyn
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError

from app.api.weather import router as weather_router
from app.api.health import router as health_router
from app.core.errors import http_exception_handler, validation_exception_handler
from app.middlewares.request_id import request_id_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动：创建全局 httpx.AsyncClient
    http_client = httpx.AsyncClient(timeout=5.0)
    app.state.http_client = http_client
    yield
    # 应用关闭：释放 http client
    await http_client.aclose()


app = FastAPI(
    title="Soleil Campus Hub",
    lifespan=lifespan,
)

# middleware
app.middleware("http")(request_id_middleware)  # :contentReference[oaicite:4]{index=4}

# exception handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # :contentReference[oaicite:5]{index=5}
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # :contentReference[oaicite:6]{index=6}

# routers
app.include_router(weather_router)
app.include_router(health_router)


@app.get("/health")
async def health():
    return {"status": "ok", "message": "FastAPI is running!"}


# 挂载天气路由
app.include_router(weather_router)
