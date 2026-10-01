from copy import deepcopy
from types import SimpleNamespace as NS

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.agents.branching import ensure_private_resource_binding, mark_resource_private_for_agent
from app.db import get_session
from app.db.models import Tenant, User, AgentProfile, Skill, KnowledgeBase, KnowledgeBaseVersion, AgentKnowledgeBranch, AgentResourceBinding
from app.public_api import pilotdeck_domain_host, pilotdeck_knowledge_read as read
from app.public_api.auth import PublicPrincipal, get_public_principal
from app.public_api.errors import PublicAPIError, public_api_error_handler
from app.public_api.sop_capability_authority import resolve_authority
from staffdeck_harness.contracts.manifest import SlotName
from staffdeck_harness.modules.registry import ModuleRegistry, discover_and_install


CONTEXT = {"sessionKey": "pd-session", "projectKey": "/own/project", "expectedRevision": 2, "requestId": "authority-1"}
CONTENT = {"skill_id": "sop", "version": "1", "name": "SOP", "start_node_id": "response",
           "terminal_node_ids": ["response"], "edges": [], "nodes": [
               {"node_id": "response", "type": "response", "name": "Answer", "allowed_actions": ["answer_user"],
                "capability_refs": {"knowledge_base_ids": ["kb"]}},
               {"node_id": "sibling", "type": "response", "name": "Other"}]}


