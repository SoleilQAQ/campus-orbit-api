from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query

from app.services.academic_service import AcademicService, get_academic_service

router = APIRouter(prefix="/api/academic", tags=["academic"])


@router.get("/health")
async def health(
    service: AcademicService = Depends(get_academic_service),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID"),
):
    return await service.health(request_id=x_request_id)


@router.post("/login")
async def login(
    payload: dict,
    service: AcademicService = Depends(get_academic_service),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID"),
):
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "").strip()
    return await service.login(username=username, password=password, request_id=x_request_id)


@router.post("/logout")
async def logout(
    service: AcademicService = Depends(get_academic_service),
    x_academic_session: str = Header(..., alias="X-Academic-Session"),
):
    return await service.logout(session_id=x_academic_session)


@router.get("/me")
async def me(
    service: AcademicService = Depends(get_academic_service),
    x_academic_session: str = Header(..., alias="X-Academic-Session"),
    refresh: bool = Query(False),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID"),
):
    return await service.me(session_id=x_academic_session, request_id=x_request_id, refresh=refresh)


@router.get("/semesters")
async def semesters(
    service: AcademicService = Depends(get_academic_service),
    x_academic_session: str = Header(..., alias="X-Academic-Session"),
    refresh: bool = Query(False),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID"),
):
    return await service.semesters(session_id=x_academic_session, request_id=x_request_id, refresh=refresh)


@router.get("/grades")
async def grades(
    service: AcademicService = Depends(get_academic_service),
    x_academic_session: str = Header(..., alias="X-Academic-Session"),
    semester: str = Query(default=""),
    refresh: bool = Query(False),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID"),
):
    return await service.grades(session_id=x_academic_session, semester=semester, request_id=x_request_id, refresh=refresh)


@router.get("/schedule")
async def schedule(
    service: AcademicService = Depends(get_academic_service),
    x_academic_session: str = Header(..., alias="X-Academic-Session"),
    xnxq: str = Query(default=""),
    refresh: bool = Query(False),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID"),
):
    return await service.schedule(session_id=x_academic_session, xnxq=xnxq, request_id=x_request_id, refresh=refresh)
