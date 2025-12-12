# app/services/jwxt_service.py
from __future__ import annotations

from typing import Tuple

import httpx

from app.core.config import settings
from app.schemas.jwxt import JwxtUserProfile


class JwxtService:
    """
    教务系统后端访问封装：
    - 负责发 HTTP 请求（httpx）
    - 负责处理 SSL 验证开关（证书过期时可以临时关闭）
    - 以后会加：登录、获取个人信息、成绩、课表等
    """

    def __init__(self) -> None:
        self.base_url = settings.jwxt_base_url.rstrip("/")

    def _build_client(self) -> httpx.AsyncClient:
        """
        每次请求创建一个 httpx.AsyncClient。
        后续如果你想搞更高性能，可以改成在 lifespan 里复用单例 client。
        """
        timeout = httpx.Timeout(
            settings.jwxt_connect_timeout,
            read=settings.jwxt_read_timeout,
        )
        client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            verify=not settings.jwxt_insecure_ssl,  # 证书过期时这里会是 False
            follow_redirects=False,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/143.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,image/apng,*/*;"
                    "q=0.8,application/signed-exchange;v=b3;q=0.7"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        return client

    async def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        教务系统登录（雏形版）：
        - 先搭好 HTTP 请求和 SSL 设置
        - 真正加密逻辑 / HTML 判断成功与否，后面单独一步搞

        返回: (是否成功, 提示消息)
        """
        # TODO: 这里需要根据你现有的 JwxtCrypto(Dart 版) 或 Python 脚本实现加密:
        # encoded = jwxt_crypto_encode(username, password)
        encoded = "TODO-implement-encoded"  # 占位符

        form_data = {
            "userAccount": username,
            "userPassword": "",
            "encoded": encoded,
        }

        async with self._build_client() as client:
            try:
                resp = await client.post("/jsxsd/xk/LoginToXk", data=form_data)

            except httpx.RequestError as exc:
                # 网络错误（DNS、连接失败等）
                return False, f"无法连接教务系统: {exc}"

        # 下面的逻辑是骨架，需要你根据实际返回页面调整
        if resp.status_code >= 500:
            return False, f"教务系统服务异常: HTTP {resp.status_code}"

        # TODO: 根据 resp.headers["Location"] 或 resp.text 判断是否登录成功
        # 比如：
        # - 如果 Location 指向 /jsxsd/framework/xsMain.jsp 则视为成功
        # - 如果页面包含 “用户名或密码错误” 字样则视为失败
        # 这里先返回一个占位信息，下一步我们再专门写“登录判断 + 抓包调试”。

        return False, "登录逻辑尚未实现（TODO）"

    async def fetch_profile(self) -> JwxtUserProfile:
        """
        获取个人信息页面并解析为 JwxtUserProfile

        这里先放一个 TODO，等登录逻辑稳定后，我们再专门写 HTML 解析。
        """
        # TODO: 实现抓取 /jsxsd/grxx/xsxx?xx=1 之类的个人信息页面
        # 然后用正则 / lxml / selectolax 解析出：
        # - 学号
        # - 姓名
        # - 学院
        # - 专业
        # - 班级
        # - 入学年份
        # - 学习层次
        raise NotImplementedError("fetch_profile 尚未实现")
