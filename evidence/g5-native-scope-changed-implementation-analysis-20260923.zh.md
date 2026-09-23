# G5 scope-changed 实现侧自验记录

日期：2026-09-23

本文件是实现侧证据，不是独立验收报告，也不把真实 provider 的 handoff/resume 记为 PASS。

## 固定路径与 refs

- 实现任务树：`/Users/a1/Desktop/claw/openbmb/StaffDeck-g5-sop-agent`
- 迁移前基线：`5e07316ad7f1703683d62ed06bb9b69a64e31810`
- 最终实现 ref：以本文件入库提交后的 `git rev-parse HEAD` 为准
- PilotDeck 依赖 ref：`fe2f7cbdbd47edf523ad15200ff991ce2343427d`

此前误写过的验收/共用路径（本轮不再写入）：

- `/Users/a1/Documents/Codex/2026-09-23/staffdeck-g5-runtime-fixed-5e07316a`
  - 曾写入 `evidence/g5-native-scope-changed-glue-analysis-20260923.zh.md`
  - 该树当前 HEAD 为 `98e52434552c1c205df2aedfb048e0e7e86e9c40`，本轮不修改、不 reset、不清理
- `/Users/a1/Documents/Codex/2026-09-23/g5-runtime-independent-fe2f7cbd`
  - 曾写入 `native-scope-changed-fixed-glue.json`
  - 曾写入 `native-scope-changed-fixed-glue-v2.json`
  - 原始 `native-scope-changed-independent.json` 保持只读

## 实现变更

1. `submit_step_result` 接受后，`session_runner` 不再等待 Harness `session.status=idle` 才返回。
2. 若接受控制时 Harness 尚未 idle，结束本 phase 并关闭该忙进程，不把 stale continuation 放回 warm pool。
3. `_step_prompt` 传递当前已发布 SOP 节点的 `type`、`allowed_actions` 等原生上下文。节点声明 `handoff_human` 时，提示明确要求通过真实 `submit_step_result(status="handoff")`，而不是把人工确认误报为 `awaiting_user`。
4. 没有修改 SOP 图、转移白名单、审批规则、用户输入或 AgentLoop 核心语义。

Completion 契约由测试覆盖：接受控制前已收到的 Harness 事件保留；接受控制后且尚未 idle 的进程不可复用；handoff control 自身是一个被验证并提交的 SOP 结果。

## 自验结果

可重复 runner：`tools/g5-native-scope-changed-self-check.py`

生成证据：`evidence/g5-native-scope-changed-self-check.json`

- bridge/completion focused：`53 passed`
- SOP/handoff/lifecycle/source-boundary：`38 passed`
- portable SOP 全集：`53 passed`
- deterministic parity handoff 场景：`BLOCKED`，本任务树缺少 Harness `apps/cli/lib/bin.js` 与 PilotDeck sidecar `dist`；未将阻塞转成 PASS

原始真实 provider 失败和后续 v2 artifact 只作为只读 provenance，完整路径记录在 self-check JSON；scope-changed handoff/resume 仍需独立验收者从新隔离树复验。
