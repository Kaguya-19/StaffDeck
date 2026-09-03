from __future__ import annotations

import pytest

from app.core.pilotdeck_agent_loop_client import StaffDeckModuleError
from app.core.pilotdeck_module_bridge import StaffDeckPilotDeckModuleBridge


class FakeModel:
    def __init__(self, response):
        self.response = response
        self.requests: list[tuple[str, object]] = []

    def generate_json(self, system_prompt, user_payload):
        self.requests.append((system_prompt, user_payload))
        return self.response

    def generate_text_stream(self, *_args, **_kwargs):
        raise AssertionError("text fallback must not be called")


class FakeInvoker:
    def __init__(self, result):
        self.result = result

    def invoke(self, _name, _arguments):
        return self.result


def test_model_preserves_multimodal_messages_without_text_fallback() -> None:
    model = FakeModel({"reply_fragment": "看到了图片。"})
    bridge = StaffDeckPilotDeckModuleBridge(
        model_client=model,
        capability_invoker=FakeInvoker({"success": True}),
    )

    result = bridge.model(
        {
            "request": {
                "systemPrompt": "system",
                "messages": [
                    {
                        "role": "user",
                        "content": "请描述图片",
                        "images": [
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/png;base64,AAAA"},
                            }
                        ],
                    }
                ],
                "tools": [],
                "toolChoice": "auto",
                "metadata": {"source": "test"},
            }
        }
    )

    assert {"type": "text_delta", "text": "看到了图片。"} in result["events"]
    assert model.requests[0][1]["conversation_context"]["messages"][0]["images"][0]["image_url"]["url"].startswith("data:image/png")


def test_model_error_is_not_downgraded_to_text_generation() -> None:
    model = FakeModel(None)
    bridge = StaffDeckPilotDeckModuleBridge(
        model_client=model,
        capability_invoker=FakeInvoker({"success": True}),
    )

    with pytest.raises(TypeError, match="empty or invalid JSON action"):
        bridge.model({"systemPrompt": "system", "userPayload": "payload"})


def test_permission_fails_closed_without_checker() -> None:
    bridge = StaffDeckPilotDeckModuleBridge(
        model_client=FakeModel({"reply_fragment": "ok"}),
        capability_invoker=FakeInvoker({"success": True}),
    )

    result = bridge.permission({"toolName": "exec_command"})

    assert result["allowed"] is False
    assert result["error"]["code"] == "PERMISSION_UNAVAILABLE"


def test_capability_error_result_keeps_host_error_shape() -> None:
    bridge = StaffDeckPilotDeckModuleBridge(
        model_client=FakeModel({"reply_fragment": "ok"}),
        capability_invoker=FakeInvoker(
            {
                "type": "error",
                "toolCallId": "call-1",
                "toolName": "lookup",
                "error": {"code": "CAPABILITY_AUTHORIZATION_REVOKED", "message": "revoked"},
                "content": [{"type": "text", "text": "revoked"}],
            }
        ),
    )

    result = bridge.capability({"name": "lookup", "toolCallId": "call-1", "arguments": {}})

    assert result["type"] == "error"
    assert result["error"]["code"] == "CAPABILITY_AUTHORIZATION_REVOKED"
    assert result["toolCallId"] == "call-1"


def test_model_budget_gate_rejects_before_extra_model_action() -> None:
    model = FakeModel({"reply_fragment": "ok"})
    bridge = StaffDeckPilotDeckModuleBridge(
        model_client=model,
        capability_invoker=FakeInvoker({"success": True}),
        remaining_actions=1,
    )
    bridge.model({"systemPrompt": "system", "userPayload": "first"})
    with pytest.raises(StaffDeckModuleError, match="action budget exhausted"):
        bridge.model({"systemPrompt": "system", "userPayload": "second"})
    assert len(model.requests) == 1
