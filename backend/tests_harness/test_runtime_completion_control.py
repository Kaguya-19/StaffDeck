from app.core.task_request_compiler import TaskRequirement
from staffdeck_harness.bridge.control import ExecutionHost
from staffdeck_harness.composition.compiler import CompositionCompiler
from tests_harness.test_capability_host_hardening import db as db, _host, _staff, _ctx
import pytest


def test_conversation_cannot_submit_a_sop_result(db):
    cap = _host(db, CompositionCompiler(hooks=()).compile(_staff()))
    execution = ExecutionHost(
        cap, TaskRequirement(task_frame_id="tf1", kind="conversation", goal="chat")
    )
    assert "submit_step_result" not in execution.model_tool_names()
    result, receipt = execution.invoke_proxy(
        "submit_step_result", {"status": "completed", "reply_fragment": "hi"}, _ctx()
    )
    assert result.error["code"] == "CONTROL_UNAVAILABLE" and receipt is None
    assert cap.slot.finish is None and not cap.slot.closed


def test_completion_requires_successful_node_capabilities_before_closing(db):
    cap = _host(db, CompositionCompiler(hooks=()).compile(_staff()))
    req = TaskRequirement(
        task_frame_id="tf1", kind="sop", goal="flow", required_capability_names=["required-tool"]
    )
    execution = ExecutionHost(cap, req)
    result, _ = execution.invoke_proxy(
        "submit_step_result", {"status": "completed", "reply_fragment": "done"}, _ctx()
    )
    assert result.error["code"] == "REQUIRED_CAPABILITY_NOT_INVOKED" and not cap.slot.closed
    cap.results.append({"tool_name": "required-tool", "success": True})
    result, _ = execution.invoke_proxy(
        "submit_step_result",
        {"status": "completed", "reply_fragment": "done", "next_step_id": None},
        _ctx(),
    )
    assert result.success and cap.slot.closed


def test_collect_step_cannot_pause_when_expected_slots_are_filled(db):
    cap = _host(db, CompositionCompiler(hooks=()).compile(_staff()))
    req = TaskRequirement(
        task_frame_id="tf1",
        kind="sop",
        goal="collect",
        expected_slots=["project_goal"],
        sop_context={
            "step": {
                "node_id": "n1_collect",
                "type": "collect_info",
                "expected_user_info": ["project_goal"],
            }
        },
        allowed_transitions=[{"next_node_id": "build_plan"}],
    )
    cap.slot.allowed_next_steps = frozenset({"build_plan"})
    execution = ExecutionHost(cap, req)
    result, _ = execution.invoke_proxy(
        "submit_step_result",
        {
            "status": "awaiting_user",
            "reply_fragment": "请确认。",
            "slot_updates": {"project_goal": "完成验证交付"},
        },
        _ctx(),
    )
    assert result.error["code"] == "COLLECT_STEP_MUST_ADVANCE"
    assert not cap.slot.closed


def test_missing_slots_wait_cannot_advance_and_can_be_repaired(db):
    cap = _host(db, CompositionCompiler(hooks=()).compile(_staff()))
    cap.slot.allowed_next_steps = frozenset({"build_plan"})
    req = TaskRequirement(
        task_frame_id="tf1", kind="sop", goal="collect",
        expected_slots=["project_goal", "current_stage", "known_blockers"],
        sop_context={"step": {"node_id": "n1_collect", "type": "collect_info",
                              "expected_user_info": ["project_goal", "current_stage", "known_blockers"]}},
        allowed_transitions=[{"next_node_id": "build_plan"}],
    )
    execution = ExecutionHost(cap, req)
    arguments = {"status": "awaiting_user", "reply_fragment": "请补充阶段和阻塞。",
                 "slot_updates": {"project_goal": "交付新版本"}, "next_step_id": "build_plan"}
    result, _ = execution.invoke_proxy("submit_step_result", arguments, _ctx())
    assert not result.success
    assert result.error["code"] == "AWAITING_USER_CANNOT_ADVANCE"
    assert cap.slot.finish is None and not cap.slot.closed
    result, _ = execution.invoke_proxy(
        "submit_step_result", {**arguments, "next_step_id": None}, _ctx()
    )
    assert result.success and cap.slot.closed
    assert cap.slot.finish["status"] == "awaiting_user"
    assert cap.slot.finish["next_step_id"] is None
    assert cap.slot.finish["slot_updates"] == {"project_goal": "交付新版本"}