@pytest.fixture
def authority(tmp_path, monkeypatch):
    settings = NS(security_profile="OSS_LOCAL", harness_modules="", harness_disabled_modules="",
                  harness_v3_enabled=False, harness_v3_root="", harness_v3_home="")
    registry = discover_and_install(ModuleRegistry(), settings)
    for slot in SlotName:
        registry.mark_guarded(slot)
    registry.seal()
    monkeypatch.setattr("staffdeck_harness.modules.registry._active", registry)
    engine = create_engine(f"sqlite:///{tmp_path / 'authority.sqlite'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        actor = User(id="actor", tenant_id="t", username="actor", role="member", password_hash="unused")
        db.add_all([Tenant(id="t", name="Tenant"), actor,
                    AgentProfile(id="agent", tenant_id="t", name="Agent", metadata_json={"owner_user_id": "actor"}),
                    Skill(id="sop-row", tenant_id="t", skill_id="sop", version="1", name="SOP",
                          content_json=CONTENT, status="published"),
                    AgentResourceBinding(id="sop-binding", tenant_id="t", agent_id="agent", resource_type="skill",
                                         resource_id="sop-row", metadata_json={"scope": "agent_private"})])
        kb = KnowledgeBase(id="kb", tenant_id="t", name="KB", capability_scope="sop_specific")
        mark_resource_private_for_agent(kb, "agent")
        db.add(kb)
        db.flush()
        ensure_private_resource_binding(db, "t", "agent", "knowledge_base", "kb")
        db.add_all([KnowledgeBaseVersion(id="version", tenant_id="t", knowledge_base_id="kb", version="1", name="KB", capability_scope="sop_specific"),
                    AgentKnowledgeBranch(id="branch", tenant_id="t", agent_id="agent", knowledge_base_id="kb", source_knowledge_base_id="kb", head_version="1")])
        db.commit()
        principal = PublicPrincipal("t", actor, frozenset({"knowledge:read"}), credential_id="credential")
        pinned = {**CONTEXT, "admission": {"tenantId": "t", "actorUserId": "actor", "agentId": "agent",
                  "credentialId": "credential", "pilotDeckUserId": "owner"}, "sopId": "sop", "sopVersion": "1",
                  "nodeId": "response", "content": deepcopy(CONTENT)}
        def callback(request):
            body = __import__("json").loads(request.content)
            assert body["operation"] == "read_sop_authority"
            assert body["input"] == {**CONTEXT, "admissionCredentialId": "credential"}
            return httpx.Response(200, json=pinned)
        client = pilotdeck_domain_host.PilotDeckDomainHostClient("http://owner", "synthetic-bridge", "owner", httpx.MockTransport(callback))
        monkeypatch.setattr(pilotdeck_domain_host, "_bound_client", client)
        yield NS(db=db, principal=principal, pinned=pinned, registry=registry, engine=engine)
    engine.dispose()


def test_configured_sources_catalog_pep_optional_and_restart_readback(authority):
    result = resolve_authority(authority.db, authority.principal, "agent", CONTEXT)
    assert len(result["optionalCapabilities"]) == 1
    item = result["optionalCapabilities"][0]
    assert (item["operation"], item["resourceId"], item["required"], item["providerModuleId"], item["selectionMode"]) == (
        "knowledge.search/v1", "kb", False, "knowledge.local", "current")
    assert "provider_config" not in str(result) and "synthetic-bridge" not in str(result)
    authority.db.commit()
    with Session(authority.engine) as restarted:
        assert resolve_authority(restarted, authority.principal, "agent", CONTEXT) == result


@pytest.mark.parametrize("field,value,code", [
    ("sopVersion", "old", "SOP_AUTHORITY_PIN_MISMATCH"),
    ("content", {}, "SOP_AUTHORITY_PIN_MISMATCH"),
    ("nodeId", "unknown", "SOP_AUTHORITY_NODE_MISMATCH"),
    ("expectedRevision", 1, "SOP_AUTHORITY_ADMISSION_MISMATCH"),
])
def test_wrong_pin_node_or_revision_denied(authority, field, value, code):
    authority.pinned[field] = value
    with pytest.raises(PublicAPIError) as error:
        resolve_authority(authority.db, authority.principal, "agent", CONTEXT)
    assert error.value.code == code


@pytest.mark.parametrize("field", ["tenantId", "actorUserId", "agentId", "credentialId", "pilotDeckUserId"])
def test_foreign_or_unadmitted_identity_denied(authority, field):
    authority.pinned["admission"][field] = "other"
    with pytest.raises(PublicAPIError, match="Owner admission"):
        resolve_authority(authority.db, authority.principal, "agent", CONTEXT)


def test_sibling_empty_and_live_revocation(authority):
    authority.pinned["nodeId"] = "sibling"
    assert resolve_authority(authority.db, authority.principal, "agent", CONTEXT)["optionalCapabilities"] == []
    authority.pinned["nodeId"] = "response"
    binding = authority.db.exec(select(AgentResourceBinding).where(AgentResourceBinding.resource_id == "kb")).one()
    binding.status = "disabled"
    authority.db.add(binding)
    authority.db.commit()
    result = resolve_authority(authority.db, authority.principal, "agent", CONTEXT)
    assert result["optionalCapabilities"] == []


@pytest.mark.parametrize("extra", [{"grant": "kb"}, {"expectedRevision": True}, {"projectKey": ""}])
def test_strict_context(authority, extra):
    with pytest.raises(PublicAPIError) as error:
        resolve_authority(authority.db, authority.principal, "agent", {**CONTEXT, **extra})
    assert error.value.code == "SOP_AUTHORITY_INPUT_INVALID"


def test_authority_manifest_protocol_and_public_credential_guards(authority):
    app = FastAPI()
    app.add_exception_handler(PublicAPIError, public_api_error_handler)
    app.include_router(read.router)
    app.dependency_overrides[get_session] = lambda: authority.db
    body = {"kind": "request", "method": "module_call", "messageId": "m", "runId": "r", "operationId": "o",
            "requestId": "q", "module": "capability", "payload": {"operation": "resolve", "input": CONTEXT}}
    with TestClient(app) as client:
        manifest = client.get("/sop-capability-authority/module-manifest").json()
        assert manifest["contract"] == "staffdeck.sop-capability-authority/v1"
        assert manifest["methods"] == ["resolve"]
        path = "/agents/agent/sop-capability-authority/v2/module/call"
        assert client.post(path, json=body).status_code == 401
        app.dependency_overrides[get_public_principal] = lambda: authority.principal
        response = client.post(path, json=body)
        assert response.status_code == 200
        assert response.json()["inReplyTo"] == "m" and response.json()["requestId"] == "q"
        assert response.json()["payload"]["result"]["optionalCapabilities"][0]["resourceId"] == "kb"
        app.dependency_overrides[get_public_principal] = lambda: PublicPrincipal("t", authority.principal.actor_user, frozenset())
        assert client.post(path, json=body).status_code == 403
        app.dependency_overrides[get_public_principal] = lambda: authority.principal
        body["payload"]["grant"] = "kb"
        assert client.post(path, json=body).status_code == 400


@pytest.mark.parametrize("selectors,expected", [
    ({}, True), ({"knowledgeBaseIds": [], "knowledgeBaseVersionIds": []}, True),
    ({"knowledgeBaseIds": ["kb", "foreign"], "knowledgeBaseVersionIds": ["version", "foreign"]}, True),
    ({"knowledgeBaseIds": ["foreign"]}, False), ({"knowledgeBaseVersionIds": ["foreign"]}, False),
    ({"knowledge_base_ids": ["kb"]}, False), ({"scope": {"all": True}}, False), ({"maxChunks": True}, False),
    ({"knowledgeBaseIds": [1]}, False), ({"documentIds": "id"}, False),
])
def test_bound_query_execution_selectors_and_no_denied_search(authority, monkeypatch, selectors, expected):
    searches = []
    monkeypatch.setattr(read.native_knowledge, "search_knowledge", lambda query, db, user:
        searches.append(query) or NS(model_dump=lambda **kw: {"chunks": [{"id": "chunk"}]}))
    app = FastAPI()
    app.add_exception_handler(PublicAPIError, public_api_error_handler)
    app.include_router(read.router)
    app.dependency_overrides[get_session] = lambda: authority.db
    app.dependency_overrides[get_public_principal] = lambda: authority.principal
    projected = resolve_authority(authority.db, authority.principal, "agent", CONTEXT)
    execution_context = {**CONTEXT, "snapshotId": projected["snapshotId"], "registryGeneration": projected["registryGeneration"]}
    body = {"kind": "request", "method": "module_call", "messageId": "m", "runId": "r", "operationId": "o",
            "requestId": "q", "module": "knowledge", "payload": {"operation": "query", "input": {"query": "fact", **selectors}, "authorityContext": execution_context}}
    with TestClient(app) as client:
        response = client.post("/agents/agent/knowledge-module/v2/module/call", json=body)
    assert response.status_code == 200 if expected else response.status_code in {400, 403, 422}
    assert len(searches) == int(expected)
    if expected:
        assert searches[0].knowledge_base_ids == ["kb"]
        assert searches[0].knowledge_base_version_ids == ["version"]


@pytest.mark.parametrize("pin", [{"provider_module_id": "missing.provider"}, {"module_version": "99.0.0"}])
def test_unavailable_provider_or_version_never_projects(authority, pin):
    binding = authority.db.get(AgentResourceBinding, "sop-binding")
    binding.metadata_json = {**binding.metadata_json, "slot_bindings": {"kb:kb": {"resource_id": "kb", **pin}}}
    authority.db.add(binding)
    authority.db.commit()
    try:
        result = resolve_authority(authority.db, authority.principal, "agent", CONTEXT)
        assert result["optionalCapabilities"] == []
    except PublicAPIError as error:
        assert error.status_code in {403, 409}


@pytest.mark.parametrize("mutation", ["snapshot", "generation", "revoke", "missing"])
def test_execution_projection_change_or_revoke_has_no_search_side_effect(authority, monkeypatch, mutation):
    import json
    result = resolve_authority(authority.db, authority.principal, "agent", CONTEXT)
    context = {**CONTEXT, "snapshotId": result["snapshotId"], "registryGeneration": result["registryGeneration"]}
    if mutation == "snapshot":
        context["snapshotId"] = "stale"
    elif mutation == "generation":
        context["registryGeneration"] += 1
    elif mutation == "missing":
        del context["snapshotId"]
    else:
        binding = authority.db.exec(select(AgentResourceBinding).where(AgentResourceBinding.resource_id == "kb")).one()
        binding.status = "disabled"
        authority.db.add(binding)
        authority.db.commit()
    monkeypatch.setattr(read.native_knowledge, "search_knowledge", lambda *args: pytest.fail("denied execution must not retrieve"))
    body = {"kind": "request", "method": "module_call", "messageId": "m", "runId": "r", "operationId": "o",
            "requestId": "q", "module": "knowledge", "payload": {"operation": "query", "input": {"query": "fact"}, "authorityContext": context}}
    response = read.read_module_call("agent", body, authority.principal, authority.db)
    assert response.status_code in {403, 409, 422}
    payload = json.loads(response.body)
    assert payload["ok"] is False
    if mutation in {"snapshot", "generation"}:
        assert response.status_code == 409 and payload["code"] == "SOP_AUTHORITY_STALE"


def test_configured_replacement_sources_do_not_read_resource_orm(authority, monkeypatch):
    from dataclasses import replace
    from staffdeck_harness.composition.slots import sop_slots
    from staffdeck_harness.contracts.manifest import ModuleKind
    from staffdeck_harness.contracts.security import ResourceRef, SecurityContext
    from staffdeck_harness.contracts.sources import ResourceDescriptor
    from staffdeck_harness.contracts.staff import StaffComposition, SessionPolicy, SopView, CapabilityBindingView
    from staffdeck_harness.modules.registry import manifest
    from staffdeck_harness.security.oss_local import build_oss_local_profile

    content = deepcopy(CONTENT)
    ref = ResourceRef("agent", "agent", "t", {"owner_user_id": "actor"})
    bound = {"binding_status": "active", "private_to_agent": True}
    sop = SopView("sop", "remote-row", "1", "SOP", content, None, {}, tuple(sop_slots(content)), ResourceRef("sop", "sop", "t", bound))
    cap = CapabilityBindingView("knowledge_base", "kb", "remote-binding", ResourceRef("knowledge_base", "kb", "t", bound), "Remote KB", "sop_specific")
    staff = StaffComposition("t", "agent", "Remote", False, "active", None, {}, SessionPolicy(), (cap,), (), (), None, (), ref)
    sources = {
        SlotName.IDENTITY_SOURCE: NS(resolve=lambda context, identity: SecurityContext("actor", "t")),
        SlotName.STAFF_SOURCE: NS(reference=lambda context: ref, resolve=lambda context: staff, model=lambda *args: None),
        SlotName.SOP_SOURCE: NS(resolve=lambda context, staff: (sop,), reference=lambda context, id: sop.ref),
        SlotName.RESOURCE_CATALOG: NS(resolve=lambda context, type, id, op: ResourceDescriptor(ResourceRef(type, id, "t", bound), "KB", op)),
    }
    registry = ModuleRegistry()
    for slot, source in sources.items():
        registry.install(manifest(f"test.{slot.name.lower()}", "Replacement", kind=ModuleKind.TRUSTED, slots=[slot]),
                         NS(build=lambda db, source=source: source), slot=slot)
    registry.install(manifest("knowledge.local", "Installed Knowledge", kind=ModuleKind.CODE,
        slots=[SlotName.STAFF_CAPABILITY], provides=["knowledge.search/v1"]), NS(), slot=SlotName.STAFF_CAPABILITY)
    registry.security_profile = build_oss_local_profile()
    monkeypatch.setattr("staffdeck_harness.modules.registry._active", registry)
    monkeypatch.setattr(authority.db, "get", lambda *args: pytest.fail("authority must use configured Sources, not resource ORM"))
    result = resolve_authority(authority.db, authority.principal, "agent", CONTEXT)
    assert [item["resourceId"] for item in result["optionalCapabilities"]] == ["kb"]
    # Unsupported installed providers remain unavailable even with a legal catalog/PEP result.
    registry = ModuleRegistry()
    for slot, source in sources.items():
        registry.install(manifest(f"test.{slot.name.lower()}", "Replacement", kind=ModuleKind.TRUSTED, slots=[slot]),
                         NS(build=lambda db, source=source: source), slot=slot)
    registry.install(manifest("knowledge.remote", "Remote", kind=ModuleKind.CODE,
        slots=[SlotName.STAFF_CAPABILITY], provides=["knowledge.search/v1"]), NS(), slot=SlotName.STAFF_CAPABILITY)
    registry.security_profile = build_oss_local_profile()
    monkeypatch.setattr("staffdeck_harness.modules.registry._active", registry)
    result = resolve_authority(authority.db, authority.principal, "agent", CONTEXT)
    assert result["optionalCapabilities"] == []
    assert result["unavailable"][0]["reason"] == "SOP_AUTHORITY_PORT_UNMAPPED"
