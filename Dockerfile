FROM ghcr.io/astral-sh/uv:0.9.2-python3.14-alpine

WORKDIR /app

# 1. 给 uv 配置默认 index（新版推荐 UV_DEFAULT_INDEX）
ENV UV_DEFAULT_INDEX="https://mirrors.aliyun.com/pypi/simple/"
# 兼容旧习惯的话，也可以顺手配一下：
ENV UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/"

# 2. 如果还想保留官方 PyPI 当备选，可以用 UV_INDEX / extra-index-url，
#   但对这种「主要是加速 & 避开 GFW」场景，单个国内镜像就够用

# 3. 再去 sync
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 4. 拷贝项目代码
COPY . .

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