def test_handoff_control_is_an_accepted_sop_completion(db):
    cap = _host(db, CompositionCompiler(hooks=()).compile(_staff()))
    execution = ExecutionHost(
        cap,
        TaskRequirement(task_frame_id="tf1", kind="sop", goal="confirm", allowed_transitions=[]),
    )

    result, _ = execution.invoke_proxy(
        "submit_step_result",
        {"status": "handoff", "reply_fragment": "请负责人确认范围变更。"},
        _ctx(),
    )

    assert result.success and cap.slot.closed
    assert cap.slot.finish["status"] == "handoff"


def test_control_cannot_select_an_unlisted_transition(db):
    cap = _host(db, CompositionCompiler(hooks=()).compile(_staff()))
    execution = ExecutionHost(cap, TaskRequirement(task_frame_id="tf1", kind="sop", goal="flow"))
    result, _ = execution.invoke_proxy(
        "submit_step_result",
        {"status": "completed", "reply_fragment": "done", "next_step_id": "injected-node"},
        _ctx(),
    )
    assert result.error["code"] == "INVALID_TRANSITION" and not cap.slot.closed


def test_sop_prompt_preserves_native_handoff_node_contract():
    from staffdeck_harness.bridge.task_agent import _step_prompt

    req = TaskRequirement(
        task_frame_id="tf1",
        kind="sop",
        goal="确认范围变更",
        sop_context={
            "skill_id": "project_delivery_plan",
            "step": {
                "node_id": "confirm_scope",
                "type": "handoff",
                "name": "确认范围变更",
                "instruction": "范围发生变化时，请负责人确认影响与后续安排。",
                "allowed_actions": ["handoff_human"],
            },
        },
    )

    prompt = _step_prompt(req, None, [], "")

    assert '"type": "handoff"' in prompt
    assert '"handoff_human"' in prompt
    assert 'status="handoff"' in prompt
    assert 'status="awaiting_user"' in prompt

    ordinary = req.model_copy(
        update={
            "sop_context": {
                "skill_id": "project_delivery_plan",
                "step": {"node_id": "build_plan", "type": "response", "allowed_actions": ["answer_user"]},
            }
        }
    )
    assert "当前节点声明了人工交接动作" not in _step_prompt(ordinary, None, [], "")



def test_handoff_control_schema_describes_native_handoff_status():
    from types import SimpleNamespace
    from staffdeck_harness.bridge.control import ExecutionHost

    req = TaskRequirement(
        task_frame_id="tf1",
        kind="sop",
        goal="confirm",
        sop_context={"step": {"type": "handoff", "allowed_actions": ["handoff_human"]}},
    )
    execution = ExecutionHost(SimpleNamespace(), req)
    submit = next(item for item in execution.tool_schemas() if item["name"] == "submit_step_result")
    assert "status=handoff" in submit["description"]
    assert "awaiting_user" in submit["description"]


def test_collect_prompt_prioritizes_node_boundary_and_advancement():
    from staffdeck_harness.bridge.task_agent import _step_prompt

    req = TaskRequirement(
        task_frame_id="tf1",
        kind="sop",
        goal="完成项目计划",
        requirements=["评估范围变化并等待负责人审批"],
        current_user_message="目标、阶段和阻塞项都已提供。",
        expected_slots=["project_goal", "current_stage", "known_blockers"],
        sop_context={
            "skill_id": "project_delivery_plan",
            "step": {
                "node_id": "n1_collect",
                "type": "collect_info",
                "instruction": "提取项目状态",
                "expected_user_info": ["project_goal", "current_stage", "known_blockers"],
            },
        },
        allowed_transitions=[{"next_node_id": "build_plan"}],
    )

    prompt = _step_prompt(req, None, [], "")
    assert "当前节点契约优先于整帧目标" in prompt
    assert "不要在 collect_info 节点执行后续节点的影响分析、审批或最终行动清单" in prompt
    assert "status=\"completed\"" in prompt
    assert "build_plan" in prompt

    response_prompt = _step_prompt(
        req.model_copy(
            update={
                "sop_context": {
                    "skill_id": "project_delivery_plan",
                    "step": {
                        "node_id": "build_plan",
                        "type": "response",
                        "instruction": "生成推进计划",
                    },
                }
            }
        ),
        None,
        [],
        "",
    )
    assert "response 节点只负责生成本节点" in response_prompt
    assert "不要因为后续节点需要用户确认就把本节点提前提交为 awaiting_user" in response_prompt


