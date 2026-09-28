"""Explicit SD domain callback binding to the selected PD host runtime.

The account service credential stays server-side. The public API's original
credential/KB PEP runs before this callback; this module owns no job or model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class PilotDeckDomainHostClient:
    origin: str
    bridge_token: str
    pilotdeck_user_id: str
    transport: httpx.BaseTransport | None = None

    def file_parse(
        self, *, tenant_id: str, actor_user_id: str, agent_id: str,
        filename: str, content_base64: str, media_type: str | None,
    ) -> dict[str, Any]:
        if not all((self.origin, self.bridge_token, self.pilotdeck_user_id,
                    tenant_id, actor_user_id, agent_id, filename)):
            raise RuntimeError("PUBLIC_HOST_IDENTITY_UNBOUND")
        with httpx.Client(base_url=self.origin, transport=self.transport,
                          timeout=60, follow_redirects=False) as client:
            response = client.post(
                "/api/module-host/call",
                headers={"Authorization": f"Bearer {self.bridge_token}"},
                json={
                    "principal": {
                        "pilotDeckUserId": self.pilotdeck_user_id,
                        "tenantId": tenant_id,
                        "actorUserId": actor_user_id,
                        "agentId": agent_id,
                    },
                    "operation": "file_parse",
                    "input": {"filename": filename, "content_base64": content_base64,
                              "media_type": media_type, "max_bytes": 20 * 1024 * 1024},
                },
            )
        if not response.is_success:
            try:
                error = response.json()
            except ValueError:
                error = response.text
            raise RuntimeError(f"PUBLIC_HOST_FILE_PARSE_FAILED: {response.status_code} {error}")
        value = response.json()
        if not isinstance(value, dict) or not isinstance(value.get("text"), str) \
                or not isinstance(value.get("metadata"), dict) \
                or not isinstance(value["metadata"].get("fileType"), str):
            raise RuntimeError("PUBLIC_HOST_FILE_PARSE_INVALID_RESPONSE")
        return value


_bound_client: PilotDeckDomainHostClient | None = None


def bind_pilotdeck_domain_host(client: PilotDeckDomainHostClient) -> None:
    """Called once by the SD deployment composition root for the enabled profile."""
    if not isinstance(client, PilotDeckDomainHostClient):
        raise TypeError("PilotDeckDomainHostClient is required")
    global _bound_client
    _bound_client = client


def require_pilotdeck_domain_host() -> PilotDeckDomainHostClient:
    if _bound_client is None:
        raise RuntimeError("PUBLIC_HOST_FILE_PORT_UNBOUND")
    return _bound_client
