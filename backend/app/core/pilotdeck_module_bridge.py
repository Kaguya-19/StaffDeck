from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.core.harness_capability_invoker import HarnessCapabilityInvoker
from app.llm import LLMClient


class StaffDeckPilotDeckModuleBridge:
    """Expose StaffDeck-owned modules to the PilotDeck sidecar."""

    def __init__(
        self,
        *,
        model_client: LLMClient,
        capability_invoker: HarnessCapabilityInvoker,
        permission_checker: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None,
        checkpoint_sink: Callable[[dict[str, Any]], Mapping[str, Any] | None] | None = None,
    ) -> None:
        self.model_client = model_client
        self.capability_invoker = capability_invoker
        self.permission_checker = permission_checker
        self.checkpoint_sink = checkpoint_sink

    def __call__(self, module: str, payload: dict[str, Any]) -> Mapping[str, Any]:
        if module == "model":
            return self.model(payload)
        if module == "capability":
            return self.capability(payload)
        if module == "permission":
            return self.permission(payload)
        if module == "checkpoint":
            return self.checkpoint(payload)
        raise ValueError(f"Unknown PilotDeck module: {module}")

    def model(self, payload: dict[str, Any]) -> Mapping[str, Any]:
        """Return buffered canonical text events for one model invocation.

        The existing StaffDeck client exposes provider-normalized text chunks;
        keeping the bridge buffered preserves that API while the sidecar owns
        turn/tool-loop semantics. Native tool deltas can be added to the events
        list later without changing the module envelope.
        """

        request = payload.get("request")
        if isinstance(request, dict):
            system_prompt = str(request.get("systemPrompt") or "")
            user_payload: dict[str, Any] | str = {
                "messages": request.get("messages") or [],
                "tools": request.get("tools") or [],
                "tool_choice": request.get("toolChoice"),
                "metadata": request.get("metadata") or {},
            }
        else:
            system_prompt = str(payload.get("systemPrompt") or "")
            user_payload = payload.get("userPayload")
            if not isinstance(user_payload, (dict, str)):
                user_payload = str(user_payload or "")
        try:
            action = self.model_client.generate_json(system_prompt, user_payload)
        except Exception:
            action = None
        events: list[dict[str, Any]] = [{"type": "message_start", "role": "assistant"}]
        if isinstance(action, dict) and action.get("action") == "tool" and str(action.get("tool_name") or "").strip():
            call_id = str(action.get("tool_call_id") or "staffdeck-call")
            events.extend([
                {"type": "tool_call_end", "toolCall": {"id": call_id, "name": str(action["tool_name"]), "input": action.get("arguments") or {}}},
                {"type": "message_end", "finishReason": "tool_call"},
            ])
        else:
            raw_text = (
                (action or {}).get("reply_fragment") or (action or {}).get("reply")
                if isinstance(action, dict)
                else ""
            )
            text = str(raw_text or "")
            if not text:
                text = "".join(self.model_client.generate_text_stream(system_prompt, user_payload))
            if text:
                events.append({"type": "text_delta", "text": text})
            events.append({"type": "message_end", "finishReason": "stop"})
        return {
            "events": events,
        }

    def capability(self, payload: dict[str, Any]) -> Mapping[str, Any]:
        name = str(payload.get("name") or "").strip()
        tool_call_id = str(payload.get("toolCallId") or "staffdeck-call")
        arguments = payload.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        result = self.capability_invoker.invoke(name, arguments)
        if isinstance(result, dict) and result.get("type") in {"success", "error"}:
            return result
        if isinstance(result, dict) and result.get("success") is True:
            return {
                "type": "success",
                "toolCallId": tool_call_id,
                "toolName": name,
                "data": result.get("data"),
                "content": [{"type": "json", "value": result.get("data", result)}],
                "startedAt": "1970-01-01T00:00:00.000Z",
                "completedAt": "1970-01-01T00:00:00.000Z",
            }
        error = result.get("error") if isinstance(result, dict) else None
        return {
            "type": "error",
            "toolCallId": tool_call_id,
            "toolName": name,
            "error": {
                "code": str((error or {}).get("code") if isinstance(error, dict) else "tool_execution_failed"),
                "message": str((error or {}).get("message") if isinstance(error, dict) else "Capability invocation failed."),
            },
            "content": [{"type": "text", "text": str((error or {}).get("message") if isinstance(error, dict) else "Capability invocation failed.")}],
            "startedAt": "1970-01-01T00:00:00.000Z",
            "completedAt": "1970-01-01T00:00:00.000Z",
        }

    def permission(self, payload: dict[str, Any]) -> Mapping[str, Any]:
        if self.permission_checker is None:
            return {"allowed": True, "source": "harness_capability_invoker"}
        return dict(self.permission_checker(payload))

    def checkpoint(self, payload: dict[str, Any]) -> Mapping[str, Any]:
        if self.checkpoint_sink is None:
            return {"accepted": True}
        result = self.checkpoint_sink(payload)
        return dict(result or {"accepted": True})


__all__ = ["StaffDeckPilotDeckModuleBridge"]