def test_completed_control_cannot_erase_an_already_filled_required_slot(db):
    cap = _host(db, CompositionCompiler(hooks=()).compile(_staff()))
    req = TaskRequirement(task_frame_id="tf1", kind="sop", goal="collect",
                          expected_slots=["quota"], known_slots={"quota": 4})
    execution = ExecutionHost(cap, req)
    result, _ = execution.invoke_proxy("submit_step_result",
        {"status": "completed", "reply_fragment": "完成", "slot_updates": {"quota": "  "}}, _ctx())
    assert result.error["code"] == "REQUIRED_SLOT_MISSING"
    assert not cap.slot.closed and cap.slot.finish is None
    result, _ = execution.invoke_proxy("submit_step_result",
        {"status": "completed", "reply_fragment": "完成", "slot_updates": {"quota": 0}}, _ctx())
    assert result.success and cap.slot.closed


@pytest.mark.parametrize("status", ["completed", "awaiting_user", "handoff", "failed"])
def test_native_conversation_result_uses_v2_status_and_slot_normalization(db, status):
    from app.core.harness_agent import HarnessAction, finish_execution_result
    from staffdeck_harness.bridge.task_agent import HarnessV3TaskAgent
    from staffdeck_harness.interactions.pipeline_host import PipelineState

    cap = _host(db, CompositionCompiler(hooks=()).compile(_staff()))
    req = TaskRequirement(task_frame_id="tf1", kind="conversation", goal="chat")
    action = HarnessAction(
        action="finish",
        status=status,
        reply_fragment="reply",
        slot_updates={"confirmed": True},
        next_step_id="not-a-sop-step",
    )
    expected = finish_execution_result(req, action, [], [], [], [], action_count=1)
    runner = HarnessV3TaskAgent.__new__(HarnessV3TaskAgent)
    runner._host = cap
    actual = runner._result(
        req, cap.slot, PipelineState(cap.slot.snapshot), action.model_dump_json(), "stop", 1, [], []
    )
    assert actual.model_dump() == expected.model_dump()
    assert not cap.slot.closed, "a native reply is not a control-tool submission"


def test_marker_only_checkpoint_recovers_only_its_own_sop_public_history(db):
    from app.core.task_frame_store import TaskFrameStore
    from app.db.models import ChatSession, HarnessTaskFrameRecord, HarnessRunRecord, Message
    import json

    session = ChatSession(id="s1", tenant_id="t1", user_id="u1", agent_id="a1")
    row = HarnessTaskFrameRecord(
        tenant_id="t1", session_id="s1", task_id="f1", source_turn_id="m1", kind="sop"
    )
    other = HarnessTaskFrameRecord(
        tenant_id="t1", session_id="s1", task_id="f2", source_turn_id="m2", kind="sop"
    )
    db.add_all([session, row, other])
    db.commit()
    store = TaskFrameStore(db)
    logical, foreign = store.ensure_agent_loop(row), store.ensure_agent_loop(other)
    for frame, loop, text in ((row, logical, "OWN-NONCE"), (other, foreign, "OTHER-SECRET")):
        db.add(
            Message(
                id=frame.source_turn_id, tenant_id="t1", session_id="s1", role="user", content=text
            )
        )
        db.add(
            HarnessRunRecord(
                tenant_id="t1",
                session_id="s1",
                task_frame_record_id=frame.id,
                agent_loop_id=loop.id,
                task_id=frame.task_id,
                source_turn_id=frame.source_turn_id,
                status="awaiting_user",
                task_requirement_json={"known_slots": {"token": text}},
                result_json={"reply_fragment": text, "slot_updates": {"token": text}},
            )
        )
    logical.checkpoint_json = {"engine": "harness_v3", "version": 1, "task_frame_id": row.task_id}
    db.add(logical)
    db.commit()
    recovered = store.execution_checkpoint(row, logical)
    assert "OWN-NONCE" in json.dumps(recovered)
    assert "OTHER-SECRET" not in json.dumps(recovered)
    assert recovered["history_recovery_source"] == "legacy_public_runs"
