from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.core.harness_capability_invoker import HarnessCapabilityInvoker
from app.llm import LLMClient
from app.core.pilotdeck_agent_loop_client import StaffDeckModuleError


class StaffDeckPilotDeckModuleBridge:
    """Expose StaffDeck-owned modules to the PilotDeck sidecar."""

    def __init__(
        self,
        *,
        model_client: LLMClient,
        capability_invoker: HarnessCapabilityInvoker,
        permission_checker: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None,
        checkpoint_sink: Callable[[dict[str, Any]], Mapping[str, Any] | None] | None = None,
        remaining_actions: int | None = None,
    ) -> None:
        self.model_client = model_client
        self.capability_invoker = capability_invoker
        self.permission_checker = permission_checker
        self.checkpoint_sink = checkpoint_sink
        self._remaining_actions = remaining_actions

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
            canonical_messages = self._canonical_messages(request.get("messages"))
            user_payload: dict[str, Any] | str = {
                "tools": request.get("tools") or [],
                "tool_choice": request.get("toolChoice"),
                "metadata": request.get("metadata") or {},
            }
            if canonical_messages:
                user_payload["conversation_context"] = {"messages": canonical_messages}
        else:
            system_prompt = str(payload.get("systemPrompt") or "")
            user_payload = payload.get("userPayload")
            if not isinstance(user_payload, (dict, str)):
                user_payload = str(user_payload or "")
        if self._remaining_actions is not None:
            if self._remaining_actions <= 0:
                raise StaffDeckModuleError(
                    "ACTION_BUDGET_EXHAUSTED",
                    "StaffDeck action budget exhausted before the next model action.",
                )
            self._remaining_actions -= 1
        action = self.model_client.generate_json(system_prompt, user_payload)
        if not isinstance(action, dict):
            raise TypeError("StaffDeck model returned an empty or invalid JSON action.")
        events: list[dict[str, Any]] = [{"type": "message_start", "role": "assistant"}]
        if action.get("action") == "tool" and str(action.get("tool_name") or "").strip():
            call_id = str(action.get("tool_call_id") or "staffdeck-call")
            events.extend([
                {"type": "tool_call_end", "toolCall": {"id": call_id, "name": str(action["tool_name"]), "input": action.get("arguments") or {}}},
                {"type": "message_end", "finishReason": "tool_call"},
            ])
        else:
            raw_text = (
                action.get("reply_fragment") or action.get("reply")
            )
            text = str(raw_text or "")
            if text:
                events.append({"type": "text_delta", "text": text})
            events.append({"type": "message_end", "finishReason": "stop"})
        return {
            "events": events,
        }

    @staticmethod
    def _canonical_messages(messages: object) -> list[dict[str, Any]]:
        if not isinstance(messages, list):
            return []
        projected: list[dict[str, Any]] = []
        for raw in messages:
            if not isinstance(raw, dict):
                continue
            role = str(raw.get("role") or "").strip()
            if role not in {"user", "assistant"}:
                continue
            content = raw.get("content")
            text_parts: list[str] = []
            images: list[dict[str, Any]] = []
            blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    text_parts.append(block["text"])
                elif block.get("type") == "image" and block.get("source") == "base64":
                    mime = str(block.get("mimeType") or "application/octet-stream")
                    data = block.get("data")
                    if isinstance(data, str) and data:
                        images.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{data}"},
                        })
            for image in raw.get("images", []) if isinstance(raw.get("images"), list) else []:
                if isinstance(image, dict) and image.get("type") == "image_url":
                    image_url = image.get("image_url")
                    if isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
                        images.append({"type": "image_url", "image_url": {"url": image_url["url"]}})
            if text_parts or images:
                projected.append({
                    "role": role,
                    "content": "".join(text_parts),
                    **({"images": images} if images else {}),
                })
        return projected

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
        error_code = (
            str(error.get("code") or "tool_execution_failed")
            if isinstance(error, dict)
            else "tool_execution_failed"
        )
        error_message = (
            str(error.get("message") or "Capability invocation failed.")
            if isinstance(error, dict)
            else "Capability invocation failed."
        )
        retryable = error.get("retryable") if isinstance(error, dict) else None
        return {
            "type": "error",
            "toolCallId": tool_call_id,
            "toolName": name,
            "error": {
                "code": error_code,
                "message": error_message,
                **({"retryable": bool(retryable)} if retryable is not None else {}),
            },
            "content": [{"type": "text", "text": error_message}],
            "startedAt": "1970-01-01T00:00:00.000Z",
            "completedAt": "1970-01-01T00:00:00.000Z",
        }

    def permission(self, payload: dict[str, Any]) -> Mapping[str, Any]:
        if self.permission_checker is None:
            return {
                "allowed": False,
                "source": "staffdeck",
                "error": {
                    "code": "PERMISSION_UNAVAILABLE",
                    "message": "StaffDeck permission checker is not configured.",
                },
            }
        return dict(self.permission_checker(payload))

    def checkpoint(self, payload: dict[str, Any]) -> Mapping[str, Any]:
        if self.checkpoint_sink is None:
            return {"accepted": True}
        result = self.checkpoint_sink(payload)
        return dict(result or {"accepted": True})


__all__ = ["StaffDeckPilotDeckModuleBridge"]
