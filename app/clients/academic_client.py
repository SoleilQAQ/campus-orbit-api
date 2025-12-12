# app/clients/academic_client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class AcademicHealthResult:
    status_code: int
    url: str
    location: Optional[str]
    text_sample: str
    content_length: int
    content_type: Optional[str]


@dataclass(frozen=True)
class AcademicLoginResult:
    success: bool
    status_code: int
    location: Optional[str]
    cookies: Dict[str, str]
    text_sample: str


class AcademicClient:
    """
    教务系统 HTTP 访问层（Step A：health + login 骨架）

    - verify 默认 True；只有配置 ACADEMIC_INSECURE_SKIP_VERIFY=true 才会跳过证书校验。
    - follow_redirects=False：我们要显式拿到 302 的 Location（教务站很爱跳转）。
    - transport：仅用于测试注入（MockTransport / 自定义 transport）。
    """

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base_url = settings.academic_base_url.rstrip("/")
        self._health_path = settings.academic_health_path

        self._connect_timeout = settings.academic_connect_timeout
        self._read_timeout = settings.academic_read_timeout

        self._verify = not settings.academic_insecure_skip_verify
        self._transport = transport  # ✅ 现在 transport 有定义了（参数传入）

    def _timeout(self) -> httpx.Timeout:
        # httpx.Timeout 支持 connect/read/write/pool 四段超时
        return httpx.Timeout(
            connect=self._connect_timeout,
            read=self._read_timeout,
            write=self._read_timeout,
            pool=self._connect_timeout,
        )

    def _client_kwargs(
        self,
        request_id: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        headers = {
            "User-Agent": settings.academic_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if extra_headers:
            headers.update(extra_headers)
        if request_id:
            headers["X-Request-ID"] = request_id

        kw: Dict[str, Any] = {
            "base_url": self._base_url,
            "timeout": self._timeout(),
            "follow_redirects": False,
            "verify": self._verify,
            "headers": headers,
        }

        # ✅ 只有测试注入 transport 时才传（httpx 的 transport 是“低层发送器”）
        if self._transport is not None:
            kw["transport"] = self._transport

        return kw

    async def fetch_health(self, request_id: Optional[str] = None) -> AcademicHealthResult:
        async with httpx.AsyncClient(**self._client_kwargs(request_id=request_id)) as client:
            resp = await client.get(self._health_path)

        location = resp.headers.get("location")
        sample = (resp.text or "")[:200]
        content_length = len(resp.content or b"")
        content_type = resp.headers.get("content-type")

        return AcademicHealthResult(
            status_code=resp.status_code,
            url=str(resp.url),
            location=location,
            text_sample=sample,
            content_length=content_length,
            content_type=content_type,
        )

    async def login(
        self,
        username: str,
        password: str,
        request_id: Optional[str] = None,
    ) -> AcademicLoginResult:
        kw = self._client_kwargs(
            request_id=request_id,
            extra_headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        async with httpx.AsyncClient(**kw) as client:
            # 先 GET 一下登录页（很多系统会先发 cookie/验证码相关）
            await client.get(self._health_path)

            # Step A：先用“明文骨架”
            # 下一步：把 Flutter 的 encoded 算法移植到 Python，再把 encoded 填上
            form = {
                "userAccount": username,
                "userPassword": password,
                "encoded": "",  # TODO
            }
            resp = await client.post("/jsxsd/xk/LoginToXk", data=form)

            location = resp.headers.get("location")
            sample = (resp.text or "")[:200]
            cookies = {k: v for k, v in client.cookies.items()}

        ok = resp.status_code in (302, 303) and (location is None or "LoginToXk" not in location)

        return AcademicLoginResult(
            success=ok,
            status_code=resp.status_code,
            location=location,
            cookies=cookies,
            text_sample=sample,
        )
