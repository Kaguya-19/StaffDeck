import json
from types import SimpleNamespace

import httpx
import pytest

from app.public_api.pilotdeck_domain_host import PilotDeckDomainHostClient
from app.session.session_schema import TurnPlan


def test_pd_host_route_uses_catalog_and_model_stream_with_bound_principal(monkeypatch):
    calls = []
    def handle(request):
        assert request.url.path == "/api/module-host/call"
        assert request.headers["authorization"] == "Bearer bridge"
        body = json.loads(request.content)
        assert body["principal"] == {"pilotDeckUserId": "pd-user", "tenantId": "tenant",
                                     "actorUserId": "actor", "agentId": "target"}
        calls.append(body)
        if body["operation"] == "list_model_catalog":
            return httpx.Response(200, json={"defaultSelection": {"mode": "model", "provider": "provider", "model": "model"},
                "data": [{"id": "provider/model", "provider": "provider", "model": "model", "available": True}]})
        assert body["operation"] == "model_stream"
        assert body["input"]["modelId"] == "provider/model"
        assert body["input"]["request"]["provider"] == "provider"
        return httpx.Response(200, headers={"content-type": "application/x-ndjson"},
            text='{"type":"text_delta","text":"{\\"decision\\":\\"answer_only\\"}"}\n'
                 '{"type":"message_end","finishReason":"stop"}\n')
    client = PilotDeckDomainHostClient("http://pd", "bridge", "pd-user", httpx.MockTransport(handle))
    from app.core.turn_planner import TurnPlanner
    monkeypatch.setattr(TurnPlanner, "prepare_payload", lambda *args, **kwargs: {"message": "buy"})
    monkeypatch.setattr(TurnPlanner, "normalize_plan", lambda self, plan, *args: plan)
    session = SimpleNamespace(active_skill_id=None)
    plan = client.plan_sop_route(tenant_id="tenant", actor_user_id="actor", agent_id="target",
        message="buy", session=session, routing_skills=[], conversation_context=None)
    assert isinstance(plan, TurnPlan) and plan.decision == "answer_only"
    assert [call["operation"] for call in calls] == ["list_model_catalog", "model_stream"]


def test_pd_host_route_rejects_missing_selection_without_model_request(monkeypatch):
    calls = []
    def handle(request):
        calls.append(json.loads(request.content)["operation"])
        return httpx.Response(200, json={"data": []})
    client = PilotDeckDomainHostClient("http://pd", "bridge", "pd-user", httpx.MockTransport(handle))
    from app.core.turn_planner import TurnPlanner
    monkeypatch.setattr(TurnPlanner, "prepare_payload", lambda *args, **kwargs: {})
    with pytest.raises(RuntimeError, match="PUBLIC_HOST_MODEL_SELECTION_UNBOUND"):
        client.plan_sop_route(tenant_id="tenant", actor_user_id="actor", agent_id="target",
            message="buy", session=SimpleNamespace(), routing_skills=[], conversation_context=None)
    assert calls == ["list_model_catalog"]


def test_runtime_binding_uses_existing_gateway_token_file(tmp_path):
    from app.public_api import pilotdeck_domain_host as host
    token_path = tmp_path / "server-token"
    token_path.write_text("existing-token\n", encoding="utf-8")
    old = host._bound_client
    try:
        host.bind_pilotdeck_domain_host_from_runtime(
            gateway_url="ws://127.0.0.1:16411/ws", token_path=str(token_path), pilotdeck_user_id="pd-user")
        bound = host.require_pilotdeck_domain_host()
        assert (bound.origin, bound.bridge_token, bound.pilotdeck_user_id) == (
            "http://127.0.0.1:16411", "existing-token", "pd-user")
        with pytest.raises(RuntimeError, match="PUBLIC_HOST_RUNTIME_BINDING_INVALID"):
            host.bind_pilotdeck_domain_host_from_runtime(
                gateway_url="http://user:pass@other.test", token_path=str(token_path), pilotdeck_user_id="pd-user")
    finally:
        host._bound_client = old
