# Provider evidence provenance

以下 JSON 是从验收树只读复制到实现任务树的证据快照，未在源路径修改或覆盖：

- `native-scope-changed-independent.json`：原始 `HARNESS_STEP_TIMEOUT` 失败
- `native-scope-changed-fixed-glue.json`：首次 glue 修复后 handoff 持久化、resume 暴露 stale pooled-process timeout
- `native-scope-changed-fixed-glue-v2.json`：无 timeout，但 provider 在 `confirm_scope` 直接提交 `awaiting_user`，没有形成 `HumanHandoffRequest`

这些是实现侧 provenance，不是独立验收结果。后续独立验收必须从新的隔离树，以普通输入重新运行并单独判断 handoff/resume。
