import asyncio
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from app.public_api import staffdeck_facade as facade


def test_auto_upload_uses_one_native_owner_operation_and_original_job(monkeypatch):
    checks = []
    monkeypatch.setattr(facade, "enforce_public_knowledge_pep", lambda db, principal, agent_id, **kwargs:
                        checks.append((agent_id, kwargs)))
    monkeypatch.setattr(facade, "_payload", lambda value: value)
    def upload(request, agent_id, db, user, *, host_origin):
        assert (request.tenant_id, request.knowledge_base_id, agent_id) == ("tenant", None, "target")
        assert request.capability_scope == "sop_specific"
        assert request.filename == "unique.md" and request.title == "Unique"
        assert "_pilotdeck_host" not in request.metadata
        assert host_origin == {
            "credential_id": "credential", "agent_id": "target", "actor_user_id": "actor",
        }
        assert request.metadata["content_type"] == "text/markdown"
        assert user.id == "actor"
        return {"id": "native-ingest-job", "status": "queued", "knowledge_base_id": "new-private-base"}
    monkeypatch.setattr(facade.native_knowledge, "upload_document_for_public_host", upload)
    principal = SimpleNamespace(tenant_id="tenant", credential_id="credential",
                                actor_user=SimpleNamespace(id="actor"))
    file = UploadFile(file=BytesIO(b"unique fact"), filename="unique.md",
                      headers={"content-type": "text/markdown"})
    result = asyncio.run(facade.upload_knowledge_document_auto_facade(
        "target", file, "Unique", "sop_specific", principal, object()))
    assert result == {"id": "native-ingest-job", "status": "queued", "knowledge_base_id": "new-private-base"}
    assert checks == [("target", {"write": True})]


def test_auto_upload_requires_deferred_credential_before_native_write(monkeypatch):
    monkeypatch.setattr(facade, "enforce_public_knowledge_pep", lambda *args, **kwargs: None)
    monkeypatch.setattr(facade.native_knowledge, "upload_document", lambda *args: pytest.fail("no write"))
    principal = SimpleNamespace(tenant_id="tenant", credential_id=None,
                                actor_user=SimpleNamespace(id="actor"))
    with pytest.raises(Exception, match="Deferred import requires"):
        asyncio.run(facade.upload_knowledge_document_auto_facade(
            "target", UploadFile(file=BytesIO(b"x"), filename="x.md"),
            None, "general", principal, object()))


def test_native_owner_keeps_internal_host_marker_out_of_source_metadata(monkeypatch):
    from app.api import knowledge as native
    from app.knowledge.schema import KnowledgeDocumentUploadRequest
    monkeypatch.setattr(native, "ensure_tenant", lambda *args: None)
    seen = {}
    def resolve(db, request, agent_id, user, creator_metadata):
        seen["source"] = creator_metadata
        return SimpleNamespace(id="new-private-base")
    monkeypatch.setattr(native, "_resolve_upload_knowledge_base", resolve)
    monkeypatch.setattr(native, "knowledge_version_for_upload", lambda *args, **kwargs: SimpleNamespace(id="version"))
    monkeypatch.setattr(native, "enqueue_async_job", lambda *args, **kwargs: None)
    monkeypatch.setattr(native, "job_read", lambda job: job)
    class Service:
        def __init__(self, db): pass
        def create_ingest_job(self, payload):
            seen["payload"] = payload
            return SimpleNamespace(id="native-job")
        def run_ingest_job(self, job_id): pass
    monkeypatch.setattr(native, "KnowledgeService", Service)
    request = KnowledgeDocumentUploadRequest(
        tenant_id="tenant", filename="source.md", content_base64="YQ==",
        metadata={"content_type": "text/markdown",
                  "_pilotdeck_host": {"credential_id": "credential", "agent_id": "target", "actor_user_id": "actor"}},
    )
    db = SimpleNamespace(commit=lambda: None)
    user = SimpleNamespace(id="actor", username="actor", display_name="Actor")
    assert native.upload_document(request, "target", db, user).id == "native-job"
    assert "_pilotdeck_host" not in seen["source"]
    assert seen["payload"].metadata == seen["source"]
    assert seen["payload"].host_origin is None
    origin = {"credential_id": "credential", "agent_id": "target", "actor_user_id": "actor"}
    native.upload_document_for_public_host(request, "target", db, user, host_origin=origin)
    assert seen["payload"].host_origin == origin
    assert "_pilotdeck_host" not in seen["source"]
