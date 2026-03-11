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
        return {"profile": {"location": "Warsaw"}, "items": [{"id": "match-1"}]}


def test_webapp_index_route_serves_html() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/webapp")

    assert response.status_code == 200
    assert "Helly Dashboard" in response.text


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

    assert auth_response.status_code == 200
    assert auth_response.json()["session"]["role"] == "candidate"
    assert session_response.status_code == 200
    assert session_response.json()["capabilities"]["candidateDashboard"] is True
    assert candidate_response.status_code == 200
    assert candidate_response.json()["items"][0]["id"] == "match-1"
