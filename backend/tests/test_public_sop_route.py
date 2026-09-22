from types import SimpleNamespace

from app.db.models import Skill
from app.public_api import sops
from app.public_api.schemas import SOPRouteRequest
from app.session.session_schema import PlannedTaskFrame, TurnPlan


def _skill(skill_id: str, scope: str = "general") -> Skill:
    return Skill(
        id=f"skill-{skill_id}",
        tenant_id="tenant-1",
        skill_id=skill_id,
        name=skill_id,
        description=f"{skill_id} description",
        content_json={"trigger_intents": [skill_id], "capability_scope": scope, "nodes": [{"node_id": "start"}]},
        status="published",
    )


def test_public_sop_route_uses_visible_discoverable_skills_and_native_router(monkeypatch):
    visible = [_skill("purchase"), _skill("price_compare"), _skill("internal", "sop_specific")]
    monkeypatch.setattr(sops, "enforce_agent_access", lambda *args, **kwargs: None)
    monkeypatch.setattr(sops, "ensure_public_agent", lambda *args, **kwargs: None)
    monkeypatch.setattr(sops, "visible_published_skills", lambda *args, **kwargs: visible)
    monkeypatch.setattr(sops, "model_for_agent", lambda *args, **kwargs: object())

    captured = {}

    def fake_plan(self, message, session, available_skills, model_config, conversation_context=None, memory_context=None, task_frame_state=None, interaction_mode="normal", team_context=None):
        captured["skills"] = [skill.skill_id for skill in available_skills]
        return TurnPlan(
            decision="start_new_task",
            confidence=0.9,
            user_intent=message,
            task_frames=[PlannedTaskFrame(
                kind="sop",
                decision="start_new_task",
                target_skill_id="purchase",
                target_step_id="start",
            )],
        )

    monkeypatch.setattr(sops.TurnPlanner, "plan", fake_plan)
    principal = SimpleNamespace(tenant_id="tenant-1", actor_user=SimpleNamespace(id="user-1"))
    result = sops.route_sop(
        "agent-1",
        SOPRouteRequest(message="buy an item"),
        principal,
        SimpleNamespace(commit=lambda: None),
    )

    assert result["selected_sop_id"] == "purchase"
    assert result["candidate_sop_ids"] == ["purchase", "price_compare"]
    assert captured["skills"] == ["purchase", "price_compare"]
