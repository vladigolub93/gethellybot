import importlib

from fastapi.testclient import TestClient

from apps.api.main import create_app
from src.db.dependencies import get_db_session

webapp_router_module = importlib.import_module("src.webapp.router")


class FakeWebAppService:
    def __init__(self, _db):
        return None

    def authenticate_init_data(self, init_data):
        return {
            "sessionToken": "token-1",
            "session": {
                "telegramUserId": 123456,
                "userId": "user-1",
                "role": "candidate",
                "displayName": "Vlad Golub",
            },
        }

    def get_session_from_auth_header(self, authorization_header):
        if authorization_header != "Bearer token-1":
            raise AssertionError("unexpected auth header")
        return type(
            "SessionContext",
            (),
            {
                "role": "candidate",
                "to_public_dict": lambda self: {
                    "telegramUserId": 123456,
                    "userId": "user-1",
                    "role": "candidate",
                    "displayName": "Vlad Golub",
                },
            },
        )()

    def build_session_payload(self, session_context):
        return {
            "session": session_context.to_public_dict(),
            "capabilities": {
                "candidateDashboard": True,
                "managerDashboard": False,
                "adminDashboard": False,
            },
        }

    def list_candidate_opportunities(self, _session_context):
        return {
            "profile": {"location": "Warsaw"},
            "cvChallenge": {"eligible": True, "launchUrl": "https://example.com/webapp/cv-challenge"},
            "items": [{"id": "match-1"}],
        }

    def get_candidate_profile_detail(self, _session_context):
        return {
            "profile": {
                "id": "profile-1",
                "name": "Vlad Golub",
                "summary": {"approvalSummaryText": "Backend engineer"},
            }
        }

    def bootstrap_candidate_cv_challenge(self, _session_context):
        return {
            "eligible": True,
            "attempt": {"id": "attempt-1"},
            "challenge": {"title": "Helly CV Challenge"},
        }

    def finish_candidate_cv_challenge(
        self,
        _session_context,
        *,
        attempt_id,
        score,
        lives_left,
        stage_reached,
        won,
        result_json,
        ):
        return {
            "attempt": {
                "id": attempt_id,
                "score": score,
                "livesLeft": lives_left,
                "stageReached": stage_reached,
                "won": won,
                "result": result_json,
            }
        }

    def save_candidate_cv_challenge_progress(
        self,
        _session_context,
        *,
        attempt_id,
        score,
        lives_left,
        stage_reached,
        progress_json,
    ):
        return {
            "attempt": {
                "id": attempt_id,
                "score": score,
                "livesLeft": lives_left,
                "stageReached": stage_reached,
                "progress": progress_json,
            }
        }


def test_webapp_index_route_serves_html() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/webapp")

    assert response.status_code == 200
    assert "<title>Helly</title>" in response.text


def test_cv_challenge_route_serves_html() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/webapp/cv-challenge")

    assert response.status_code == 200
    assert "Helly CV Challenge" in response.text


def test_webapp_auth_and_candidate_routes(monkeypatch) -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: object()
    monkeypatch.setattr(webapp_router_module, "WebAppService", FakeWebAppService)
    client = TestClient(app)

    auth_response = client.post("/webapp/api/auth/telegram", json={"initData": "signed-data"})
    session_response = client.get("/webapp/api/session", headers={"Authorization": "Bearer token-1"})
    candidate_response = client.get(
        "/webapp/api/candidate/opportunities",
        headers={"Authorization": "Bearer token-1"},
    )
    profile_response = client.get(
        "/webapp/api/candidate/profile",
        headers={"Authorization": "Bearer token-1"},
    )
    challenge_bootstrap_response = client.get(
        "/webapp/api/candidate/cv-challenge/bootstrap",
        headers={"Authorization": "Bearer token-1"},
    )
    challenge_finish_response = client.post(
        "/webapp/api/candidate/cv-challenge/finish",
        headers={"Authorization": "Bearer token-1"},
        json={
            "attemptId": "attempt-1",
            "score": 9,
            "livesLeft": 1,
            "stageReached": 3,
            "won": True,
            "result": {"missedSkills": ["Docker"]},
        },
    )
    challenge_progress_response = client.post(
        "/webapp/api/candidate/cv-challenge/progress",
        headers={"Authorization": "Bearer token-1"},
        json={
            "attemptId": "attempt-1",
            "score": 4,
            "livesLeft": 2,
            "stageReached": 2,
            "progress": {"score": 4, "objects": [{"text": "React"}]},
        },
    )

    assert auth_response.status_code == 200
    assert auth_response.json()["session"]["role"] == "candidate"
    assert session_response.status_code == 200
    assert session_response.json()["capabilities"]["candidateDashboard"] is True
    assert candidate_response.status_code == 200
    assert candidate_response.json()["items"][0]["id"] == "match-1"
    assert profile_response.status_code == 200
    assert profile_response.json()["profile"]["id"] == "profile-1"
    assert challenge_bootstrap_response.status_code == 200
    assert challenge_bootstrap_response.json()["attempt"]["id"] == "attempt-1"
    assert challenge_progress_response.status_code == 200
    assert challenge_progress_response.json()["attempt"]["livesLeft"] == 2
    assert challenge_finish_response.status_code == 200
    assert challenge_finish_response.json()["attempt"]["score"] == 9
