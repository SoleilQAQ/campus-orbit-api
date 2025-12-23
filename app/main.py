# app/main.py
from contextlib import asynccontextmanager

import httpx  # httpx/aiohttp/request
from fastapi import FastAPI  # django/flask/Sanic/Robyn
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.weather import router as weather_router
from app.api.health import router as health_router
from app.api.academic import router as academic_router
from app.api.geo import router as geo_router
from app.platform.routes import router as platform_router
from app.core.errors import http_exception_handler, validation_exception_handler
from app.middlewares.request_id import request_id_middleware
from app.middlewares.logging import LoggingMiddleware


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
app.middleware("http")(request_id_middleware)
# 使用纯 ASGI 中间件，避免 BaseHTTPMiddleware 在 Python 3.11+ 中的兼容性问题
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# exception handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# routers
app.include_router(weather_router)
app.include_router(health_router)
app.include_router(academic_router)
app.include_router(geo_router)
app.include_router(platform_router)

@app.get("/health")
async def health():
    return {"status": "ok", "message": "FastAPI is running!"}
