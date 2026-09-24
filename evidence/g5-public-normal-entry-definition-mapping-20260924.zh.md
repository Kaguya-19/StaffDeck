# G5 public normal-entry 定义映射记录

日期：2026-09-24
范围：只对既有真实 normal-entry/public-version 结果与既有 formal UI page-published 结果做证据映射；不重跑场景，不修改 acceptance tree。

## 结论

1. `project_delivery_plan@1.0.1` 和 `project_delivery_plan@1.0.2` 的真实 public-version normal-entry 链路有直接证据：公共发布/发现、PilotDeck normal entry、版本绑定、旧 session snapshot、wait/resume/replay 和新 session 的当前版本选择均已记录。
2. 旧的 formal UI page-published 链路也有独立证据：PilotDeck `1.3.1` 与 StaffDeck `1.3.0` 均保存了页面发布对象，并有对应 runtime 的 handoff、reload、resume、duplicate replay 和 `finalize_plan` 完成记录。
3. 两组证据不是同一条定义/版本 lineage。旧 UI 对象使用 `n2_plan`，而当前 public normal-entry `1.0.1/1.0.2` 使用 `build_plan`；旧 UI 的 `confirm_scope.allowed_actions` 为 `continue_flow`，当前 public 对象为 `handoff_human`。因此不能把旧 UI 运行结果改写成当前 `1.0.1/1.0.2` 的 page-editor-to-normal-entry 同定义证明。
4. 历史“准备 `1.0.1`”的完整 draft request/response 与 draft ID 未保存。`published-project-delivery-plan-1.0.1.json` 能证明导出的对象内容，不能补证明当时的创建/发布事务；本文不重构该缺失记录。

## 固定输入

| 组件 | 固定 worktree | fixed ref |
|---|---|---|
| PilotDeck | `/Users/a1/Documents/Codex/2026-09-23/pilotdeck-g5-independent-final-20260923` | `fe2f7cbdbd47edf523ad15200ff991ce2343427d` |
| StaffDeck | `/Users/a1/Documents/Codex/2026-09-23/staffdeck-g5-independent-final-20260923` | `85ac9ae5020f82795243ff313ea61ebc5d49104a` |

当前真实模型记录为 `provider1/qwen3.6-flash-distill`；凭据已脱敏。当前 normal-entry 输入契约是普通项目交付请求，不含 SOP 工具或 result-status 指令。

## 定义与运行证据矩阵

