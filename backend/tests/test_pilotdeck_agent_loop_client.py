from __future__ import annotations

import sys

from app.core.pilotdeck_agent_loop_client import (
    PilotDeckAgentLoopClient,
    PilotDeckExecutionIdentity,
)
from app.core.task_request_compiler import TaskRequirement


SIDECAR = r'''
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("method") == "hello":
        print(json.dumps({"kind":"response","messageId":"hello-res","inReplyTo":msg["messageId"],"ok":True,"connectionGeneration":"test-connection"}), flush=True)
    elif msg.get("method") == "execute":
        print(json.dumps({"kind":"response","messageId":"accepted","inReplyTo":msg["messageId"],"requestId":msg["requestId"],"ok":True,"streamId":"stream-1","cursor":0}), flush=True)
        print(json.dumps({"kind":"request","messageId":"module-call","method":"module_call","runId":msg["runId"],"operationId":msg["operationId"],"requestId":"module-request","module":"capability","payload":{"name":"lookup","arguments":{}}}), flush=True)
    elif msg.get("kind") == "response" and msg.get("inReplyTo") == "module-call":
        print(json.dumps({"kind":"event","messageId":"event-1","eventType":"agent.tool_result","streamId":"stream-1","sequence":0,"runId":"run-1","operationId":"op-1","requestId":"request-1","final":False,"payload":{"tool":"lookup"}}), flush=True)
        print(json.dumps({"kind":"event","messageId":"final-1","eventType":"agent.execute.completed","streamId":"stream-1","sequence":1,"runId":"run-1","operationId":"op-1","requestId":"request-1","final":True,"outcome":"completed","payload":{"result":{"task_frame_id":"frame-1","status":"completed","reply_fragment":"done","action_count":1}}}), flush=True)
'''


def _requirement() -> TaskRequirement:
    return TaskRequirement(task_frame_id="frame-1", kind="conversation", goal="lookup")


def test_sidecar_client_dispatches_host_module_call_and_decodes_result() -> None:
    client = PilotDeckAgentLoopClient([sys.executable, "-u", "-c", SIDECAR])
    traces: list[str] = []
    result = client.execute(
        _requirement(),
        identity=PilotDeckExecutionIdentity(
            tenant_id="tenant-1",
            session_id="session-1",
            turn_id="turn-1",
            run_id="run-1",
            operation_id="op-1",
            idempotency_key="frame-1",
        ),
        bridge=lambda module, payload: {"success": True, "module": module, "payload": payload},
        trace_sink=lambda event_type, payload: traces.append(event_type),
    )
    client.close()
    assert result.status == "completed"
    assert result.reply_fragment == "done"
    assert traces == ["agent.tool_result"]
