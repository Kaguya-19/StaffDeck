import json
from types import SimpleNamespace

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.db.models import (
    KnowledgeBase, KnowledgeDiscoverySuggestion, KnowledgeDocument, KnowledgeIngestJob, Tool,
)
from app.knowledge.service import KnowledgeService
from app.public_api import auth, pilotdeck_domain_host as binding, sessions
from app.public_api.pilotdeck_domain_binding import FixedPilotDeckDomainHostClient
from app.security import permissions


@pytest.fixture
def discovery(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'discovery.sqlite'}")
    SQLModel.metadata.create_all(engine)
    db = Session(engine)
    document = KnowledgeDocument(tenant_id="tenant", knowledge_base_id="kb",
                                 filename="tool.md", file_type="md", title="Tool API")
    job = KnowledgeIngestJob(tenant_id="tenant", knowledge_base_id="kb",
                            document_id=document.id, filename="tool.md",
                            status="running", stage="discovering", metadata_json={
        "_pilotdeck_host": {"credential_id": "credential", "agent_id": "target",
                            "actor_user_id": "actor"},
        "metadata": {"created_by_user_id": "actor"},
    })
    db.add(KnowledgeBase(id="kb", tenant_id="tenant", name="Private base"))
    db.add(document)
    db.add(job)
    db.commit()
    checks, calls = [], []
    principal = SimpleNamespace(tenant_id="tenant", actor_user=SimpleNamespace(id="actor"),
                                can=lambda scope: scope == "knowledge:write")
    monkeypatch.setattr(auth, "principal_for_credential", lambda db, credential:
                        principal if credential == "credential" else pytest.fail("wrong credential"))
    monkeypatch.setattr(auth, "enforce_agent_access", lambda p, agent, write:
                        checks.append(("access", agent, write)))
    monkeypatch.setattr(sessions, "ensure_public_agent", lambda *args: None)
    monkeypatch.setattr(permissions, "ensure_agent_scope_manager", lambda db, tenant, agent, actor:
                        checks.append(("manager", tenant, agent, actor.id)))
    monkeypatch.setattr(KnowledgeService, "_default_model_config",
                        lambda *args: pytest.fail("no SD default model fallback"))

    def handle(request):
        body = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer bridge"
        assert body["principal"] == {"pilotDeckUserId": "pd-user", "tenantId": "tenant",
                                     "actorUserId": "actor", "agentId": "target"}
        calls.append((request.url.path, body))
        if request.url.path == "/api/module-host/describe":
            return httpx.Response(200, json={"operations": [
                "list_model_catalog", "model_prepare", "model_stream"]})
        if body["operation"] == "list_model_catalog":
            return httpx.Response(200, json={
                "defaultSelection": {"mode": "model", "provider": "pd", "model": "selected"},
                "data": [{"id": "pd/selected", "provider": "pd", "model": "selected",
                          "available": True, "is_default": True}],
            })
        payload = body["input"]
        assert payload["modelId"] == "pd/selected"
        assert payload["request"]["provider"] == "pd"
        assert payload["request"]["model"] == "selected"
        if body["operation"] == "model_prepare":
            return httpx.Response(200, json={"requestId": payload["requestId"],
                "selection": {"requestedModelId": "pd/selected", "selectedModelId": "selected",
                              "providerId": "pd"}, "request": payload["request"]})
        assert body["operation"] == "model_stream"
        result = {"discoveries": [{"suggestion_type": "tool", "title": f"Tool {i}",
            "payload": {"name": f"discovery.{i}", "url": f"https://example.test/tool/{i}"},
            "source_refs": [{"document_id": document.id}]} for i in range(2)]}
        return httpx.Response(200, headers={"content-type": "application/x-ndjson",
            "x-pilotdeck-model-id": "selected", "x-pilotdeck-provider-id": "pd"}, text=
            json.dumps({"type": "text_delta", "text": json.dumps(result)}) + "\n" +
            json.dumps({"type": "message_end", "finishReason": "stop"}) + "\n")

    host = FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user",
        httpx.MockTransport(handle), "tenant", "actor", "target")
    monkeypatch.setattr(binding, "_bound_client", host)
    service = KnowledgeService(db)
    service._public_host_ingest = True
    yield SimpleNamespace(db=db, engine=engine, document=document, job=job, service=service,
                          calls=calls, checks=checks, principal=principal, host=host)
    db.close()
    engine.dispose()


def run_discovery(fixture):
    fixture.service._discover_from_document("tenant", "kb", fixture.document, [], fixture.job)


def test_public_discovery_uses_fixed_pd_port_and_persists_review_states(discovery):
    run_discovery(discovery)
    assert [body.get("operation", "describe") for _, body in discovery.calls] == [
        "describe", "list_model_catalog", "model_prepare", "model_stream"]
    assert discovery.checks == [("access", "target", True),
                                ("manager", "tenant", "target", "actor")]
    document_id = discovery.document.id
    discovery.db.close()
    with Session(discovery.engine) as db:
        rows = db.exec(select(KnowledgeDiscoverySuggestion)).all()
        assert len(rows) == 2 and all(row.status == "pending" for row in rows)
        assert all(row.source_refs_json == [{"document_id": document_id}] for row in rows)
        service = KnowledgeService(db)
        service.confirm_discovery(rows[0])
        service.reject_discovery(rows[1])
    with Session(discovery.engine) as db:
        assert sorted(row.status for row in db.exec(select(KnowledgeDiscoverySuggestion)).all()) == [
            "confirmed", "rejected"]
        assert len(db.exec(select(Tool)).all()) == 1


@pytest.mark.parametrize("field,value", [("agent_id", "other"), ("actor_user_id", "other")])
def test_public_discovery_rejects_different_host_scope(discovery, field, value):
    metadata = dict(discovery.job.metadata_json)
    metadata["_pilotdeck_host"] = {**metadata["_pilotdeck_host"], field: value}
    discovery.job.metadata_json = metadata
    with pytest.raises(RuntimeError, match="PUBLIC_HOST_(FIXED_IDENTITY_MISMATCH|INGEST_IDENTITY_INVALID)"):
        run_discovery(discovery)
    assert discovery.calls == []
    assert discovery.db.exec(select(KnowledgeDiscoverySuggestion)).all() == []


def test_public_discovery_rechecks_write_permission_before_model(discovery):
    discovery.principal.can = lambda scope: False
    with pytest.raises(RuntimeError, match="PUBLIC_HOST_INGEST_IDENTITY_INVALID"):
        run_discovery(discovery)
    assert discovery.calls == []


def test_public_discovery_without_bound_port_never_falls_back(discovery, monkeypatch):
    monkeypatch.setattr(binding, "_bound_client", None)
    with pytest.raises(RuntimeError, match="PUBLIC_HOST_FILE_PORT_UNBOUND"):
        run_discovery(discovery)
    assert discovery.calls == []
