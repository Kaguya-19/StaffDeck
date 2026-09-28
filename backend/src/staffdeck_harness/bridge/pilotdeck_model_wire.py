"""Loss-aware OpenAI Harness wire ↔ PD public canonical model Port."""
from __future__ import annotations

import json
from typing import Any


class UnsupportedModelWire(ValueError):
    pass


def canonical_request(body: dict[str, Any], selection: Any) -> dict[str, Any]:
    messages = []
    system = []
    for message in body["messages"]:
        if not isinstance(message, dict):
            raise UnsupportedModelWire("message must be an object")
        role, content = message.get("role"), message.get("content")
        if role == "system":
            if not isinstance(content, str):
                raise UnsupportedModelWire("non-text system message")
            system.append(content)
            continue
        if role == "tool":
            if not isinstance(message.get("tool_call_id"), str) or not isinstance(content, str):
                raise UnsupportedModelWire("invalid tool result")
            messages.append({"role": "user", "content": [{"type": "tool_result",
                "toolCallId": message["tool_call_id"], "content": [{"type": "text", "text": content}]}]})
            continue
        if role not in ("user", "assistant"):
            raise UnsupportedModelWire("unsupported message role")
        blocks = []
        if isinstance(content, str):
            blocks.append({"type": "text", "text": content})
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    raise UnsupportedModelWire("invalid content block")
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    blocks.append({"type": "text", "text": part["text"]})
                elif part.get("type") == "image_url":
                    image = part.get("image_url")
                    url = image.get("url") if isinstance(image, dict) else image
                    if not isinstance(url, str):
                        raise UnsupportedModelWire("invalid image URL")
                    if url.startswith("data:"):
                        header, sep, data = url.partition(",")
                        if not sep or not header.endswith(";base64"):
                            raise UnsupportedModelWire("invalid image data URL")
                        blocks.append({"type": "image", "source": "base64", "mimeType": header[5:-7], "data": data})
                    else:
                        blocks.append({"type": "image", "source": "url", "mimeType": "image/*", "data": url})
                else:
                    raise UnsupportedModelWire("unsupported content block")
        elif content is not None:
            raise UnsupportedModelWire("unsupported message content")
        for call in message.get("tool_calls") or []:
            fn = call.get("function") if isinstance(call, dict) else None
            if not isinstance(fn, dict) or not isinstance(call.get("id"), str) \
                    or not isinstance(fn.get("name"), str) or not isinstance(fn.get("arguments"), str):
                raise UnsupportedModelWire("invalid assistant tool call")
            try:
                arguments = json.loads(fn["arguments"])
            except ValueError as exc:
                raise UnsupportedModelWire("invalid assistant tool arguments") from exc
            blocks.append({"type": "tool_call", "id": call["id"],
                           "name": fn["name"], "input": arguments})
        messages.append({"role": role, "content": blocks})
    request = {"provider": selection.provider, "model": selection.model,
               "messages": messages, "stream": True}
    if system:
        request["systemPrompt"] = "\n\n".join(system)
    if body.get("tools"):
        tools = []
        for tool in body["tools"]:
            fn = tool.get("function") if isinstance(tool, dict) else None
            if not isinstance(tool, dict) or tool.get("type") != "function" or not isinstance(fn, dict) \
                    or not isinstance(fn.get("name"), str) or not isinstance(fn.get("parameters"), dict):
                raise UnsupportedModelWire("unsupported tool schema")
            tools.append({"name": fn["name"], "description": fn.get("description") or "",
                          "inputSchema": fn["parameters"]})
        request["tools"] = tools
        choice = body.get("tool_choice", "auto")
        if isinstance(choice, dict):
            fn = choice.get("function")
            if choice.get("type") != "function" or not isinstance(fn, dict) or not isinstance(fn.get("name"), str):
                raise UnsupportedModelWire("unsupported tool choice")
            choice = {"type": "tool", "name": fn["name"]}
        if choice not in ("auto", "none", "required") and not isinstance(choice, dict):
            raise UnsupportedModelWire("unsupported tool choice")
        request["toolChoice"] = choice
    if body.get("stop"):
        raise UnsupportedModelWire("stop sequences are unavailable on the PD model Port")
    max_tokens = body.get("max_tokens")
    # Harness emits 256k as an unspecified default. Let the selected PD model
    # apply its own configured output cap in that case.
    if isinstance(max_tokens, int) and 0 < max_tokens < 256000:
        request["maxOutputTokens"] = max_tokens
    if isinstance(body.get("temperature"), (float, int)):
        request["temperature"] = body["temperature"]
    return request


