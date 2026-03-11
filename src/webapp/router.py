from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.dependencies import get_db_session
from src.webapp.service import WEBAPP_STATIC_DIR, WebAppService


router = APIRouter(prefix="/webapp", tags=["webapp"])


class TelegramWebAppAuthRequest(BaseModel):
    initData: str


class CandidateCvChallengeFinishRequest(BaseModel):
    attemptId: str
    score: int
    livesLeft: int
    stageReached: int
    won: bool
    result: Optional[dict] = None


class CandidateCvChallengeProgressRequest(BaseModel):
    attemptId: str
    score: int
    livesLeft: int
    stageReached: int
    progress: Optional[dict] = None


def _service(db: Session = Depends(get_db_session)) -> WebAppService:
    return WebAppService(db)


def _session_context(
    authorization: str = Header(default=""),
    service: WebAppService = Depends(_service),
):
    return service.get_session_from_auth_header(authorization)


@router.get("", response_class=FileResponse)
@router.get("/", response_class=FileResponse)
def webapp_index():
    return FileResponse(WEBAPP_STATIC_DIR / "index.html")


@router.get("/cv-challenge", response_class=FileResponse)
@router.get("/cv-challenge/", response_class=FileResponse)
def cv_challenge_index():
    return FileResponse(WEBAPP_STATIC_DIR / "cv-challenge.html")


@router.post("/api/auth/telegram")
def authenticate_telegram_webapp(
    payload: TelegramWebAppAuthRequest,
    service: WebAppService = Depends(_service),
):
    return service.authenticate_init_data(payload.initData)


@router.get("/api/session")
def webapp_session(
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.build_session_payload(session_context)


@router.get("/api/candidate/opportunities")
def candidate_opportunities(
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.list_candidate_opportunities(session_context)


@router.get("/api/candidate/opportunities/{match_id}")
def candidate_opportunity_detail(
    match_id: str,
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.get_candidate_opportunity_detail(session_context, match_id)


@router.get("/api/candidate/cv-challenge/bootstrap")
def candidate_cv_challenge_bootstrap(
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.bootstrap_candidate_cv_challenge(session_context)


@router.post("/api/candidate/cv-challenge/finish")
def candidate_cv_challenge_finish(
    payload: CandidateCvChallengeFinishRequest,
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.finish_candidate_cv_challenge(
        session_context,
        attempt_id=payload.attemptId,
        score=payload.score,
        lives_left=payload.livesLeft,
        stage_reached=payload.stageReached,
        won=payload.won,
        result_json=payload.result,
    )


@router.post("/api/candidate/cv-challenge/progress")
def candidate_cv_challenge_progress(
    payload: CandidateCvChallengeProgressRequest,
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.save_candidate_cv_challenge_progress(
        session_context,
        attempt_id=payload.attemptId,
        score=payload.score,
        lives_left=payload.livesLeft,
        stage_reached=payload.stageReached,
        progress_json=payload.progress,
    )


@router.get("/api/hiring-manager/vacancies")
def hiring_manager_vacancies(
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.list_manager_vacancies(session_context)


@router.get("/api/hiring-manager/vacancies/{vacancy_id}")
def hiring_manager_vacancy_detail(
    vacancy_id: str,
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.get_manager_vacancy_detail(session_context, vacancy_id)


@router.get("/api/hiring-manager/vacancies/{vacancy_id}/matches")
def hiring_manager_vacancy_matches(
    vacancy_id: str,
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.list_manager_vacancy_matches(session_context, vacancy_id)


@router.get("/api/hiring-manager/matches/{match_id}")
def hiring_manager_match_detail(
    match_id: str,
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.get_manager_match_detail(session_context, match_id)


@router.get("/api/admin/vacancies")
def admin_vacancies(
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.list_admin_vacancies(session_context)


@router.get("/api/admin/vacancies/{vacancy_id}")
def admin_vacancy_detail(
    vacancy_id: str,
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.get_admin_vacancy_detail(session_context, vacancy_id)


@router.get("/api/admin/vacancies/{vacancy_id}/matches")
def admin_vacancy_matches(
    vacancy_id: str,
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.list_admin_vacancy_matches(session_context, vacancy_id)


@router.get("/api/admin/matches/{match_id}")
def admin_match_detail(
    match_id: str,
    session_context=Depends(_session_context),
    service: WebAppService = Depends(_service),
):
    return service.get_admin_match_detail(session_context, match_id)
