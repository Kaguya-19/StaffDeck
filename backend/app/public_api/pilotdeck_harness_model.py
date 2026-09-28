"""Non-persistent model selection for an authorized Harness turn.

The enabled deployment binds one fixed PD identity. No SD ModelConfig or
provider credential is created here; every selection comes from the live PD
catalog and every completion uses its authenticated public model Port.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4
import json

import httpx

from app.public_api.pilotdeck_domain_host import require_pilotdeck_domain_host
from app.public_api.pilotdeck_domain_binding import FixedPilotDeckDomainHostClient


@dataclass(frozen=True)
class PilotDeckHarnessModel:
    id: str
    provider: str
    model: str
    host: FixedPilotDeckDomainHostClient
    principal: dict[str, str]
    # Internal turn deadline hint. It is never part of the PD model selection
    # or canonical request; Knowledge routing may derive a shorter local wait.
    timeout_seconds: float | None = None


def select_harness_model(context: Any, model_id: str | None = None) -> PilotDeckHarnessModel:
    host = require_pilotdeck_domain_host()
    if not isinstance(host, FixedPilotDeckDomainHostClient) or (
        context.tenant_id, context.user_id, context.staff_id
    ) != (host.tenant_id, host.actor_user_id, host.agent_id):
        raise RuntimeError("PUBLIC_HOST_FIXED_IDENTITY_MISMATCH")
    principal = {"pilotDeckUserId": host.pilotdeck_user_id,
                 "tenantId": host.tenant_id, "actorUserId": host.actor_user_id,
                 "agentId": host.agent_id}
    with httpx.Client(base_url=host.origin, transport=host.transport,
                      timeout=60, follow_redirects=False) as client:
        catalog = host._call(client, principal=principal,
                             operation="list_model_catalog", input={}).json()
    items = catalog.get("data") if isinstance(catalog, dict) else None
    if not isinstance(items, list):
        raise RuntimeError("PUBLIC_HOST_MODEL_CATALOG_INVALID")
    default = catalog.get("defaultSelection")
    if model_id:
        selected = [item for item in items if isinstance(item, dict) and item.get("id") == model_id]
    elif isinstance(default, dict):
        selected = [item for item in items if isinstance(item, dict)
                    and item.get("provider") == default.get("provider")
                    and item.get("model") == default.get("model")]
    else:
        selected = [item for item in items if isinstance(item, dict) and item.get("is_default") is True]
    if len(selected) != 1:
        raise RuntimeError("PUBLIC_HOST_MODEL_SELECTION_UNBOUND")
    item = selected[0]
    provider, model = item.get("provider"), item.get("model")
    if not isinstance(provider, str) or not provider or not isinstance(model, str) or not model \
            or item.get("id") not in (model, f"{provider}/{model}") \
            or item.get("available", item.get("enabled")) is not True:
        raise RuntimeError("PUBLIC_HOST_MODEL_SELECTION_INVALID")
    return PilotDeckHarnessModel(str(item["id"]), provider, model, host, principal)


def stream_model_events(selection: PilotDeckHarnessModel, request: dict[str, Any]):
    """Yield validated canonical events from the existing authenticated Port."""
    with httpx.Client(base_url=selection.host.origin, transport=selection.host.transport,
                      timeout=selection.timeout_seconds, follow_redirects=False) as client:
        with client.stream("POST", "/api/module-host/call",
                           headers={"Authorization": f"Bearer {selection.host.bridge_token}"},
                           json={"principal": selection.principal, "operation": "model_stream",
                                 "input": {"requestId": f"harness-{uuid4().hex}",
                                           "modelId": selection.id, "request": request}}) as response:
            if not response.is_success:
                raise RuntimeError(f"PUBLIC_HOST_MODEL_STREAM_FAILED: {response.status_code}")
            if not response.headers.get("content-type", "").startswith("application/x-ndjson"):
                raise RuntimeError("PUBLIC_HOST_MODEL_STREAM_INVALID")
            for line in response.iter_lines():
                if line.strip():
                    try:
                        event = json.loads(line)
                    except ValueError as exc:
                        raise RuntimeError("PUBLIC_HOST_MODEL_STREAM_INVALID") from exc
                    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                        raise RuntimeError("PUBLIC_HOST_MODEL_STREAM_INVALID")
                    yield event


def generate_harness_json(selection: PilotDeckHarnessModel, system_prompt: str,
                          user_payload: dict[str, Any]) -> Any:
    """Use the original JSON repair policy with the same authenticated PD Port."""
    from app.llm.client import (LLMClient, _prepare_user_input, _request_messages,
                                _with_json_mode_instruction)
    from staffdeck_harness.bridge.pilotdeck_model_wire import canonical_request

    class PublicJsonClient(LLMClient):
        def __init__(self):
            pass

        def generate_text(self, prompt, payload, cancellation=None, **kwargs):
            return self._generate_json_candidate(prompt, payload, False, cancellation)

        def _generate_json_candidate(self, prompt, payload, json_mode_supported, cancellation=None):
            if cancellation is not None and getattr(cancellation, "cancelled", False):
                raise RuntimeError("PUBLIC_HOST_MODEL_CANCELLED")
            context, serialized = _prepare_user_input(payload)
            messages = _with_json_mode_instruction(_request_messages(prompt, context, serialized))
            if not messages or messages[0].get("role") != "system":
                raise RuntimeError("PUBLIC_HOST_MODEL_PROMPT_INVALID")
            canonical = canonical_request({"messages": messages, "stream": True}, selection)
            fragments = []
            ended = False
            for event in stream_model_events(selection, canonical):
                if event["type"] == "text_delta" and isinstance(event.get("text"), str):
                    fragments.append(event["text"])
                elif event["type"] == "message_end":
                    if event.get("finishReason") != "stop":
                        raise RuntimeError("PUBLIC_HOST_MODEL_INCOMPLETE")
                    ended = True
                elif event["type"] == "error":
                    raise RuntimeError("PUBLIC_HOST_MODEL_FAILED")
            if not ended or not fragments:
                raise RuntimeError("PUBLIC_HOST_MODEL_INCOMPLETE")
            return "".join(fragments)

    return PublicJsonClient().generate_json(system_prompt, user_payload)
