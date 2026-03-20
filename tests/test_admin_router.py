import importlib
from types import SimpleNamespace

from fastapi.testclient import TestClient

from apps.api.main import create_app
from src.admin.session import AdminSessionContext


admin_router_module = importlib.import_module("src.admin.router")
admin_auth_module = importlib.import_module("src.admin.auth")


class FakeAdminService:
    def __init__(self):
        self.calls = []

    def build_session_payload(self, session_context):
        self.calls.append(("session", session_context.role))
        return {
            "session": session_context.to_public_dict(),
            "capabilities": {"adminDashboard": True},
        }

    def list_users(self, session_context, **kwargs):
        self.calls.append(("list_users", session_context.role, kwargs))
        return {
            "items": [{"id": "user-1"}],
            "filters": {},
            "counts": {"total": 1},
        }

    def get_user_detail(self, session_context, *, user_id):
        self.calls.append(("get_user_detail", session_context.role, user_id))
        return {"user": {"id": user_id}}

    def block_users(self, session_context, *, user_ids, reason=None):
        self.calls.append(("block_users", session_context.role, list(user_ids), reason))
        return {"status": "ok", "updatedUserIds": list(user_ids)}

    def unblock_users(self, session_context, *, user_ids):
        self.calls.append(("unblock_users", session_context.role, list(user_ids)))
        return {"status": "ok", "updatedUserIds": list(user_ids)}

    def delete_user(self, session_context, *, user_id):
        self.calls.append(("delete_user", session_context.role, user_id))
        return {"status": "ok", "userId": user_id}

    def list_matches(self, session_context, **kwargs):
        self.calls.append(("list_matches", session_context.role, kwargs))
        return {"items": [{"id": "match-1"}], "filters": {}, "counts": {"total": 1}}

    def get_match_detail(self, session_context, *, match_id):
        self.calls.append(("get_match_detail", session_context.role, match_id))
        return {"match": {"id": match_id}}

    def analytics_overview(self, session_context):
        self.calls.append(("analytics_overview", session_context.role))
        return {"users": {"total": 1}}

    def preview_message(self, session_context, *, user_ids, message_text):
        self.calls.append(("preview_message", session_context.role, list(user_ids), message_text))
        return {"message": {"text": message_text}, "deliverable": [], "skipped": [], "counts": {"selected": len(user_ids)}}

    def send_message(self, session_context, *, user_ids, message_text):
        self.calls.append(("send_message", session_context.role, list(user_ids), message_text))
        return {"status": "ok", "notificationIds": ["notif-1"], "counts": {"selected": len(user_ids)}, "skipped": []}


def _admin_settings():
    return SimpleNamespace(
        effective_admin_panel_pin="6088",
        effective_admin_session_secret="test-admin-secret",
        admin_session_ttl_seconds=3600,
        is_dev=True,
    )


def test_admin_index_route_serves_html() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/admin")

    assert response.status_code == 200
    assert "<title>Helly Admin</title>" in response.text


def test_admin_pin_auth_accepts_valid_pin_and_rejects_invalid(monkeypatch) -> None:
    settings = _admin_settings()
    monkeypatch.setattr(admin_auth_module, "get_settings", lambda: settings)
    monkeypatch.setattr(admin_router_module, "get_settings", lambda: settings)
    app = create_app()
    client = TestClient(app)

    invalid_response = client.post("/admin/api/auth/pin", json={"pin": "1234"})
    valid_response = client.post("/admin/api/auth/pin", json={"pin": "6088"})

    assert invalid_response.status_code == 401
    assert invalid_response.json()["detail"] == "Invalid admin PIN."
    assert valid_response.status_code == 200
    assert valid_response.json()["authenticated"] is True
    assert "helly_admin_session=" in valid_response.headers.get("set-cookie", "")


def test_admin_api_routes_use_service_and_session_override() -> None:
    app = create_app()
    fake_service = FakeAdminService()
    app.dependency_overrides[admin_router_module._service] = lambda: fake_service
    app.dependency_overrides[admin_router_module._admin_session_context] = lambda: AdminSessionContext(
        role="admin",
        issued_at=1,
        expires_at=9999999999,
    )
    client = TestClient(app)

    session_response = client.get("/admin/api/session")
    users_response = client.get("/admin/api/users", params={"role": "candidate", "status": "active"})
    user_detail_response = client.get("/admin/api/users/user-1")
    block_response = client.post("/admin/api/users/block", json={"userIds": ["user-1"], "reason": "spam"})
    unblock_response = client.post("/admin/api/users/unblock", json={"userIds": ["user-1"]})
    delete_response = client.delete("/admin/api/users/user-1")
    matches_response = client.get("/admin/api/matches", params={"status": "approved"})
    match_detail_response = client.get("/admin/api/matches/match-1")
    analytics_response = client.get("/admin/api/analytics/overview")
    preview_response = client.post("/admin/api/messages/preview", json={"userIds": ["user-1"], "text": "Hello"})
    send_response = client.post("/admin/api/messages/send", json={"userIds": ["user-1"], "text": "Hello"})
    logout_response = client.post("/admin/api/auth/logout")

    assert session_response.status_code == 200
    assert users_response.status_code == 200
    assert users_response.json()["items"][0]["id"] == "user-1"
    assert user_detail_response.status_code == 200
    assert user_detail_response.json()["user"]["id"] == "user-1"
    assert block_response.status_code == 200
    assert block_response.json()["updatedUserIds"] == ["user-1"]
    assert unblock_response.status_code == 200
    assert delete_response.status_code == 200
    assert matches_response.status_code == 200
    assert matches_response.json()["items"][0]["id"] == "match-1"
    assert match_detail_response.status_code == 200
    assert match_detail_response.json()["match"]["id"] == "match-1"
    assert analytics_response.status_code == 200
    assert analytics_response.json()["users"]["total"] == 1
    assert preview_response.status_code == 200
    assert preview_response.json()["message"]["text"] == "Hello"
    assert send_response.status_code == 200
    assert send_response.json()["notificationIds"] == ["notif-1"]
    assert logout_response.status_code == 200

    call_names = [entry[0] for entry in fake_service.calls]
    assert call_names == [
        "session",
        "list_users",
        "get_user_detail",
        "block_users",
        "unblock_users",
        "delete_user",
        "list_matches",
        "get_match_detail",
        "analytics_overview",
        "preview_message",
        "send_message",
    ]
