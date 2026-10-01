import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.public_api.pilotdeck_approvals import ApprovalReply, PilotDeckApprovalClient
from app.public_api.errors import PublicAPIError, public_api_error_handler


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
    with pytest.raises(PublicAPIError) as error:
        client.call("status", {}, "Bearer approver")
    assert error.value.status_code == 403
    assert error.value.code == "SOP_APPROVAL_FORBIDDEN"


@pytest.mark.parametrize("change", ["message", "expected_revision"])
def test_public_reply_preserves_original_receipt_conflict(change, native_consumer):
    client, db, user, headers, calls = native_consumer
    original = None
    def owner(request):
        nonlocal original
        payload = request.read()
        if original is None:
            original = payload
            return httpx.Response(200, json={"accepted": True, "duplicate": False, "revision": 8})
        if payload == original:
            return httpx.Response(200, json={"accepted": True, "duplicate": True, "revision": 8})
        return httpx.Response(409, json={"code": "SOP_RESUME_REQUEST_CONFLICT"})
    def transport(request):
        calls.append(request)
        return owner(request)
    client.app.state.pilotdeck_approval_client = PilotDeckApprovalClient(
        "http://localhost:16411", "service", "tenant", "target", httpx.MockTransport(transport))
    body = dict(session_key="session", request_id="original-request", wait_id="original",
                expected_revision=7, message="Reviewed")
    first = client.post("/pilotdeck/approvals/reply", headers=headers, json=body)
    assert first.status_code == 200 and first.json()["duplicate"] is False
    changed = {**body, change: "Changed" if change == "message" else 9}
    for _ in range(2):
        response = client.post("/pilotdeck/approvals/reply", headers=headers, json=changed)
        assert response.status_code == 409
        assert response.json()["code"] == "SOP_RESUME_REQUEST_CONFLICT"
        assert response.json()["status"] == 409
    replay = client.post("/pilotdeck/approvals/reply", headers=headers, json=body)
    assert replay.status_code == 200 and replay.json()["duplicate"] is True
    assert len(calls) == 4


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
        role="member", source="web",
    )
    with TestClient(app) as client:
        assert client.get("/pilotdeck/approvals/session", headers={"authorization": "Bearer approver"}).status_code == 403


@pytest.fixture
def native_consumer(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine
    from app.db import get_session
    from app.db.models import User
    from app.security.auth import create_access_token
    from app.public_api.pilotdeck_approvals import router
    from staffdeck_harness.runtime import control_auth

    monkeypatch.setattr(control_auth, "provider", lambda: None)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id="approver", tenant_id="tenant", username="approver",
                    password_hash="unused", role="member", source="web")
        assert user.disabled is False
        db.add(user)
        db.commit()
        token = create_access_token(user)
        calls = []
        def handle(request):
            calls.append(request)
            return httpx.Response(200, json={"accepted": True, "duplicate": True, "revision": 8})
        app = FastAPI()
        app.add_exception_handler(PublicAPIError, public_api_error_handler)
        app.include_router(router)
        app.state.pilotdeck_approval_client = PilotDeckApprovalClient(
            "http://localhost:16411", "service", "tenant", "target", httpx.MockTransport(handle))
        app.dependency_overrides[get_session] = lambda: db
        with TestClient(app) as client:
            yield client, db, user, {"authorization": f"Bearer {token}"}, calls
    engine.dispose()


def test_matching_native_user_uses_real_auth_for_status_and_receipt(native_consumer):
    client, db, user, headers, calls = native_consumer
    assert client.get("/pilotdeck/approvals/session", headers=headers).status_code == 200
    body = dict(session_key="session", request_id="request", wait_id="original",
                expected_revision=7, message="Reviewed")
    response = client.post("/pilotdeck/approvals/reply", headers=headers, json=body)
    assert response.status_code == 200
    assert response.json() == {"accepted": True, "duplicate": True, "revision": 8}
    assert len(calls) == 2
    assert calls[-1].headers["x-staffdeck-approver-authorization"] == headers["authorization"]


@pytest.mark.parametrize("field,value", [("source", "channel"), ("role", "guest"), ("tenant_id", "other"), ("disabled", True)])
def test_native_subject_boundaries(native_consumer, field, value):
    client, db, user, headers, calls = native_consumer
    setattr(user, field, value)
    db.add(user)
    db.commit()
    response = client.get("/pilotdeck/approvals/session", headers=headers)
    assert response.status_code in {401, 403}
    assert calls == []


def test_native_missing_bearer_is_unauthenticated(native_consumer):
    client, db, user, headers, calls = native_consumer
    assert client.get("/pilotdeck/approvals/session").status_code == 401
    assert calls == []


@pytest.mark.parametrize("facts,status", [({"disabled": False}, 200), ({"disabled": True}, 403),
                                           ({}, 503), ({"disabled": False, "role": "admin"}, 403)])
def test_external_directory_disabled_is_authoritative(native_consumer, monkeypatch, facts, status):
    from app.security.auth import get_current_user
    from staffdeck_harness.runtime import control_auth
    client, db, user, headers, calls = native_consumer
    class ExternalControl:
        member_identity_source = "web"
        def resolve_members(self, tenant_id, ids):
            assert (tenant_id, ids) == ("tenant", ["approver"])
            return [dict(id="approver", tenant_id="tenant", username="approver",
                         source="web", role="member") | facts]
    monkeypatch.setattr(control_auth, "provider", lambda: ExternalControl())
    # External authentication already returns this real User projection; only
    # directory facts can authorize its active-account status, not the User.
    client.app.dependency_overrides[get_current_user] = lambda: user
    assert client.get("/pilotdeck/approvals/session", headers=headers).status_code == status
    assert len(calls) == (1 if status == 200 else 0)


def test_external_missing_directory_fails_closed(native_consumer, monkeypatch):
    from app.security.auth import get_current_user
    from staffdeck_harness.runtime import control_auth
    client, db, user, headers, calls = native_consumer
    monkeypatch.setattr(control_auth, "provider", lambda: object())
    client.app.dependency_overrides[get_current_user] = lambda: user
    response = client.get("/pilotdeck/approvals/session", headers=headers)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MEMBER_DIRECTORY_UNAVAILABLE"
    assert calls == []
