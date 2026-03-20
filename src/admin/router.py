from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.admin.auth import issue_admin_session_for_pin
from src.admin.service import AdminService
from src.admin.session import (
    ADMIN_SESSION_COOKIE_NAME,
    AdminSessionError,
    verify_admin_session_token,
)
from src.config.settings import get_settings
from src.db.dependencies import get_db_session


ADMIN_STATIC_DIR = Path(__file__).resolve().parent / "static"

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminPinAuthRequest(BaseModel):
    pin: str = Field(default="")


class AdminUserBlockRequest(BaseModel):
    userIds: List[str]
    reason: Optional[str] = None


class AdminUserUnblockRequest(BaseModel):
    userIds: List[str]


class AdminMessageRequest(BaseModel):
    userIds: List[str]
    text: str


def _service(db: Session = Depends(get_db_session)) -> AdminService:
    return AdminService(db)


def _admin_session_context(request: Request):
    token = request.cookies.get(ADMIN_SESSION_COOKIE_NAME, "")
    settings = get_settings()
    try:
        return verify_admin_session_token(
            token=token,
            secret=settings.effective_admin_session_secret,
        )
    except AdminSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.get("", response_class=FileResponse)
@router.get("/", response_class=FileResponse)
def admin_index():
    return FileResponse(ADMIN_STATIC_DIR / "index.html")


@router.post("/api/auth/pin")
def authenticate_admin_pin(
    payload: AdminPinAuthRequest,
    response: Response,
):
    try:
        token, session_context = issue_admin_session_for_pin(provided_pin=payload.pin)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    settings = get_settings()
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.admin_session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=not settings.is_dev,
        path="/",
    )
    return {
        "session": session_context.to_public_dict(),
        "authenticated": True,
    }


@router.post("/api/auth/logout")
def logout_admin(response: Response):
    response.delete_cookie(key=ADMIN_SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.get("/api/session")
def admin_session(
    session_context=Depends(_admin_session_context),
    service: AdminService = Depends(_service),
):
    return service.build_session_payload(session_context)


@router.get("/api/users")
def admin_users(
    role: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    candidate_state: Optional[str] = Query(default=None),
    vacancy_state: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    session_context=Depends(_admin_session_context),
    service: AdminService = Depends(_service),
):
    return service.list_users(
        session_context,
        role=role,
        status_filter=status_filter,
        candidate_state=candidate_state,
        vacancy_state=vacancy_state,
        search=search,
    )


@router.get("/api/users/{user_id}")
def admin_user_detail(
    user_id: str,
    session_context=Depends(_admin_session_context),
    service: AdminService = Depends(_service),
):
    return service.get_user_detail(session_context, user_id=user_id)


@router.post("/api/users/block")
def admin_block_users(
    payload: AdminUserBlockRequest,
    session_context=Depends(_admin_session_context),
    service: AdminService = Depends(_service),
):
    return service.block_users(session_context, user_ids=payload.userIds, reason=payload.reason)


@router.post("/api/users/unblock")
def admin_unblock_users(
    payload: AdminUserUnblockRequest,
    session_context=Depends(_admin_session_context),
    service: AdminService = Depends(_service),
):
    return service.unblock_users(session_context, user_ids=payload.userIds)


@router.delete("/api/users/{user_id}")
def admin_delete_user(
    user_id: str,
    session_context=Depends(_admin_session_context),
    service: AdminService = Depends(_service),
):
    return service.delete_user(session_context, user_id=user_id)


@router.get("/api/matches")
def admin_matches(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    fit_band: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    session_context=Depends(_admin_session_context),
    service: AdminService = Depends(_service),
):
    return service.list_matches(
        session_context,
        status_filter=status_filter,
        fit_band=fit_band,
        search=search,
    )


@router.get("/api/matches/{match_id}")
def admin_match_detail(
    match_id: str,
    session_context=Depends(_admin_session_context),
    service: AdminService = Depends(_service),
):
    return service.get_match_detail(session_context, match_id=match_id)


@router.get("/api/analytics/overview")
def admin_analytics_overview(
    session_context=Depends(_admin_session_context),
    service: AdminService = Depends(_service),
):
    return service.analytics_overview(session_context)


@router.post("/api/messages/preview")
def admin_message_preview(
    payload: AdminMessageRequest,
    session_context=Depends(_admin_session_context),
    service: AdminService = Depends(_service),
):
    return service.preview_message(
        session_context,
        user_ids=payload.userIds,
        message_text=payload.text,
    )


@router.post("/api/messages/send")
def admin_message_send(
    payload: AdminMessageRequest,
    session_context=Depends(_admin_session_context),
    service: AdminService = Depends(_service),
):
    return service.send_message(
        session_context,
        user_ids=payload.userIds,
        message_text=payload.text,
    )
