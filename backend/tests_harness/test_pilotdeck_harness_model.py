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
    PilotDeckHarnessModel, PublicModelPortError, generate_harness_json,
    prepare_model_request, select_harness_model, stream_model_events,
)
from staffdeck_harness.bridge.capability_mcp import ActivationRegistry
from staffdeck_harness.bridge.model_gateway import CHAT_COMPLETIONS_PATH, ModelGateway


def test_fixed_identity_selects_live_pd_catalog_and_streams_harness_tools():
    seen = []
    def handle(request):
        assert request.url.path in {"/api/module-host/describe", "/api/module-host/call"}
        assert request.headers["authorization"] == "Bearer bridge"
        call = json.loads(request.content)
        assert call["principal"] == {"pilotDeckUserId": "pd-user", "tenantId": "tenant",
                                      "actorUserId": "actor", "agentId": "target"}
        if request.url.path.endswith("/describe"):
            return httpx.Response(200, json={"operations": ["list_model_catalog", "model_prepare", "model_stream"]})
        seen.append(call)
        if call["operation"] == "list_model_catalog":
            return httpx.Response(200, json={"data": [{"id": "provider-1/logical-model", "provider": "provider-1",
                                                       "model": "logical-model", "available": True,
                                                       "is_default": True}],
                                            "defaultSelection": {"mode": "model", "provider": "provider-1",
                                                                 "model": "logical-model"}})
        if call["operation"] == "model_prepare":
            input = call["input"]
            assert input["modelId"] == "provider-1/logical-model"
            return httpx.Response(200, json={"requestId": input["requestId"],
                "selection": {"requestedModelId": input["modelId"],
                              "selectedModelId": "logical-model", "providerId": "provider-1"},
                "request": input["request"]})
        assert call["operation"] == "model_stream"
        assert call["input"]["requestId"] == seen[-2]["input"]["requestId"]
        wire = call["input"]["request"]
        assert wire["provider"] == "provider-1" and wire["model"] == "logical-model"
        assert wire["tools"][0]["name"] == "mcp__staffdeck__knowledge_search"
        assert wire["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
        events = [{"type": "tool_call_start", "id": "call-1", "name": "mcp__staffdeck__knowledge_search"},
                  {"type": "tool_call_delta", "id": "call-1", "delta": '{"query":"fact"}'},
                  {"type": "tool_call_end", "toolCall": {"id": "call-1", "name": "mcp__staffdeck__knowledge_search", "input": {"query": "fact"}}},
                  {"type": "message_end", "finishReason": "tool_call"}]
        return httpx.Response(200, headers={"content-type": "application/x-ndjson",
                                            "x-pilotdeck-model-id": "logical-model",
                                            "x-pilotdeck-provider-id": "provider-1"},
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
        assert [call["operation"] for call in seen] == ["list_model_catalog", "model_prepare", "model_stream"]
    finally:
        domain._bound_client = previous


def test_pd_model_port_failure_does_not_read_sd_model():
    def handle(request):
        if request.url.path.endswith("/describe"):
            return httpx.Response(200, json={"operations": ["list_model_catalog", "model_prepare", "model_stream"]})
        return httpx.Response(503)
    bound = FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user",
        httpx.MockTransport(handle), "tenant", "actor", "target")
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
        assert call["operation"] in {"model_prepare", "model_stream"}
        assert call["principal"]["actorUserId"] == "actor"
        assert call["input"]["request"]["provider"] == "provider"
        if call["operation"] == "model_prepare":
            input = call["input"]
            return httpx.Response(200, json={"requestId": input["requestId"],
                "selection": {"requestedModelId": "logical", "selectedModelId": "logical",
                              "providerId": "provider"}, "request": input["request"]})
        return httpx.Response(200, headers={"content-type": "application/x-ndjson",
                                            "x-pilotdeck-model-id": "logical",
                                            "x-pilotdeck-provider-id": "provider"},
            text='{"type":"text_delta","text":"{\\"updates\\":[]}"}\n'
                 '{"type":"message_end","finishReason":"stop"}\n')
    bound = FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user",
        httpx.MockTransport(handle), "tenant", "actor", "target")
    selection = PilotDeckHarnessModel("logical", "provider", "logical", bound,
        {"pilotDeckUserId": "pd-user", "tenantId": "tenant", "actorUserId": "actor", "agentId": "target"},
        timeout_seconds=3.0)
    assert generate_harness_json(selection, "Return JSON", {"fact": "x"}) == {"updates": []}
    assert len(seen) == 2
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


