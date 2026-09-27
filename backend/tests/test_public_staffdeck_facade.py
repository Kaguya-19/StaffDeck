from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from app.db import get_session
from app.db.models import AgentProfile, Tenant, User
from app.public_api.app import create_public_api_app
from app.public_api.auth import PublicPrincipal, get_public_principal
from app.public_api.credential_profiles import AGENT_RUNTIME_SCOPES, USER_FULL_ACCESS_SCOPES
from app.public_api import staffdeck_facade as facade
from app.public_api import knowledge_pep
from app.public_api.errors import PublicAPIError


CARD = {
    "skill_id": "sop_test",
    "name": "Test SOP",
    "version": "1.0.0",
    "nodes": [{"node_id": "start", "type": "respond", "name": "Start", "instruction": "Answer"}],
    "edges": [],
    "start_node_id": "start",
    "terminal_node_ids": ["start"],
}


class PublicStaffDeckFacadeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.actor = SimpleNamespace(id="actor", tenant_id="tenant", role="admin")
        self.principal = PublicPrincipal("tenant", self.actor, frozenset(USER_FULL_ACCESS_SCOPES))
        self.db = object()

    def test_only_account_profile_gains_sop_cancel(self) -> None:
        self.assertIn("sops:cancel", USER_FULL_ACCESS_SCOPES)
        self.assertNotIn("sops:cancel", AGENT_RUNTIME_SCOPES)
        self.assertNotIn("jobs:cancel", USER_FULL_ACCESS_SCOPES)
        self.assertNotIn("*", USER_FULL_ACCESS_SCOPES)

    def test_fixed_public_routes_are_registered(self) -> None:
        paths = create_public_api_app().openapi()["paths"]
        expected = {
            "/agents/{agent_id}/sops:preview-generate": "post",
            "/agents/{agent_id}/sops/{sop_id}:preview-rewrite": "post",
            "/agents/{agent_id}/sop-preview-jobs/{job_id}/events": "get",
            "/agents/{agent_id}/sops/{sop_id}:move-to-draft": "post",
            "/agents/{agent_id}/sops/{sop_id}": "delete",
            "/agents/{agent_id}/sops/{sop_id}:sync-from-overall": "post",
            "/agents/{agent_id}/sops/{sop_id}:promote-to-overall": "post",
            "/agents/{agent_id}/sops/{sop_id}/versions/{version}": "delete",
            "/agents/{agent_id}/tools:probe": "post",
            "/agents/{agent_id}/tools/{tool_id}": "delete",
            "/agents/{agent_id}/sops:extract-file": "post",
        }
        for path, method in expected.items():
            self.assertIn(method, paths[path], path)

    def test_dirty_rewrite_passes_current_skill_and_conversation_without_save(self) -> None:
        body = facade.PreviewRewrite.model_validate({
            "current_skill": CARD,
            "instruction": "Rewrite this unsaved graph",
            "target_path": "nodes[0]",
            "conversation": [{"role": "user", "content": "Keep my edit"}],
        })
        with patch.object(facade, "_agent"), patch.object(
            facade.native_skills, "create_rewrite_job", return_value={"job_id": "preview"}
        ) as create, patch.object(facade.native_skills, "create_skill") as save:
            result = facade.preview_rewrite("agent", "sop_test", body, self.principal, self.db)
        self.assertEqual(result, {"job_id": "preview"})
        request = create.call_args.args[1]
        self.assertEqual(request.tenant_id, "tenant")
        self.assertEqual(request.agent_id, "agent")
        self.assertEqual(request.current_skill.skill_id, "sop_test")
        self.assertEqual(request.conversation[0]["content"], "Keep my edit")
        save.assert_not_called()

    def test_preview_schema_rejects_identity_override(self) -> None:
        with self.assertRaises(Exception):
            facade.PreviewRewrite.model_validate({
                "tenant_id": "other", "current_skill": CARD, "instruction": "change"
            })

    def test_preview_job_path_cannot_switch_agent(self) -> None:
        facade._register_preview_job("bound-preview", "agent-a")
        with patch.object(facade, "_agent"), patch.object(
            facade.native_skills, "_owned_stream_job"
        ) as native_owner:
            with self.assertRaises(PublicAPIError) as raised:
                facade._preview_job(self.principal, "agent-b", "bound-preview", self.db)
        self.assertEqual(raised.exception.code, "JOB_NOT_FOUND")
        native_owner.assert_not_called()

    def test_http_preview_preserves_dirty_input_and_enforces_scope(self) -> None:
        app = create_public_api_app()
        app.dependency_overrides[get_session] = lambda: self.db
        app.dependency_overrides[get_public_principal] = lambda: self.principal
        with TestClient(app) as client, patch.object(facade, "_agent"), patch.object(
            facade.native_skills, "create_rewrite_job", return_value={"job_id": "transient"}
        ) as create:
            response = client.post(
                "/agents/agent/sops/sop_test:preview-rewrite",
                json={"current_skill": CARD, "instruction": "rewrite unsaved text",
                      "conversation": [{"role": "user", "content": "dirty"}]},
            )
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json(), {"job_id": "transient"})
        self.assertEqual(create.call_args.args[1].current_skill.skill_id, "sop_test")

        app.dependency_overrides[get_public_principal] = lambda: PublicPrincipal(
            "tenant", self.actor, frozenset({"sops:read"})
        )
        with TestClient(app) as client:
            denied = client.post(
                "/agents/agent/sops/sop_test:preview-rewrite",
                json={"current_skill": CARD, "instruction": "rewrite"},
            )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["code"], "INSUFFICIENT_SCOPE")

    def test_original_remove_operation_receives_principal_actor_and_target(self) -> None:
        with patch.object(facade, "_agent") as check, patch.object(
            facade.native_skills, "delete_skill", return_value={"status": "hidden"}
        ) as remove:
            result = facade.remove_sop("agent", "sop_test", self.principal, self.db)
        self.assertEqual(result, {"status": "hidden"})
        check.assert_called_once_with(self.db, self.principal, "agent", write=True)
        remove.assert_called_once_with("sop_test", "tenant", self.db, "agent", self.actor)

    def test_knowledge_pep_replays_native_view_dependency_and_rejects_wrong_document(self) -> None:
        db = SimpleNamespace(get=lambda _model, _id: SimpleNamespace(
            tenant_id="tenant", knowledge_base_id="other-base"
        ))
        with patch.object(knowledge_pep, "enforce_agent_access"), patch.object(
            knowledge_pep, "ensure_public_agent"
        ), patch.object(knowledge_pep, "require_agent_scope_viewer") as viewer, patch.object(
            knowledge_pep.native_bases, "get_knowledge_base"
        ) as base:
            with self.assertRaises(PublicAPIError) as raised:
                knowledge_pep.enforce_public_knowledge_pep(
                    db, self.principal, "agent", knowledge_base_id="base", document_id="document"
                )
        self.assertEqual(raised.exception.code, "DOCUMENT_NOT_FOUND")
        viewer.assert_called_once_with("tenant", "agent", self.actor, db)
        base.assert_called_once_with("base", "tenant", "agent", db)

    def test_knowledge_body_cannot_override_path_or_principal_scope(self) -> None:
        with self.assertRaises(PublicAPIError) as raised:
            knowledge_pep.reject_public_scope_override(
                {"knowledge_base_id": "other"}, "tenant_id", "knowledge_base_id"
            )
        self.assertEqual(raised.exception.code, "PUBLIC_SCOPE_OVERRIDE")

    def test_public_knowledge_list_rejects_member_without_native_view_permission(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(Tenant(id="tenant", name="Tenant"))
            db.add(User(id="owner", tenant_id="tenant", username="owner", role="member", password_hash="x"))
            db.add(User(id="visitor", tenant_id="tenant", username="visitor", role="member", password_hash="x"))
            db.add(AgentProfile(id="agent", tenant_id="tenant", name="Employee", status="active",
                                is_overall=False, metadata_json={"owner_user_id": "owner"}))
            db.commit()
            visitor = db.get(User, "visitor")
            owner = db.get(User, "owner")
        app = create_public_api_app()
        def session_override():
            with Session(engine) as db:
                yield db
        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_public_principal] = lambda: PublicPrincipal(
            "tenant", visitor, frozenset({"knowledge:read"}), allowed_agent_ids=frozenset({"agent"})
        )
        with TestClient(app) as client:
            denied = client.get("/agents/agent/knowledge-bases")
        self.assertEqual(denied.status_code, 403, denied.text)
        app.dependency_overrides[get_public_principal] = lambda: PublicPrincipal(
            "tenant", owner, frozenset({"knowledge:read"}), allowed_agent_ids=frozenset({"agent"})
        )
        with TestClient(app) as client:
            allowed = client.get("/agents/agent/knowledge-bases")
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual(allowed.json()["data"], [])


if __name__ == "__main__":
    unittest.main()
