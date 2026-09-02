from __future__ import annotations

import json
import os
import select
import shlex
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.task_request_compiler import TaskExecutionResult, TaskRequirement


class PilotDeckAgentLoopError(RuntimeError):
    """Failure crossing the PilotDeck module boundary."""

    def __init__(self, code: str, message: str, *, result_unknown: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.result_unknown = result_unknown


ModuleBridge = Callable[[str, dict[str, Any]], Mapping[str, Any]]
TraceSink = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class PilotDeckExecutionIdentity:
    tenant_id: str
    session_id: str
    turn_id: str
    run_id: str
    operation_id: str
    idempotency_key: str
    step_id: str | None = None


class PilotDeckAgentLoopClient:
    """Synchronous StaffDeck client for a PilotDeck AgentLoop sidecar."""

    def __init__(
        self,
        command: str | list[str],
        *,
        cwd: str | None = None,
        timeout_seconds: float = 900.0,
        startup_timeout_seconds: float = 10.0,
    ) -> None:
        self.command = shlex.split(command) if isinstance(command, str) else list(command)
        if not self.command:
            raise ValueError("PilotDeck sidecar command must not be empty")
        self.cwd = cwd
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.startup_timeout_seconds = max(0.1, float(startup_timeout_seconds))
        self._process: subprocess.Popen[bytes] | None = None
        self._message_counter = 0
        self._connection_generation: str | None = None
        self._stdout_buffer = bytearray()

    def close(self) -> None:
        process = self._process
        self._process = None
        self._connection_generation = None
        self._stdout_buffer.clear()
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    def execute(
        self,
        requirement: TaskRequirement,
        *,
        identity: PilotDeckExecutionIdentity,
        checkpoint: dict[str, Any] | None = None,
        bridge: ModuleBridge | None = None,
        trace_sink: TraceSink | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        deadline_monotonic: float | None = None,
    ) -> TaskExecutionResult:
        self._ensure_process()
        process = self._require_process()
        request_id = self._next_id("execute")
        message_id = self._next_id("message")
        operation_deadline = _deadline_iso(deadline_monotonic, self.timeout_seconds)
        request = {
            "kind": "request",
            "messageId": message_id,
            "method": "execute",
            "runId": identity.run_id,
            "operationId": identity.operation_id,
            "requestId": request_id,
            "sessionId": identity.session_id,
            "turnId": identity.turn_id,
            "idempotencyKey": identity.idempotency_key,
            "operationDeadline": operation_deadline,
            "payload": {
                "tenantId": identity.tenant_id,
                "stepId": identity.step_id,
                "taskRequirement": requirement.model_dump(mode="json"),
                "checkpoint": dict(checkpoint or {}),
            },
        }
        self._write(request)
        stream_id: str | None = None
        expected_sequence = 0
        started = time.monotonic()
        cancel_sent = False
        while True:
            remaining = self._remaining_timeout(started, deadline_monotonic)
            if remaining <= 0:
                self._send_cancel(identity, request_id, "deadline_exceeded")
                raise PilotDeckAgentLoopError(
                    "DEADLINE_EXCEEDED",
                    "PilotDeck AgentLoop operation exceeded its deadline.",
                    result_unknown=True,
                )
            if is_cancelled and is_cancelled() and not cancel_sent:
                self._send_cancel(identity, request_id, "staffdeck_cancelled")
                cancel_sent = True
            message = self._read(remaining)
            if message.get("kind") == "request" and message.get("method") == "module_call":
                response = self._dispatch_module_call(message, bridge)
                self._write(response)
                continue
            if message.get("kind") == "error":
                raise PilotDeckAgentLoopError(
                    str(message.get("code") or "MODULE_ERROR"),
                    str(message.get("message") or "PilotDeck module error"),
                    result_unknown=message.get("retryability") == "retry_after_status",
                )
            if message.get("kind") == "response":
                if message.get("streamId"):
                    stream_id = str(message["streamId"])
                if message.get("final") is True:
                    return self._result_from_payload(message.get("payload"), message, requirement)
                continue
            if message.get("kind") != "event":
                continue
            if message.get("runId") != identity.run_id or message.get("operationId") != identity.operation_id:
                continue
            if stream_id is None:
                stream_id = str(message.get("streamId") or "")
            if str(message.get("streamId") or "") != stream_id:
                raise PilotDeckAgentLoopError("STREAM_MISMATCH", "PilotDeck stream identity changed.")
            sequence = int(message.get("sequence", -1))
            if sequence < expected_sequence:
                continue
            if sequence > expected_sequence:
                raise PilotDeckAgentLoopError("SEQUENCE_GAP", "PilotDeck stream sequence has a gap.", result_unknown=True)
            expected_sequence += 1
            payload = message.get("payload")
            if message.get("final") is not True and isinstance(payload, dict) and trace_sink:
                trace_sink(str(message.get("eventType") or "agent.event"), dict(payload))
            if message.get("final") is True:
                outcome = str(message.get("outcome") or "failed")
                if outcome == "cancelled":
                    raise PilotDeckAgentLoopError("CANCELLED", "PilotDeck AgentLoop was cancelled.")
                if outcome == "result_unknown":
                    raise PilotDeckAgentLoopError("RESULT_UNKNOWN", "PilotDeck result requires reconciliation.", result_unknown=True)
                return self._result_from_payload(payload, message, requirement)

    def _dispatch_module_call(
        self,
        request: Mapping[str, Any],
        bridge: ModuleBridge | None,
    ) -> dict[str, Any]:
        module = str(request.get("module") or "")
        payload = request.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        try:
            if bridge is None:
                raise PilotDeckAgentLoopError("MODULE_BRIDGE_UNAVAILABLE", f"No StaffDeck bridge for {module}.")
            result = dict(bridge(module, payload))
            return {
                "kind": "response",
                "messageId": self._next_id("module-result"),
                "inReplyTo": str(request.get("messageId") or ""),
                "requestId": str(request.get("requestId") or ""),
                "ok": True,
                "final": True,
                "outcome": "completed",
                "payload": result,
            }
        except PilotDeckAgentLoopError as exc:
            return {
                "kind": "response",
                "messageId": self._next_id("module-error"),
                "inReplyTo": str(request.get("messageId") or ""),
                "requestId": str(request.get("requestId") or ""),
                "ok": False,
                "final": True,
                "outcome": "result_unknown" if exc.result_unknown else "failed",
                "code": exc.code,
                "error": {"message": str(exc)},
            }
        except Exception as exc:
            return {
                "kind": "response",
                "messageId": self._next_id("module-error"),
                "inReplyTo": str(request.get("messageId") or ""),
                "requestId": str(request.get("requestId") or ""),
                "ok": False,
                "final": True,
                "outcome": "failed",
                "code": "STAFFDECK_MODULE_ERROR",
                "error": {"message": str(exc)},
            }

    def _send_cancel(self, identity: PilotDeckExecutionIdentity, request_id: str, reason: str) -> None:
        try:
            self._write({
                "kind": "request",
                "messageId": self._next_id("cancel"),
                "method": "cancel",
                "runId": identity.run_id,
                "operationId": identity.operation_id,
                "requestId": request_id,
                "reason": reason,
            })
        except PilotDeckAgentLoopError:
            pass

    def _ensure_process(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        self.close()
        try:
            self._process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                bufsize=0,
                env=os.environ.copy(),
            )
            hello_id = self._next_id("hello")
            self._write({
                "kind": "request",
                "messageId": hello_id,
                "method": "hello",
                "payload": {"protocolVersion": "2.0", "client": "staffdeck"},
            })
            response = self._read(self.startup_timeout_seconds)
            if response.get("kind") != "response" or response.get("ok") is not True:
                raise PilotDeckAgentLoopError("HANDSHAKE_FAILED", "PilotDeck sidecar hello failed.")
            self._connection_generation = str(response.get("connectionGeneration") or "")
        except (OSError, PilotDeckAgentLoopError):
            self.close()
            raise

    def _require_process(self) -> subprocess.Popen[bytes]:
        if self._process is None or self._process.poll() is not None:
            raise PilotDeckAgentLoopError("SIDECAR_NOT_RUNNING", "PilotDeck sidecar is not running.", result_unknown=True)
        return self._process

    def _write(self, message: Mapping[str, Any]) -> None:
        process = self._require_process() if self._process is not None else self._process
        if process is None or process.stdin is None:
            raise PilotDeckAgentLoopError("SIDECAR_NOT_RUNNING", "PilotDeck sidecar stdin is unavailable.", result_unknown=True)
        try:
            process.stdin.write((json.dumps(dict(message), ensure_ascii=False) + "\n").encode("utf-8"))
            process.stdin.flush()
        except OSError as exc:
            raise PilotDeckAgentLoopError("SIDECAR_WRITE_FAILED", str(exc), result_unknown=True) from exc

    def _read(self, timeout: float) -> dict[str, Any]:
        process = self._require_process()
        if process.stdout is None:
            raise PilotDeckAgentLoopError("SIDECAR_STDOUT_UNAVAILABLE", "PilotDeck sidecar stdout is unavailable.", result_unknown=True)
        deadline = time.monotonic() + max(0.01, timeout)
        while True:
            newline = self._stdout_buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self._stdout_buffer[:newline])
                del self._stdout_buffer[: newline + 1]
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PilotDeckAgentLoopError("SIDECAR_TIMEOUT", "Timed out waiting for PilotDeck sidecar.", result_unknown=True)
            ready, _, _ = select.select([process.stdout], [], [], remaining)
            if not ready:
                raise PilotDeckAgentLoopError("SIDECAR_TIMEOUT", "Timed out waiting for PilotDeck sidecar.", result_unknown=True)
            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                raise PilotDeckAgentLoopError("SIDECAR_EXITED", "PilotDeck sidecar exited before a terminal result.", result_unknown=True)
            self._stdout_buffer.extend(chunk)
        try:
            value = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise PilotDeckAgentLoopError("INVALID_SIDECAR_JSON", "PilotDeck sidecar returned invalid JSON.", result_unknown=True) from exc
        if not isinstance(value, dict):
            raise PilotDeckAgentLoopError("INVALID_SIDECAR_MESSAGE", "PilotDeck sidecar message must be an object.", result_unknown=True)
        return value

    def _result_from_payload(
        self,
        payload: Any,
        message: Mapping[str, Any],
        requirement: TaskRequirement,
    ) -> TaskExecutionResult:
        if isinstance(payload, dict) and isinstance(payload.get("result"), dict):
            payload = payload["result"]
        if isinstance(payload, dict):
            try:
                return TaskExecutionResult.model_validate(payload)
            except Exception:
                error = payload.get("error")
                text = _final_message_text(payload)
                parsed = _parse_task_result_text(text, requirement.task_frame_id)
                if parsed is not None:
                    return parsed
                outcome = str(message.get("outcome") or "failed")
                return TaskExecutionResult(
                    task_frame_id=requirement.task_frame_id,
                    status="completed" if outcome == "completed" else "failed",
                    reply_fragment=text,
                    error=(
                        {"code": "PILOTDECK_EXECUTION_FAILED", "message": str(error)}
                        if outcome != "completed" and error
                        else None
                    ),
                )
        else:
            error = None
        outcome = str(message.get("outcome") or "failed")
        return TaskExecutionResult(
            task_frame_id="",
            status="failed" if outcome != "completed" else "action_budget",
            error=error if isinstance(error, dict) else {"code": "INVALID_RESULT", "message": "PilotDeck returned an invalid TaskExecutionResult."},
        )

    def _remaining_timeout(self, started: float, deadline_monotonic: float | None) -> float:
        remaining = self.timeout_seconds - (time.monotonic() - started)
        if deadline_monotonic is not None:
            remaining = min(remaining, deadline_monotonic - time.monotonic())
        return remaining

    def _next_id(self, prefix: str) -> str:
        self._message_counter += 1
        return f"{prefix}-{self._message_counter}"


def _final_message_text(payload: Mapping[str, Any]) -> str:
    final_message = payload.get("finalMessage")
    if not isinstance(final_message, Mapping):
        return ""
    content = final_message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, Mapping) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _parse_task_result_text(text: str, task_frame_id: str) -> TaskExecutionResult | None:
    if not text.strip():
        return None
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    value.setdefault("task_frame_id", task_frame_id)
    if value.get("status") not in {
        "completed",
        "awaiting_user",
        "handoff",
        "failed",
        "blocked",
        "action_budget",
    }:
        return None
    try:
        return TaskExecutionResult.model_validate(value)
    except Exception:
        return None

def _deadline_iso(deadline_monotonic: float | None, timeout_seconds: float) -> str:
    seconds = timeout_seconds if deadline_monotonic is None else max(0.0, deadline_monotonic - time.monotonic())
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


__all__ = [
    "ModuleBridge",
    "PilotDeckAgentLoopClient",
    "PilotDeckAgentLoopError",
    "PilotDeckExecutionIdentity",
]