| 对象/版本 | 定义来源 | 节点与动作 | 边/条件 | runtime 绑定证据 | 同定义桥接结论 |
|---|---|---|---|---|---|
| Public normal-entry `project_delivery_plan@1.0.1` | [`published-project-delivery-plan-1.0.1.json`](/Users/a1/Documents/Codex/2026-09-23/g5-independent-final-20260923-real/published-project-delivery-plan-1.0.1.json)；结果汇总 [`pilotdeck-real-public-version-natural.json`](/Users/a1/Documents/Codex/2026-09-23/g5-independent-final-20260923-real/pilotdeck-real-public-version-natural.json) | `n1_collect: collect_info/extract_slots`; `build_plan: response/answer_user`; `confirm_scope: handoff/handoff_human`; `finalize_plan: response/continue_flow` | `n1_collect -> build_plan (default)`；`build_plan -> confirm_scope (scope_changed)`；`build_plan -> finalize_plan (no_scope_change)`；`confirm_scope -> finalize_plan (confirmation_received)` | 旧 session 首轮及 reload 后仍绑定 `1.0.1`，持久化 wait ID `11480898-1967-4126-9286-5098e1453254`；resume 接受、重复 replay 去重，最终 `finalize_plan/completed`。 | **已证明 public normal-entry 使用该定义**；但历史 1.0.1 创建/发布事务记录缺失。 |
| Public normal-entry `project_delivery_plan@1.0.2` | [`published-project-delivery-plan-1.0.2.json`](/Users/a1/Documents/Codex/2026-09-23/g5-independent-final-20260923-real/published-project-delivery-plan-1.0.2.json)；发布元数据在 [`pilotdeck-real-public-version-natural.json`](/Users/a1/Documents/Codex/2026-09-23/g5-independent-final-20260923-real/pilotdeck-real-public-version-natural.json)（draft `sopdraft_d156f8c39470416a`） | `n1_collect: collect_info/extract_slots`; `build_plan: response/answer_user`; `confirm_scope: handoff/handoff_human`; `finalize_plan: response/continue_flow` | 与 1.0.1 相同四条条件边 | 新 session 绑定 `1.0.2`，真实 provider 运行到 `build_plan`，以合法 `awaiting_user` 结束并保留待确认项。 | **已证明 public normal-entry 使用该定义**。 |
| Formal UI page-published PilotDeck `1.3.1` | [`pilotdeck-fixed-page-published-1.3.1.json`](/Users/a1/Documents/Codex/2026-09-22/g5-independent-final/pilotdeck-fixed-page-published-1.3.1.json) | `n1_collect`、`n2_plan`、`confirm_scope`、`finalize_plan`；`n2_plan` 为 `response/answer_user`；旧对象的 `confirm_scope` 动作为 `continue_flow` | `n1_collect -> n2_plan (default)`；`n2_plan -> confirm_scope (scope_changed)`；`n2_plan -> finalize_plan (no_scope_change)`；`confirm_scope -> finalize_plan (confirmation_received)` | [`pilotdeck-runtime-1.3.1.json`](/Users/a1/Documents/Codex/2026-09-22/g5-independent-final/pilotdeck-runtime-1.3.1.json)：handoff、same wait ID after reload、一次 resume、duplicate replay、`finalize_plan/completed`。 | **仅证明旧 UI 定义的独立页面发布/runtime 链路**；未证明它等于当前 1.0.x。 |
| Formal UI page-published StaffDeck `1.3.0` | [`staffdeck-fixed-page-published-1.3.0.json`](/Users/a1/Documents/Codex/2026-09-22/g5-independent-final/staffdeck-fixed-page-published-1.3.0.json) | `n1_collect: collect_info/extract_slots`; `n2_plan: response/answer_user`; `confirm_scope: handoff/continue_flow`; `finalize_plan: response/continue_flow` | `n1_collect -> n2_plan (default)`；`n2_plan -> confirm_scope (scope_changed)`；`n2_plan -> finalize_plan (no_scope_change)`；`confirm_scope -> finalize_plan (confirmation_received)` | [`staffdeck-runtime-1.3.0.json`](/Users/a1/Documents/Codex/2026-09-22/g5-independent-final/staffdeck-runtime-1.3.0.json)：handoff、same wait ID after reload、一次 resume、duplicate replay、`finalize_plan/completed`。 | **仅证明旧 UI 定义的独立页面发布/runtime 链路**；未证明它等于当前 1.0.x。 |

## 当前 public normal-entry 链路中已直接观察到的版本关系

- 结果文件的 `fixedRefs` 明确记录了本次 PilotDeck/StaffDeck fixed refs，provider 为真实 `provider1/qwen3.6-flash-distill`。
- `1.0.2` 的发布元数据保留 draft ID `sopdraft_d156f8c39470416a` 和公开版本 `1.0.2`。
- 旧 session 在版本切换后仍绑定 `project_delivery_plan@1.0.1`，同一 wait ID 在 gateway dispose/recreate 后仍可恢复；重复 resume 被去重。
- 新 session 绑定 `project_delivery_plan@1.0.2`，停在 `build_plan` 的合法 `awaiting_user` 状态。这不是 `finalize_plan` 完成，也不应被报告为失败。

这些事实建立的是当前 public normal-entry 的版本选择与 snapshot 语义，不会自动把旧 UI page-published 对象追溯成同一个定义。

## 不能声称的内容

- 不能把 `1.3.0/1.3.1` 的页面编辑器发布记录当作 `1.0.1/1.0.2` 的页面编辑器发布记录。
- 不能仅凭相同 `skill_id`、相同四条条件语义或相同终态节点，声称两条链路使用了同一 graph definition；节点 ID 和 action 字段已经不同。
- 不能从现有 `1.0.1` 导出 JSON 反推缺失的历史 draft ID、创建请求、发布响应或当时的 discovery 响应。

## 最小后续桥接证据（建议，不在本记录中执行）

要证明“formal UI 发布对象 -> public discovery/normal entry”是同一定义，应从**同一个** formal UI published object 开始，并保存：

1. 页面发布返回体/导出对象的脱敏原文，含 skill ID、版本、节点、边和 action 字段。
2. 将该精确对象通过 public discovery 输入，记录 discovery 选择结果和 bound version。
3. 记录 normal-entry session 的 binding、graph 关键字段（至少节点 ID、类型、actions、边条件）及运行 trace。
4. 对照证明页面对象、discovery 结果、session snapshot 三者字段一致；再单独记录 wait/resume/replay。

该桥接必须使用真实固定实现和普通业务请求，不注入 bundle、不伪造 client、不改写 graph、不手写 session state。

## 证据边界

本文只新增本 evidence 文件；未改动 acceptance tree、其他活动树或共享报告，也未重跑已通过场景。
