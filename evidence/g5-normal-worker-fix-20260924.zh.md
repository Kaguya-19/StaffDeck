# G5 normal worker 修复与真实运行证据

日期：2026-09-24
范围：只修改 StaffDeck 自有 checkout；没有修改验收固定 trees 或共享报告。

## 修复结论

Harness v3 的正常知识检索路径仍使用已配置的 `deps.model_config`。本次修复没有把它替换为 `None`，也没有把 lexical ranking 设为默认路由。

修改内容：

- `backend/app/config.py` 增加 `harness_v3_knowledge_route_timeout_seconds`，默认 30 秒。
- `backend/src/staffdeck_harness/capabilities/local_services.py` 在 Harness v3 的 nested Knowledge route 上复制 model config，仅收窄 nested provider 请求的 `timeout_seconds`，并保留现有 `KnowledgeService` 异常后的 lexical fallback。
- 非 Harness v3、无 model config 的路径保持原对象/原行为。

配置的 Knowledge model route 仍然会被尝试。30 秒是单次 nested model client 的请求 timeout，不是整个知识检索或 SOP 的墙钟上限；SDK 重试及文档/索引两次路由可能使总耗时更长。

## 固定输入

| 组件 | fixed ref |
|---|---|
| PilotDeck | `fe2f7cbdbd47edf523ad15200ff991ce2343427d` |
| StaffDeck | `85ac9ae5020f82795243ff313ea61ebc5d49104a` |

## 当前真实 bounded run

本次使用真实 provider、真实 public API、真实 Harness v3 AgentLoop 和真实项目知识库；临时 SQLite/Harness home 位于 `/tmp/g5-worker-fix.Ez6uAp`。

- Job：`apijob_837c5673c0fe4be9`
- Session：`session_f1cadb61db7041fb`
- 运行时间：`2026-09-24T01:52:52Z` 至 `2026-09-24T01:53:52Z`
- 终态：`succeeded / completed / progress=1.0`
- 真实 `mcp__staffdeck__knowledge_search` 返回 `kb_preset_project_001` 的 citation/evidence，并产生 `run.capability.completed`、`run.citation`。
- normal SOP 经过 `n1_collect -> build_plan -> confirm_scope`；一次 malformed structured result 被真实 harness 报错后重试，最终 `submit_step_result(status=handoff)` 成功。
- 事件流最后包含 `run.output.completed` 和 `run.succeeded`；数据库终态与 API 终态一致。
- 隔离数据库中的 `human_handoff_requests` 有 `handoff_399b0d7677584bcb / pending / session_f1cadb61db7041fb / project_delivery_plan / confirm_scope` 行；`sessions` 中同一 session 的状态为 `handoff`，`awaiting_input_json.handoff_id` 与终态结果一致。

脱敏证据：

- [`staff-run-bounded-events.sse`](g5-normal-worker-fix-20260924/staff-run-bounded-events.sse)
- [`staff-run-bounded-status-terminal.json`](g5-normal-worker-fix-20260924/staff-run-bounded-status-terminal.json)
- [`staff-run-bounded-result-terminal.json`](g5-normal-worker-fix-20260924/staff-run-bounded-result-terminal.json)

## wait / continue / handoff 边界

当前 bounded run 提供了真实 `handoff` 和正常 terminalization 证据。目录中较早的 `staff-run-initial-*` / `staff-run-continue-*` 是另一轮真实 provider 运行的 `awaiting_user -> continue_active -> completed` 记录，但它们生成于此前错误的 lexical 强制修复版本；因此本报告不把它们作为当前 configured-routing 修复的 PASS 证据，也不宣称已经完成当前 patch 下的持久化 reload/resume/idempotency 验收。

原始代码在本机另一次真实请求中也约 39 秒终态；因此当前 60 秒成功运行只证明 bounded 配置下该 normal-entry 可完成，不能单独证明它缩短耗时或必然消除历史 `HARNESS_STEP_TIMEOUT`。历史阻塞 trace 的最早差异仍是 `knowledge_search` started 后缺少 capability completed。

这也区分了三件事：

1. `awaiting_user` 后普通用户继续输入；
2. 当前 run 的真实 `handoff` 终态；
3. 需要额外 API/reload 证据的持久化 handoff/resume/idempotency。

## 验证

聚焦测试：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -p no:capture tests_harness/modules/test_knowledge_local.py -q
14 passed
```

新增单测覆盖：Harness v3 保留 configured route 并限制 nested timeout，生产型 dataclass snapshot 受 step deadline 限制；非 v3 和缺少 model config 时不改动原 deps。

未宣称 G5 总体 PASS：PilotDeck native path 尚无真实非 mock 通过证据，当前报告也没有把旧 lexical 运行或普通 `awaiting_user` continuation 冒充为当前 patch 的持久化 handoff/resume 证据。
