import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.public_api.pilotdeck_approvals import ApprovalReply, PilotDeckApprovalClient


def test_bridge_preserves_original_reply_and_separates_service_and_user_identity():
    def handler(request):
        assert request.url.path == "/api/module-host/approvals/resume"
        assert request.headers["authorization"] == "Bearer service"
        assert request.headers["x-staffdeck-approver-authorization"] == "Bearer approver"
        assert b'"waitId":"original"' in request.content
        return httpx.Response(200, json={"accepted": True, "duplicate": True, "revision": 8})

    client = PilotDeckApprovalClient("http://localhost:16411", "service", "tenant", "target", httpx.MockTransport(handler))
    assert client.call("resume", {"waitId": "original"}, "Bearer approver")["duplicate"]


def test_bridge_preserves_owner_denial():
    client = PilotDeckApprovalClient("http://localhost:16411", "service", "tenant", "target",
                                    httpx.MockTransport(lambda request: httpx.Response(403, json={"code": "SOP_APPROVAL_FORBIDDEN"})))
    with pytest.raises(HTTPException) as error:
        client.call("status", {}, "Bearer approver")
    assert error.value.status_code == 403


def test_browser_cannot_supply_subject_or_assignee():
    with pytest.raises(ValidationError):
        ApprovalReply(session_key="s", request_id="r", wait_id="w", expected_revision=1,
                      message="Reviewed", subject={"userId": "admin"})


def test_router_enforces_native_tenant_before_public_bridge():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.db.models import User
    from app.security.auth import get_current_user
    from app.public_api.pilotdeck_approvals import router

    app = FastAPI()
    app.include_router(router)
    app.state.pilotdeck_approval_client = PilotDeckApprovalClient(
        "http://localhost:16411", "service", "tenant", "target",
        httpx.MockTransport(lambda request: pytest.fail("Must not send request for mismatched tenant")),
    )
    app.dependency_overrides[get_current_user] = lambda: User(
        id="approver", tenant_id="other", username="approver", password_hash="unused",
        role="member", source="web", disabled=False,
    )
    with TestClient(app) as client:
        assert client.get("/pilotdeck/approvals/session", headers={"authorization": "Bearer approver"}).status_code == 403
