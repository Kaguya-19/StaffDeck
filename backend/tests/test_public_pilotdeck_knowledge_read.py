from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_session
from app.public_api import pilotdeck_knowledge_read as read
from app.public_api.auth import PublicPrincipal, get_public_principal


def envelope(input):
    return {"kind": "request", "method": "module_call", "messageId": "m", "runId": "r",
            "operationId": "o", "requestId": "request", "module": "knowledge",
            "payload": {"operation": "query", "input": input}}


def test_read_module_binds_authenticated_principal_and_original_pep(monkeypatch):
    actor = SimpleNamespace(id="real-actor", tenant_id="tenant")
    principal = PublicPrincipal(tenant_id="tenant", actor_user=actor, scopes=frozenset({"knowledge:read"}), agent_id="target")
    calls = []
    monkeypatch.setattr(read, "enforce_public_knowledge_pep", lambda db, p, agent:
                        calls.append(("pep", p.actor_user.id, agent)))
    def search(query, db, user):
        from app.knowledge.public_host_selection import public_host_retrieval_selected
        assert public_host_retrieval_selected()
        calls.append(("search", query.tenant_id, query.agent_id, user.id))
        return SimpleNamespace(model_dump=lambda **kwargs: {"chunks": [{"id": "c1"}], "okf_citations": [{"chunk_id": "c1"}]})
    monkeypatch.setattr(read.native_knowledge, "search_knowledge", search)
    app = FastAPI()
    app.include_router(read.router)
    app.dependency_overrides[get_public_principal] = lambda: principal
    app.dependency_overrides[get_session] = lambda: object()
    with TestClient(app) as client:
        assert client.get("/knowledge-module/module-manifest").json()["methods"] == ["query"]
        response = client.post("/agents/target/knowledge-module/v2/module/call", json=envelope({"query": "unique fact"}))
        assert response.status_code == 200
        assert response.json()["payload"]["result"]["okf_citations"] == [{"chunk_id": "c1"}]
        for illegal in ({"query": "x", "actorUserId": "real-actor"},
                        {"query": "x", "tenantId": "tenant"},
                        {"query": "x", "modelConfigId": "sd-model"}):
            denied = client.post("/agents/target/knowledge-module/v2/module/call", json=envelope(illegal))
            assert denied.status_code == 400 and denied.json()["ok"] is False
    assert calls == [("pep", "real-actor", "target"), ("search", "tenant", "target", "real-actor")]


def test_read_module_requires_real_public_credential_and_scope(monkeypatch):
    app = FastAPI()
    from app.public_api.errors import PublicAPIError, public_api_error_handler
    app.add_exception_handler(PublicAPIError, public_api_error_handler)
    app.include_router(read.router)
    app.dependency_overrides[get_session] = lambda: object()
    with TestClient(app) as client:
        assert client.post("/agents/target/knowledge-module/v2/module/call", json=envelope({"query": "x"})).status_code == 401
    principal = PublicPrincipal(tenant_id="tenant", actor_user=SimpleNamespace(id="actor"), scopes=frozenset())
    app.dependency_overrides[get_public_principal] = lambda: principal
    with TestClient(app) as client:
        assert client.post("/agents/target/knowledge-module/v2/module/call", json=envelope({"query": "x"})).status_code == 403


def test_read_module_rejects_wrong_agent_through_original_pep(monkeypatch):
    from app.public_api.errors import PublicAPIError
    principal = PublicPrincipal(tenant_id="tenant", actor_user=SimpleNamespace(id="actor"),
                                scopes=frozenset({"knowledge:read"}), agent_id="target")
    def pep(db, p, agent):
        assert agent == "other"
        raise PublicAPIError(403, "AGENT_SCOPE_MISMATCH", "Wrong target")
    monkeypatch.setattr(read, "enforce_public_knowledge_pep", pep)
    app = FastAPI()
    app.include_router(read.router)
    app.dependency_overrides[get_public_principal] = lambda: principal
    app.dependency_overrides[get_session] = lambda: object()
    with TestClient(app) as client:
        response = client.post("/agents/other/knowledge-module/v2/module/call", json=envelope({"query": "x"}))
        assert response.status_code == 403 and response.json()["code"] == "AGENT_SCOPE_MISMATCH"