def openai_chunks(events, selection: Any):
    """Convert canonical deltas, tool calls, usage and terminal state to Harness SSE chunks."""
    indexes: dict[str, int] = {}
    arguments: dict[str, str] = {}
    finished = False
    for event in events:
        kind = event["type"]
        delta: dict[str, Any] = {}
        if kind == "text_delta":
            delta = {"content": event["text"]}
        elif kind == "thinking_delta":
            delta = {"reasoning_content": event["text"]}
        elif kind == "tool_call_start":
            identifier = event["id"]
            if identifier in indexes:
                raise RuntimeError("PUBLIC_HOST_MODEL_STREAM_INVALID")
            indexes[identifier] = len(indexes)
            arguments[identifier] = ""
            delta = {"tool_calls": [{"index": indexes[identifier], "id": identifier,
                                      "type": "function", "function": {"name": event["name"], "arguments": ""}}]}
        elif kind == "tool_call_delta":
            identifier = event["id"]
            if identifier not in indexes or not isinstance(event.get("delta"), str):
                raise RuntimeError("PUBLIC_HOST_MODEL_STREAM_INVALID")
            arguments[identifier] += event["delta"]
            delta = {"tool_calls": [{"index": indexes[identifier],
                                      "function": {"arguments": event["delta"]}}]}
        elif kind == "tool_call_end":
            call = event.get("toolCall")
            if not isinstance(call, dict) or call.get("id") not in indexes:
                raise RuntimeError("PUBLIC_HOST_MODEL_STREAM_INVALID")
            identifier = call["id"]
            complete = json.dumps(call.get("input"), ensure_ascii=False, separators=(",", ":"))
            if arguments[identifier]:
                try:
                    matches = json.loads(arguments[identifier]) == call.get("input")
                except ValueError:
                    matches = False
                if not matches:
                    raise RuntimeError("PUBLIC_HOST_MODEL_TOOL_ARGUMENT_MISMATCH")
            else:
                delta = {"tool_calls": [{"index": indexes[identifier],
                                          "function": {"arguments": complete}}]}
        elif kind == "message_end":
            reason = event.get("finishReason")
            if reason not in ("stop", "length", "tool_call", "content_filter"):
                raise RuntimeError("PUBLIC_HOST_MODEL_INCOMPLETE")
            finished = True
            yield {"id": "pd-host", "object": "chat.completion.chunk", "model": selection.model,
                   "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls" if reason == "tool_call" else reason}]}
            continue
        elif kind == "usage":
            usage = event.get("usage")
            if isinstance(usage, dict):
                yield {"id": "pd-host", "object": "chat.completion.chunk", "model": selection.model,
                       "choices": [], "usage": {"prompt_tokens": usage.get("inputTokens", 0),
                                                "completion_tokens": usage.get("outputTokens", 0),
                                                "total_tokens": usage.get("totalTokens", 0)}}
            continue
        elif kind == "error":
            raise RuntimeError("PUBLIC_HOST_MODEL_FAILED")
        elif kind not in ("request_started", "message_start"):
            raise RuntimeError("PUBLIC_HOST_MODEL_STREAM_INVALID")
        if delta:
            yield {"id": "pd-host", "object": "chat.completion.chunk", "model": selection.model,
                   "choices": [{"index": 0, "delta": delta, "finish_reason": None}]}
    if not finished:
        raise RuntimeError("PUBLIC_HOST_MODEL_INCOMPLETE")
