import base64
from types import SimpleNamespace

import httpx
import pytest

from app.knowledge.service import extract_ingest_text
from app.public_api import pilotdeck_domain_host as host


def test_public_ingest_uses_bound_pd_file_port_and_original_domain_job():
    calls = []
    def handle(request):
        calls.append(request)
        assert request.url.path == "/api/module-host/call"
        assert request.headers["authorization"] == "Bearer service"
        body = __import__("json").loads(request.content)
        assert body["operation"] == "file_parse"
        assert body["principal"] == {
            "pilotDeckUserId": "pd-user", "tenantId": "tenant",
            "actorUserId": "actor", "agentId": "target",
        }
        assert body["input"]["content_base64"] == base64.b64encode(b"unique fact").decode()
        return httpx.Response(200, json={"text": "unique fact", "metadata": {"fileType": "md"}})
    client = host.PilotDeckDomainHostClient("http://pd", "service", "pd-user", httpx.MockTransport(handle))
    old = host._bound_client
    try:
        host.bind_pilotdeck_domain_host(client)
        job = SimpleNamespace(tenant_id="tenant", filename="unique.md")
        metadata = {"content_base64": base64.b64encode(b"unique fact").decode(),
                    "metadata": {"_pilotdeck_host": {"agent_id": "target", "actor_user_id": "actor"},
                                 "content_type": "text/markdown", "created_by_user_id": "actor"}}
        assert extract_ingest_text(job, metadata, b"unique fact") == ("unique fact", "md")
        assert len(calls) == 1
    finally:
        host._bound_client = old


def test_public_ingest_without_binding_fails_instead_of_native_parse():
    old = host._bound_client
    try:
        host._bound_client = None
        job = SimpleNamespace(tenant_id="tenant", filename="fact.md")
        metadata = {"content_base64": base64.b64encode(b"fact").decode(),
                    "metadata": {"_pilotdeck_host": {"agent_id": "target", "actor_user_id": "actor"},
                                 "created_by_user_id": "actor"}}
        with pytest.raises(RuntimeError, match="PUBLIC_HOST_FILE_PORT_UNBOUND"):
            extract_ingest_text(job, metadata, b"fact")
        assert extract_ingest_text(job, {"metadata": {}}, b"fact") == ("fact", "md")
    finally:
        host._bound_client = old


def test_public_ingest_rejects_missing_identity_and_host_failure():
    job = SimpleNamespace(tenant_id="tenant", filename="fact.md")
    with pytest.raises(RuntimeError, match="PUBLIC_HOST_INGEST_IDENTITY_INVALID"):
        extract_ingest_text(job, {"metadata": {"_pilotdeck_host": {"agent_id": "target"}}}, b"fact")
    client = host.PilotDeckDomainHostClient("http://pd", "service", "pd-user",
        httpx.MockTransport(lambda request: httpx.Response(415, json={"code": "PUBLIC_FILE_TYPE_UNSUPPORTED"})))
    with pytest.raises(RuntimeError, match="PUBLIC_HOST_FILE_PARSE_FAILED: 415"):
        client.file_parse(tenant_id="tenant", actor_user_id="actor", agent_id="target",
                          filename="fact.pdf", content_base64="aGVsbG8=", media_type="application/pdf")
