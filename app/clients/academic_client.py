# app/clients/academic_client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

import httpx
import html as _html
from app.core.config import settings
from app.utils.academic_crypto import academic_encode

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

import re


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
        self._transport = transport  #  现在 transport 有定义了（参数传入）

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

        #  只有测试注入 transport 时才传（httpx 的 transport 是“低层发送器”）
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
            form = {
                "userAccount": username,
                "userPassword": password,
                "encoded": academic_encode(username, password),
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

    def _looks_like_login_page(self, text: str) -> bool:
        # 兼容多种“回到登录页”的表现形式
        t = text or ""
        return ("LoginToXk" in t) or ("用户登录" in t) or ("统一身份认证" in t)

    async def fetch_html(
            self,
            path: str,
            *,
            cookies: Dict[str, str],
            method: str = "GET",
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            request_id: Optional[str] = None,
            content_type_form: bool = False,
    ) -> tuple[int, Optional[str], str]:
        extra_headers: Dict[str, str] = {}
        if content_type_form:
            extra_headers["Content-Type"] = "application/x-www-form-urlencoded"

        kw = self._client_kwargs(request_id=request_id, extra_headers=extra_headers)
        async with httpx.AsyncClient(**kw) as client:
            client.cookies.update(cookies)
            if method.upper() == "POST":
                resp = await client.post(path, params=params, data=data)
            else:
                resp = await client.get(path, params=params)

        location = resp.headers.get("location")
        text = resp.text or ""
        return resp.status_code, location, text

    async def fetch_semesters(
            self,
            *,
            cookies: Dict[str, str],
            request_id: Optional[str] = None,
    ) -> dict[str, Any]:
        status, location, html = await self.fetch_html(
            "/jsxsd/kscj/cjcx_query",
            cookies=cookies,
            method="GET",
            request_id=request_id,
        )
        sample = (html or "")[:200]

        if status in (302, 303) or self._looks_like_login_page(html):
            return {
                "success": False,
                "status_code": status,
                "location": location,
                "semesters": [],
                "html_sample": sample,
                "reason": "SESSION_EXPIRED",
            }

        semesters: list[dict[str, str]] = []
        if BeautifulSoup is not None:
            soup = BeautifulSoup(html, "html.parser")
            sel = soup.select_one("#kksj")
            if sel:
                for opt in sel.find_all("option"):
                    v = (opt.get("value") or "").strip()
                    label = (opt.get_text() or "").strip()
                    if v or label:
                        semesters.append({"value": v, "label": label})
        else:
            # fallback：正则抓 option
            for m in re.finditer(
                    r'<option[^>]*value=["\']?([^"\'> ]*)["\']?[^>]*>([^<]*)</option>',
                    html,
                    re.I,
            ):
                v = (m.group(1) or "").strip()
                label = (m.group(2) or "").strip()
                if v or label:
                    semesters.append({"value": v, "label": label})

        return {
            "success": True,
            "status_code": status,
            "location": location,
            "semesters": semesters,
            "html_sample": sample,
        }

    async def fetch_grades(
            self,
            *,
            cookies: Dict[str, str],
            semester: str = "",
            request_id: Optional[str] = None,
    ) -> dict[str, Any]:
        # 强智/正方系常见：POST /jsxsd/kscj/cjcx_list {kksj,kcxz,kcmc,xsfs}
        data = {"kksj": semester or "", "kcxz": "", "kcmc": "", "xsfs": "all"}
        status, location, html = await self.fetch_html(
            "/jsxsd/kscj/cjcx_list",
            cookies=cookies,
            method="POST",
            data=data,
            request_id=request_id,
            content_type_form=True,
        )
        sample = (html or "")[:200]

        if status in (302, 303) or self._looks_like_login_page(html):
            return {
                "success": False,
                "status_code": status,
                "location": location,
                "rows": [],
                "headers": [],
                "html_sample": sample,
                "reason": "SESSION_EXPIRED",
            }

        headers: list[str] = []
        rows: list[dict[str, str]] = []

        if BeautifulSoup is not None:
            soup = BeautifulSoup(html, "html.parser")
            table = soup.select_one("#dataList")
            if table:
                ths = table.select("tr th")
                headers = [(th.get_text() or "").strip() for th in ths if (th.get_text() or "").strip()]
                for tr in table.select("tr")[1:]:
                    tds = [(td.get_text() or "").strip() for td in tr.select("td")]
                    if not any(tds):
                        continue
                    if headers and len(tds) >= len(headers):
                        row = {headers[i]: tds[i] for i in range(len(headers))}
                    else:
                        row = {str(i): tds[i] for i in range(len(tds))}
                    rows.append(row)

        return {
            "success": True,
            "status_code": status,
            "location": location,
            "headers": headers,
            "rows": rows,
            "html_sample": sample,
        }

    def _clean_text(self, s: str) -> str:
        # &nbsp; / &#160; / \xa0 都可能出现
        s = _html.unescape(s or "")
        s = s.replace("\xa0", " ").replace("&nbsp;", " ")
        return s.strip()

    def _parse_user_info_html(self, html: str) -> dict[str, str] | None:
        html = html or ""
        table_kv: dict[str, str] = {}
        all_text = ""

        HEADER_BAD_VALUES = {"与本人关系", "关系", "称谓", "姓名"}  # 可按学校页面再补充

        if BeautifulSoup is not None:
            soup = BeautifulSoup(html, "html.parser")
            for tr in soup.select("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 2:
                    k = self._clean_text(tds[0].get_text(" ", strip=True)).rstrip("：:")
                    v = self._clean_text(tds[1].get_text(" ", strip=True))

                    #  跳过表头：<td>姓名</td><td>与本人关系</td>
                    if k == "姓名" and v in HEADER_BAD_VALUES:
                        continue

                    # 也可再跳过一些“整行都是表头词”的情况
                    if k in HEADER_BAD_VALUES and v in HEADER_BAD_VALUES:
                        continue

                    if k and v:
                        table_kv[k] = v

            all_text = self._clean_text(soup.get_text(" ", strip=True))
        else:
            all_text = self._clean_text(html)

        def pick_inline(label: str) -> str:
            m = re.search(rf">{re.escape(label)}[：:]\s*([^<]+)<", html, re.I)
            return self._clean_text(m.group(1)) if m else ""

        def pick_table(label: str) -> str:
            return table_kv.get(label, "")

        def pick_text(label: str) -> str:
            m = re.search(rf"{re.escape(label)}[：:]\s*([^\s]+)", all_text, re.I)
            return self._clean_text(m.group(1)) if m else ""

        #  新增：专门从 <td>标签对里取值，并过滤表头词
        def pick_td_value(label: str) -> str:
            pattern = rf">{re.escape(label)}</td>\s*<td[^>]*>\s*(?:&nbsp;|&#160;)?\s*([^<]+)<"
            for m in re.finditer(pattern, html, flags=re.I | re.S):
                v = self._clean_text(m.group(1))
                if v and v not in HEADER_BAD_VALUES:
                    return v
            return ""

        # name 最容易踩雷：优先 td-pair 解析，其次 table_kv/inline/text
        name = (
                pick_td_value("姓名")
                or pick_table("学生姓名")
                or pick_table("姓名")
                or pick_inline("学生姓名")
                or pick_inline("姓名")
                or pick_text("姓名")
        )
        if name in HEADER_BAD_VALUES:
            name = ""

        college = pick_table("院系") or pick_inline("院系") or pick_inline("所属院系") or pick_text(
            "院系") or pick_text("所属院系")
        major = pick_table("专业") or pick_inline("专业") or pick_inline("专业名称") or pick_text("专业")
        className = pick_table("班级") or pick_inline("班级") or pick_inline("班级名称") or pick_text("班级")

        studyLevel = pick_td_value("学习层次") or pick_table("学习层次") or pick_inline("学习层次") or pick_text(
            "学习层次")
        if studyLevel in HEADER_BAD_VALUES:
            studyLevel = ""

        # 入学年份：优先从“入学日期”里提取年份
        enrollmentYear = ""
        enroll_raw = pick_td_value("入学日期") or pick_inline("入学日期") or pick_text("入学日期")
        if enroll_raw:
            ym = re.search(r"(\d{4})", enroll_raw)
            if ym:
                enrollmentYear = ym.group(1)

        data = {
            "name": name,
            "college": college,
            "major": major,
            "className": className,
            "enrollmentYear": enrollmentYear,
            "studyLevel": studyLevel,
        }

        # 全空就返回 None
        if not any(v for v in data.values()):
            return None
        return data

    async def fetch_me(
            self,
            *,
            cookies: Dict[str, str],
            request_id: Optional[str] = None,
    ) -> dict[str, Any]:
        # 先用原来的路径；如果站点不同，再加候选（不算改结构）
        candidates = [
            ("/jsxsd/grxx/xsxx", None),
            ("/jsxsd/framework/xsMain_new.jsp", {"t1": "1"}),  # 有些学校个人信息在首页框架里
        ]

        last = None
        for path, params in candidates:
            status, location, html = await self.fetch_html(
                path,
                cookies=cookies,
                method="GET",
                params=params,
                request_id=request_id,
            )
            sample = (html or "")[:200]
            last = {"status_code": status, "location": location, "html_sample": sample, "path": path}

            if status in (302, 303) or self._looks_like_login_page(html):
                return {"success": False, "reason": "SESSION_EXPIRED", "data": None, **last}

            data = self._parse_user_info_html(html)
            if data:
                return {"success": True, "data": data, **last}

        return {"success": False, "reason": "NOT_FOUND", "data": None, **(last or {})}

    async def fetch_schedule(
        self,
        *,
        cookies: Dict[str, str],
        xnxq: str = "",
        request_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        获取课程表（强智系常见）：GET /jsxsd/xskb/xskb_list.do?xnxq01id=2024-2025-1
        返回结构：
        {
          success, status_code, location,
          semester, currentWeek, courses:[{name,teacher,location,weekday,startSection,endSection,weekRange,weeks}],
          html_sample
        }
        """
        params = {"xnxq01id": xnxq} if xnxq else None
        status, location, html = await self.fetch_html(
            "/jsxsd/xskb/xskb_list.do",
            cookies=cookies,
            method="GET",
            params=params,
            request_id=request_id,
        )
        sample = (html or "")[:200]

        if status in (302, 303) or self._looks_like_login_page(html):
            return {
                "success": False,
                "status_code": status,
                "location": location,
                "semester": xnxq or "",
                "currentWeek": None,
                "courses": [],
                "html_sample": sample,
                "reason": "SESSION_EXPIRED",
            }

        parsed = self._parse_schedule_html(html or "", xnxq=xnxq)
        return {
            "success": True,
            "status_code": status,
            "location": location,
            "html_sample": sample,
            **parsed,
        }

    # -----------------------------
    # Schedule HTML parsing helpers
    # -----------------------------

    def _parse_schedule_html(self, html: str, *, xnxq: str = "") -> dict[str, Any]:
        semester = xnxq or self._extract_semester(html) or ""
        current_week = self._extract_current_week(html)

        # 节次映射：每行（大节）对应的起止小节
        section_mapping = [
            (1, 2),
            (3, 4),
            (5, 6),
            (7, 8),
            (9, 10),
            (11, 12),
        ]

        courses: list[dict[str, Any]] = []

        # 优先 BS4
        if BeautifulSoup is not None:
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table", attrs={"id": re.compile(r"^kbtable$", re.I)})
            if not table:
                # 有些学校 id 可能不完全一致，兜底：包含 kbtable 的
                table = soup.find("table", attrs={"id": re.compile(r"kbtable", re.I)})

            if not table:
                return {"semester": semester, "currentWeek": current_week, "courses": []}

            rows = table.find_all("tr")
            data_row_index = 0

            for tr in rows:
                tds = tr.find_all("td")
                if not tds:
                    continue

                # 跳过备注行
                if "备注" in tr.get_text(strip=True):
                    continue

                if data_row_index >= len(section_mapping):
                    data_row_index += 1
                    continue

                start_sec, end_sec = section_mapping[data_row_index]

                weekday = 1
                for td in tds:
                    if weekday > 7:
                        break

                    # 判断是否是“节次/时间”列：通常没有 kbcontent/kbcontent1
                    has_course_div = (
                        td.find("div", class_=re.compile(r"\bkbcontent\b", re.I)) is not None
                        or td.find("div", class_=re.compile(r"\bkbcontent1\b", re.I)) is not None
                    )
                    if not has_course_div:
                        # 很像“节次列”的文本就跳过且不递增 weekday
                        t = td.get_text(" ", strip=True)
                        if re.search(r"(第?\s*\d+\s*(大节|节)|节次|上午|下午|晚上)", t):
                            continue
                        # 否则当作某天的空格子（递增 weekday）
                        weekday += 1
                        continue

                    w = weekday
                    weekday += 1

                    # 先找详细 kbcontent，再回退 kbcontent1
                    divs = td.find_all("div", class_=re.compile(r"\bkbcontent\b", re.I))
                    if not divs:
                        divs = td.find_all("div", class_=re.compile(r"\bkbcontent1\b", re.I))

                    for div in divs:
                        inner = (div.decode_contents() or "").strip()
                        if not inner or inner == "&nbsp;":
                            continue

                        # 多门课分隔线：----- / ----------（前后可能夹着 <br>）
                        blocks = re.split(
                            r"(?:<br\s*/?>\s*)?-{5,}\s*(?:<br\s*/?>\s*)?|-{10,}",
                            inner,
                            flags=re.I,
                        )

                        for b in blocks:
                            b = (b or "").strip()
                            if not b or b in ("<br>", "<br/>", "&nbsp;"):
                                continue
                            if "<font" not in b and "font" not in b:
                                continue

                            c = self._parse_course_block(
                                b,
                                weekday=w,
                                start_section=start_sec,
                                end_section=end_sec,
                            )
                            if c:
                                courses.append(c)

                data_row_index += 1

            courses = self._merge_courses(courses)
            return {"semester": semester, "currentWeek": current_week, "courses": courses}

        # 无 BS4：正则兜底（简化版）
        table_m = re.search(
            r"""<table[^>]*id=["']kbtable["'][^>]*>(.*?)</table>""",
            html,
            re.I | re.S,
        )
        if not table_m:
            return {"semester": semester, "currentWeek": current_week, "courses": []}

        table_html = table_m.group(1) or ""
        row_ms = list(re.finditer(r"<tr[^>]*>(.*?)</tr>", table_html, re.I | re.S))
        data_row_index = 0

        for rm in row_ms:
            row_html = rm.group(1) or ""
            if "<td" not in row_html:
                continue
            if "备注" in row_html:
                continue
            if data_row_index >= len(section_mapping):
                data_row_index += 1
                continue

            start_sec, end_sec = section_mapping[data_row_index]
            cell_ms = list(re.finditer(r"<td[^>]*>(.*?)</td>", row_html, re.I | re.S))

            weekday = 1
            for cm in cell_ms:
                if weekday > 7:
                    break
                cell = cm.group(1) or ""
                if "kbcontent" not in cell and "kbcontent1" not in cell:
                    # 节次列：不递增 weekday
                    if re.search(r"(第?\s*\d+\s*(大节|节)|节次|上午|下午|晚上)", re.sub(r"<[^>]+>", "", cell)):
                        continue
                    weekday += 1
                    continue

                w = weekday
                weekday += 1

                div_ms = list(re.finditer(r"""<div[^>]*class=["']kbcontent["'][^>]*>(.*?)</div>""", cell, re.I | re.S))
                if not div_ms:
                    div_ms = list(re.finditer(r"""<div[^>]*class=["']kbcontent1["'][^>]*>(.*?)</div>""", cell, re.I | re.S))

                for dm in div_ms:
                    inner = (dm.group(1) or "").strip()
                    if not inner:
                        continue
                    blocks = re.split(r"(?:<br\s*/?>\s*)?-{5,}\s*(?:<br\s*/?>\s*)?|-{10,}", inner, flags=re.I)
                    for b in blocks:
                        b = (b or "").strip()
                        if not b or "<font" not in b:
                            continue
                        c = self._parse_course_block(b, weekday=w, start_section=start_sec, end_section=end_sec)
                        if c:
                            courses.append(c)

            data_row_index += 1

        courses = self._merge_courses(courses)
        return {"semester": semester, "currentWeek": current_week, "courses": courses}

    def _parse_course_block(self, html: str, *, weekday: int, start_section: int, end_section: int) -> Optional[dict[str, Any]]:
        clean = re.sub(r"\s+", " ", html).strip()

        # 课程名：第一个标签前的文本（或 <br> 后的文本）
        name = ""
        m1 = re.match(r"^([^<]+)", clean)
        if m1:
            name = (m1.group(1) or "").replace("&nbsp;", "").strip()
        if not name:
            m2 = re.search(r"<br\s*/?>\s*([^<]+)", clean, re.I)
            if m2:
                name = (m2.group(1) or "").replace("&nbsp;", "").strip()
        if not name or name == "&nbsp;":
            return None

        # 教师（title 可能是 “老师” 或 “教师”）
        teacher = None
        mt = re.search(
            r"""<font[^>]*title=["']?(?:任课)?(?:老师|教师)["']?[^>]*>\s*([^<]+)\s*</font>""",
            html,
            re.I,
        )
        if mt:
            teacher = (mt.group(1) or "").replace("&nbsp;", "").strip() or None

        # 周次（可能带 [01-02节]）
        week_range = None
        mw = re.search(
            r"""<font[^>]*title=["']?周次[^"']*["']?[^>]*>\s*([^<]+)\s*</font>""",
            html,
            re.I,
        )
        weeks: list[int] = []
        if mw:
            week_range = (mw.group(1) or "").replace("&nbsp;", "").strip() or None
            if week_range:
                weeks = self._parse_week_range(week_range)

        # 教室
        location = None
        ml = re.search(
            r"""<font[^>]*title=["']?教室["']?[^>]*>\s*([^<]+)\s*</font>""",
            html,
            re.I,
        )
        if ml:
            location = (ml.group(1) or "").replace("&nbsp;", "").strip() or None

        if not weeks:
            weeks = list(range(1, 21))  # 兜底 1-20 周

        return {
            "name": name,
            "teacher": teacher,
            "location": location,
            "weekday": int(weekday),
            "startSection": int(start_section),
            "endSection": int(end_section),
            "weekRange": week_range,
            "weeks": weeks,
        }

    def _parse_week_range(self, week_str: str) -> list[int]:
        weeks: set[int] = set()
        s = week_str or ""

        is_single = "单" in s
        is_double = "双" in s

        # 去掉 [01-02节] 之类
        s = re.sub(r"\[.*?\]", "", s)
        # 去掉 (周) / 周
        s = s.replace("(周)", "").replace("周", "")
        s = s.strip()

        # 只保留周次部分：例如 "2-16" / "2,4-7,9-16"
        parts = [p.strip() for p in s.split(",") if p.strip()]
        for p in parts:
            m = re.match(r"^(\d+)\s*-\s*(\d+)$", p)
            if m:
                a = int(m.group(1))
                b = int(m.group(2))
                for i in range(a, b + 1):
                    if is_single and i % 2 == 0:
                        continue
                    if is_double and i % 2 == 1:
                        continue
                    weeks.add(i)
            else:
                try:
                    i = int(p)
                    if is_single and i % 2 == 0:
                        continue
                    if is_double and i % 2 == 1:
                        continue
                    weeks.add(i)
                except Exception:
                    pass

        return sorted(weeks)

    def _merge_courses(self, courses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not courses:
            return courses

        grouped: dict[tuple, dict[str, Any]] = {}
        for c in courses:
            key = (
                c.get("name") or "",
                int(c.get("weekday") or 0),
                int(c.get("startSection") or 0),
                int(c.get("endSection") or 0),
                c.get("teacher") or "",
                c.get("location") or "",
            )
            if key not in grouped:
                grouped[key] = dict(c)
                grouped[key]["weeks"] = set(c.get("weeks") or [])
            else:
                grouped[key]["weeks"].update(c.get("weeks") or [])

        out: list[dict[str, Any]] = []
        for v in grouped.values():
            v["weeks"] = sorted([int(x) for x in v.get("weeks") or []])
            out.append(v)

        return out

    def _extract_current_week(self, html: str) -> Optional[int]:
        # 常见：第12周 / 当前周次：第12周
        m = re.search(r"第\s*(\d+)\s*周", html or "")
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
        return None

    def _extract_semester(self, html: str) -> Optional[str]:
        # 1) 页面上直接出现：学年学期：2024-2025-1
        m = re.search(r"学年学期\s*[：:]\s*([0-9]{4}\s*-\s*[0-9]{4}\s*-\s*\d)", html or "")
        if m:
            return re.sub(r"\s+", "", m.group(1))

        # 2) 下拉选中 option
        m = re.search(
            r"""<option[^>]*selected[^>]*value=["']([^"']+)["']""",
            html or "",
            re.I,
        )
        if m:
            return (m.group(1) or "").strip() or None

        # 3) 参数里出现
        m = re.search(r"xnxq01id=([0-9]{4}-[0-9]{4}-\d)", html or "", re.I)
        if m:
            return (m.group(1) or "").strip() or None

        return None
