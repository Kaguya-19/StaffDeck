"""The normal Harness gateway consumes the fixed, authenticated PD model Port."""
import json
from dataclasses import dataclass
from types import SimpleNamespace

import httpx
import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from app.public_api import pilotdeck_domain_host as domain
from app.public_api.pilotdeck_domain_binding import FixedPilotDeckDomainHostClient
from app.public_api.pilotdeck_harness_model import (
    PilotDeckHarnessModel, generate_harness_json, select_harness_model,
)
from staffdeck_harness.bridge.capability_mcp import ActivationRegistry
from staffdeck_harness.bridge.model_gateway import CHAT_COMPLETIONS_PATH, ModelGateway


def test_fixed_identity_selects_live_pd_catalog_and_streams_harness_tools():
    seen = []
    def handle(request):
        assert request.url.path == "/api/module-host/call"
        assert request.headers["authorization"] == "Bearer bridge"
        call = json.loads(request.content)
        assert call["principal"] == {"pilotDeckUserId": "pd-user", "tenantId": "tenant",
                                      "actorUserId": "actor", "agentId": "target"}
        seen.append(call)
        if call["operation"] == "list_model_catalog":
            return httpx.Response(200, json={"data": [{"id": "logical-model", "provider": "provider-1",
                                                       "model": "logical-model", "enabled": True,
                                                       "is_default": True}]})
        assert call["operation"] == "model_stream"
        wire = call["input"]["request"]
        assert wire["provider"] == "provider-1" and wire["model"] == "logical-model"
        assert wire["tools"][0]["name"] == "mcp__staffdeck__knowledge_search"
        assert wire["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
        events = [{"type": "tool_call_start", "id": "call-1", "name": "mcp__staffdeck__knowledge_search"},
                  {"type": "tool_call_delta", "id": "call-1", "delta": '{"query":"fact"}'},
                  {"type": "tool_call_end", "toolCall": {"id": "call-1", "name": "mcp__staffdeck__knowledge_search", "input": {"query": "fact"}}},
                  {"type": "message_end", "finishReason": "tool_call"}]
        return httpx.Response(200, headers={"content-type": "application/x-ndjson"},
                              text="\n".join(json.dumps(e) for e in events) + "\n")

    bound = FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user",
        httpx.MockTransport(handle), "tenant", "actor", "target")
    previous = domain._bound_client
    domain.bind_pilotdeck_domain_host(bound)
    try:
        ctx = SimpleNamespace(tenant_id="tenant", user_id="actor", staff_id="target")
        with pytest.raises(RuntimeError, match="IDENTITY_MISMATCH"):
            select_harness_model(SimpleNamespace(tenant_id="tenant", user_id="other", staff_id="target"))
        assert not seen
        selection = select_harness_model(ctx)
        registry = ActivationRegistry()
        host = SimpleNamespace(model_config=selection, trace=lambda *_: None,
                               model_tool_names=lambda: {"knowledge_search"})
        activation = registry.register(host)
        app = Starlette()
        ModelGateway(registry, client_factory=lambda _: pytest.fail("SD LLM client used")).mount(app)
        with TestClient(app) as client:
            with client.stream("POST", CHAT_COMPLETIONS_PATH,
                               headers={"authorization": f"Bearer {activation.token}"},
                               json={"messages": [{"role": "user", "content": "hi"}], "stream": True,
                                     "tools": [{"type": "function", "function": {
                                         "name": "mcp__staffdeck__knowledge_search", "parameters": {"type": "object"}}},
                                               {"type": "function", "function": {
                                         "name": "mcp__staffdeck__forbidden", "parameters": {}}}]}) as response:
                assert response.status_code == 200
                rows = [line for line in response.iter_lines() if line.startswith("data: ")]
        assert rows[-1] == "data: [DONE]"
        chunks = [json.loads(line[6:]) for line in rows[:-1]]
        assert chunks[0]["choices"][0]["delta"]["tool_calls"][0]["function"]["name"] == "mcp__staffdeck__knowledge_search"
        assert chunks[-1]["choices"][0]["finish_reason"] == "tool_calls"
        assert [call["operation"] for call in seen] == ["list_model_catalog", "model_stream"]
    finally:
        domain._bound_client = previous


def test_pd_model_port_failure_does_not_read_sd_model():
    bound = FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user",
        httpx.MockTransport(lambda _: httpx.Response(503)), "tenant", "actor", "target")
    previous = domain._bound_client
    domain.bind_pilotdeck_domain_host(bound)
    try:
        with pytest.raises(RuntimeError, match="PUBLIC_HOST_LIST_MODEL_CATALOG_FAILED: 503"):
            select_harness_model(SimpleNamespace(tenant_id="tenant", user_id="actor", staff_id="target"))
    finally:
        domain._bound_client = previous


def test_pd_harness_knowledge_route_keeps_model_and_bounds_local_timeout():
    from staffdeck_harness.capabilities.local_services import _knowledge_route_deps

    @dataclass
    class Deps:
        model_config: object
        remaining_seconds: object = None

    selection = PilotDeckHarnessModel("logical", "provider", "logical",
        FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user",
            None, "tenant", "actor", "target"), {})
    host = SimpleNamespace(execution_engine="harness_v3", _deps=lambda: Deps(selection))
    routed = _knowledge_route_deps(host).model_config
    assert isinstance(routed, PilotDeckHarnessModel)
    assert routed.id == selection.id and routed.principal == selection.principal
    assert routed.timeout_seconds is not None and routed.timeout_seconds > 0


def test_background_json_uses_same_authenticated_pd_port():
    seen = []
    def handle(request):
        call = json.loads(request.content)
        seen.append(call)
        assert request.headers["authorization"] == "Bearer bridge"
        assert call["operation"] == "model_stream"
        assert call["principal"]["actorUserId"] == "actor"
        assert call["input"]["request"]["provider"] == "provider"
        return httpx.Response(200, headers={"content-type": "application/x-ndjson"},
            text='{"type":"text_delta","text":"{\\"updates\\":[]}"}\n'
                 '{"type":"message_end","finishReason":"stop"}\n')
    bound = FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user",
        httpx.MockTransport(handle), "tenant", "actor", "target")
    selection = PilotDeckHarnessModel("logical", "provider", "logical", bound,
        {"pilotDeckUserId": "pd-user", "tenantId": "tenant", "actorUserId": "actor", "agentId": "target"},
        timeout_seconds=3.0)
    assert generate_harness_json(selection, "Return JSON", {"fact": "x"}) == {"updates": []}
    assert len(seen) == 1
    assert "timeout_seconds" not in json.dumps(seen[0]["input"])


def test_knowledge_json_uses_pd_selection_without_sd_client(monkeypatch):
    from app.knowledge import service
    selection = PilotDeckHarnessModel("logical", "provider", "logical",
        FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user",
            None, "tenant", "actor", "target"), {})
    monkeypatch.setattr(service, "LLMClient", lambda *_: pytest.fail("SD model client used"))
    monkeypatch.setattr("app.public_api.pilotdeck_harness_model.generate_harness_json",
                        lambda model, prompt, payload: {"selected_document_ids": ["doc"]})
    assert service._generate_knowledge_json(selection, "route", {"query": "fact"}) == {"selected_document_ids": ["doc"]}
