# app/api/academic.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.schemas.academic import AcademicLoginRequest
from app.services.academic_service import AcademicService, get_academic_service

router = APIRouter(prefix="/api/academic", tags=["academic"])


@router.get("/health")
async def academic_health(
    request: Request,
    service: AcademicService = Depends(get_academic_service),
):
    rid = getattr(request.state, "request_id", None)
    return await service.health(request_id=rid)


@router.post("/login")
async def academic_login(
    request: Request,
    body: AcademicLoginRequest,
    service: AcademicService = Depends(get_academic_service),
):
    rid = getattr(request.state, "request_id", None)
    return await service.login(body.username, body.password, request_id=rid)