from types import SimpleNamespace

import pytest

from app.public_api.pilotdeck_approval_binding import bind_pilotdeck_approval_client


def test_normal_gateway_file_is_used_without_generating_another_credential(tmp_path):
    token_path = tmp_path / "server-token"
    token_path.write_text("normal-gateway-fixture-token\n", encoding="utf-8")
    env = {"PILOTDECK_APPROVAL_BRIDGE_ENABLED": "true", "PILOTDECK_GATEWAY_URL": "ws://127.0.0.1:16411/ws",
           "PILOTDECK_GATEWAY_TOKEN_PATH": str(token_path), "STAFFDECK_COPY_TENANT_ID": "tenant",
           "STAFFDECK_COPY_TARGET_AGENT_ID": "target"}
    app = SimpleNamespace(state=SimpleNamespace())
    bind_pilotdeck_approval_client(app, env)
    binding = app.state.pilotdeck_approval_client
    assert (binding.origin, binding.tenant_id, binding.agent_id) == ("http://127.0.0.1:16411", "tenant", "target")
    assert binding.bridge_token == "normal-gateway-fixture-token"
    assert token_path.read_text(encoding="utf-8") == "normal-gateway-fixture-token\n"
    token_path.unlink()
    with pytest.raises(RuntimeError, match="PD_APPROVAL_GATEWAY_CREDENTIAL_UNAVAILABLE"):
        bind_pilotdeck_approval_client(app, env)
    assert not token_path.exists()


def test_disabled_or_incomplete_deployment_does_not_create_a_binding():
    app = SimpleNamespace(state=SimpleNamespace())
    bind_pilotdeck_approval_client(app, {})
    assert not hasattr(app.state, "pilotdeck_approval_client")
    with pytest.raises(RuntimeError, match="PD_APPROVAL_BRIDGE_CONFIG_REQUIRED"):
        bind_pilotdeck_approval_client(app, {"PILOTDECK_APPROVAL_BRIDGE_ENABLED": "true"})