def test_describe_and_catalog_reject_missing_port_ambiguous_or_explicit_sd_model():
    calls = []
    catalog = {"data": [{"id": "provider/logical", "provider": "provider", "model": "logical",
                         "available": True, "is_default": True}],
               "defaultSelection": {"mode": "model", "provider": "provider", "model": "logical"}}
    operations = ["list_model_catalog", "model_prepare", "model_stream"]
    def handle(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/describe"):
            return httpx.Response(200, json={"operations": operations})
        return httpx.Response(200, json=catalog)
    bound = FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user",
        httpx.MockTransport(handle), "tenant", "actor", "target")
    previous = domain._bound_client
    domain.bind_pilotdeck_domain_host(bound)
    context = SimpleNamespace(tenant_id="tenant", user_id="actor", staff_id="target")
    try:
        operations.remove("model_prepare")
        with pytest.raises(RuntimeError, match="REQUIRED_MODEL_PORT_UNAVAILABLE"):
            select_harness_model(context)
        assert calls == ["/api/module-host/describe"]
        operations.append("model_prepare")
        catalog["data"].append({"id": "other/model", "provider": "other", "model": "model",
                                "available": True})
        assert select_harness_model(context).id == "provider/logical"
        catalog["data"].append(dict(catalog["data"][0]))
        with pytest.raises(RuntimeError, match="MODEL_SELECTION_AMBIGUOUS"):
            select_harness_model(context)
        catalog["data"].pop()
        with pytest.raises(RuntimeError, match="EXPLICIT_MODEL_NOT_SELECTED"):
            select_harness_model(context, "sd-model-config-id")
        assert calls.count("/api/module-host/call") == 3
    finally:
        domain._bound_client = previous


def test_prepare_rejection_is_http_400_before_stream_and_cancel_makes_no_call():
    operations = []
    def handle(request):
        call = json.loads(request.content)
        operations.append(call["operation"])
        assert call["operation"] == "model_prepare"
        return httpx.Response(400, json={"code": "invalid_budget", "message": "too large"})
    bound = FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user",
        httpx.MockTransport(handle), "tenant", "actor", "target")
    selection = PilotDeckHarnessModel("provider/logical", "provider", "logical", bound,
        {"pilotDeckUserId": "pd-user", "tenantId": "tenant", "actorUserId": "actor", "agentId": "target"})
    registry = ActivationRegistry()
    activation = registry.register(SimpleNamespace(model_config=selection, trace=lambda *_: None,
                                                   model_tool_names=lambda: set()))
    app = Starlette()
    ModelGateway(registry, client_factory=lambda _: pytest.fail("SD LLM client used")).mount(app)
    with TestClient(app) as client:
        response = client.post(CHAT_COMPLETIONS_PATH,
            headers={"authorization": f"Bearer {activation.token}"},
            json={"messages": [{"role": "user", "content": "hello"}], "stream": True})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_budget"
    assert operations == ["model_prepare"]
    with pytest.raises(PublicModelPortError, match="MODEL_CANCELLED"):
        prepare_model_request(selection, {"provider": "provider", "model": "logical",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]},
            cancelled=lambda: True)
    assert operations == ["model_prepare"]


def test_ndjson_error_and_missing_terminal_are_not_success():
    selection = PilotDeckHarnessModel("provider/logical", "provider", "logical",
        FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user", None,
            "tenant", "actor", "target"), {})
    from staffdeck_harness.bridge.pilotdeck_model_wire import openai_chunks
    with pytest.raises(RuntimeError, match="MODEL_INCOMPLETE"):
        list(openai_chunks([{"type": "text_delta", "text": "partial"}], selection))
    with pytest.raises(RuntimeError, match="MODEL_INCOMPLETE"):
        list(openai_chunks([{"type": "message_end", "finishReason": "length"}], selection))
    def handle(request):
        return httpx.Response(200, headers={"content-type": "application/x-ndjson",
            "x-pilotdeck-model-id": "logical", "x-pilotdeck-provider-id": "provider"},
            text='{"type":"error","error":{"code":"MODEL_UPSTREAM_UNAVAILABLE","status":503}}\n')
    selection = PilotDeckHarnessModel(selection.id, selection.provider, selection.model,
        FixedPilotDeckDomainHostClient("http://pd", "bridge", "pd-user",
            httpx.MockTransport(handle), "tenant", "actor", "target"), {})
    with pytest.raises(PublicModelPortError) as caught:
        list(stream_model_events(selection, {"provider": "provider", "model": "logical",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]},
            prepared_input={"requestId": "same", "modelId": selection.id, "request": {}}))
    assert caught.value.code == "MODEL_UPSTREAM_UNAVAILABLE" and caught.value.status == 503
