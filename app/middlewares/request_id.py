from __future__ import annotations

import uuid
from fastapi import Request
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-ID"


async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    request.state.request_id = rid  # 业务里也可以取用

    response: Response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = rid
    return response
