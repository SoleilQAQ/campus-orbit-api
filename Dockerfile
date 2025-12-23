# syntax=docker/dockerfile:1.7

FROM alpine:3.22 AS tz
RUN apk add --no-cache tzdata

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder
WORKDIR /app

ENV TZ=Asia/Shanghai
# ENV TZ=Asia/Tokyo

COPY --from=tz /usr/share/zoneinfo /usr/share/zoneinfo
RUN cp /usr/share/zoneinfo/$TZ /etc/localtime \
 && echo "$TZ" > /etc/timezone

ENV UV_DEFAULT_INDEX="https://mirrors.aliyun.com/pypi/simple/"
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev





COPY . .
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
