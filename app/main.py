# app/main.py
from contextlib import asynccontextmanager

import httpx # httpx/aiohttp/request
from fastapi import FastAPI # django/flask/Sanic/Robyn
from app.api.weather import router as weather_router


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


@app.get("/health")
async def health():
    return {"status": "ok", "message": "FastAPI is running!"}


# 挂载天气路由
app.include_router(weather_router)
