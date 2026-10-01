from __future__ import annotations

import asyncio
import shlex
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from app.api.chat import download_harness_artifact
from app.core.harness_session_cleanup import harness_task_workspace_path
from app.core.task_request_compiler import TaskExecutionResult
from app.core.turn_coordinator import _aggregate_artifacts, _merge_discovered_artifacts
from app.db.models import Message, User, utc_now
from app.harness import (
    HarnessExecutor,
    HarnessToolCall,
    HarnessToolContext,
    build_file_tool_registry,
    publish_changed_harness_artifacts,
    register_command_tools,
    snapshot_harness_workspace,
)
from tests.test_harness_artifact_download import _read_response_body, _seed_artifact


@pytest.mark.parametrize("initial_size,final_size", [(490, 245), (1110, 149)])
@pytest.mark.parametrize("publication", ["same_message", "later_message"])
def test_final_same_path_rewrite_downloads_after_database_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    initial_size: int, final_size: int, publication: str,
) -> None:
    monkeypatch.setenv("ULTRARAG_DATA_DIR", str(tmp_path / "data"))
    url = f"sqlite:///{tmp_path / 'state.sqlite'}"
    engine = create_engine(url)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_artifact(db)
        workspace = harness_task_workspace_path(
            tenant_id="tenant_demo", session_id="session_demo", task_frame_id="task_demo", db=db,
        )
        workspace.mkdir(parents=True, exist_ok=True)
        before = snapshot_harness_workspace(workspace)
        registry = build_file_tool_registry()
        register_command_tools(registry)
        executor = HarnessExecutor(registry)
        context = HarnessToolContext(
            run_id="run_demo", task_frame_id="task_demo", tenant_id="tenant_demo",
            workspace_root=workspace, sandbox_enabled=False,
        )
        path = "reports/result.txt"
        initial = "initial draft\n".ljust(initial_size, "a")
        final = "final observed file\n".ljust(final_size, "b")
        written = executor.execute(context, HarnessToolCall(
            call_id="early-write", name="write_file",
            arguments={"path": path, "content": initial, "create_parents": True},
        ))
        assert written.success
        early = publish_changed_harness_artifacts(workspace, "task_demo", before, operation="workspace_discovery")
        assert early[0]["size"] == initial_size
        # R99: a provisional result precedes a later successful shell rewrite/readback.
        overwritten = executor.execute(context, HarnessToolCall(
            call_id="later-rewrite", name="exec_command",
            arguments={"command": f"printf %s {shlex.quote(final)} > {path}"},
        ))
        assert overwritten.success and overwritten.data["ok"] is True
        readback = executor.execute(context, HarnessToolCall(
            call_id="final-read", name="read_file", arguments={"path": path},
        ))
        assert readback.success
        assert (workspace / path).read_text() == final
        latest = publish_changed_harness_artifacts(workspace, "task_demo", before, operation="workspace_discovery")
        assert latest[0]["size"] == final_size
        early_result = TaskExecutionResult(task_frame_id="task_demo", status="completed", artifacts=early)
        final_result = TaskExecutionResult(task_frame_id="task_demo", status="completed", artifacts=[*early, *latest])
        message = db.get(Message, "msg_assistant")
        assert message is not None
        if publication == "same_message":
            message.metadata_json = {"harness_artifacts": _aggregate_artifacts([early_result, final_result])}
        else:
            message.created_at = utc_now() - timedelta(seconds=1)
            message.metadata_json = {"harness_artifacts": early}
            db.add(Message(id="msg_final", tenant_id="tenant_demo", session_id="session_demo",
                role="assistant", content="Final result", metadata_json={"harness_artifacts": latest}))
        db.add(message)
        db.commit()
    engine.dispose()

    # A new engine/connection reads durable publication metadata, as after restart.
    engine = create_engine(url)
    with Session(engine) as db:
        user = db.get(User, "user_owner")
        assert user is not None
        response = download_harness_artifact("session_demo", "task_demo", tenant_id="tenant_demo",
            path=path, current_user=user, db=db)
        assert asyncio.run(_read_response_body(response)) == final.encode()
        assert response.headers["content-length"] == str(final_size)
        selected = db.get(Message, "msg_assistant" if publication == "same_message" else "msg_final")
        assert selected is not None
        metadata = selected.metadata_json["harness_artifacts"]
        assert len(metadata) == 1 and metadata[0]["size"] == final_size
        assert metadata[0]["operation"] == "workspace_discovery"
        print(f"{publication}: persisted {initial_size}->{final_size}, reopened download PASS")
        # Same-size mutation after the final publication still must fail the digest guard.
        (workspace / path).write_text("x" * final_size)
        with pytest.raises(HTTPException) as changed:
            download_harness_artifact("session_demo", "task_demo", tenant_id="tenant_demo",
                path=path, current_user=user, db=db)
        assert changed.value.status_code == 409
    engine.dispose()


def test_final_discovery_refreshes_exact_identity_with_inventory_at_limit() -> None:
    early = [{"type": "workspace_file", "task_frame_id": "task_demo", "path": f"{index}.txt", "size": 490}
        for index in range(20)]
    result = TaskExecutionResult(task_frame_id="task_demo", status="completed", artifacts=early)
    latest = {**early[0], "size": 245, "operation": "workspace_discovery"}
    overflow = {**latest, "path": "unselected.txt"}
    _merge_discovered_artifacts(result, [overflow, latest])
    assert len(result.artifacts) == 20
    assert result.artifacts[0] == latest
    other_frame = {**latest, "task_frame_id": "task_other"}
    handoff = {"type": "human_handoff", "handoff_id": "handoff_real", "task_frame_id": "task_demo"}
    combined = _aggregate_artifacts([TaskExecutionResult(task_frame_id="task_demo", status="handoff",
        artifacts=[early[0], other_frame, handoff, latest])])
    assert combined == [latest, other_frame, handoff]
