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
                      timeout=None, follow_redirects=False) as client:
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
