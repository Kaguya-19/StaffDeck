# UI 审批呈现固定交付（2026-09-28）

唯一 ownership 按 `/Users/a1/Documents/Codex/2026-09-27/g0-g6-integration-intake/APPROVAL_OWNER_HANDOFF_20260928.md`。本 UI 提交从已交 SD `4f918aa5`、PD `904d132d` 接续；不碰 public domain/router、adapter browser façade、整合 root/canonical 分发、他线 dirty。

## 已实现

- canonical `packages/staffdeck-business-ui/src/FormalSopApprovalInbox.tsx`：纯呈现。只接 adapter 注入的 `{status: StaffDeckSopStatusSnapshot|null, loading, submitting, error, onReply}`；需要 `status.approval` 的原 `waitId/revision/skillId/version/nodeId/assigneeUserId`，不从 current/latest/default 查 assignee 或建立本地 wait。仅暂存未提交的 textarea 文本；wait/session/revision 变化清空。按钮提交时只调用 `onReply(approval, trimmedMessage)`，requestId、已认证 resume、receipt、错误与幂等全部归 adapter。缺审批、`approvalError` 或非法 revision 时不发命令。
- SD native 入口 `frontend-enterprise/src/pages/chat/components/ChatDialogs.tsx` 增加可选 `pilotDeckApprovalInbox?: ReactNode` 呈现插槽，位于原“待回答”Dialog 中原 native handoff 列表之后。未改 native handoffs/filter/replies/count/权限；无注入时原行为完全相同。
- native reexport、SD/PD source-string catalog 五个新增可见标签。pinned skill/version/node 当用户内容；产品标签双语。

## 固定消费合同与两宿主挂载点

原公共 Gateway status 返回 `{status: StaffDeckSopStatusSnapshot|null}`，其中 pinned `approval` 来自原 session 持久化 bundle。resume POST 需要 scope、`source:'human'`、`requestId`、`waitId`、`expectedRevision`、`message`，返回原 resume receipt。UI 只接受 adapter **解包后且已认证**的 status，不能 browser 直传 caller authority/subject 或自行调用 gateway/token。

| 宿主原入口 | 精确呈现 hunk / adapter 输入 | owner |
|---|---|---|
| SD `ChatPage.tsx` 与 `ChatGalleryPage.tsx` 的 `<ChatDialogs chat={chat} />` | 由 SD adapter 提供当前认证会话的 `approvalInbox: ReactNode`，变为 `<ChatDialogs chat={chat} pilotDeckApprovalInbox={approvalInbox} />`。adapter 负责原 admission sessionKey 映射、正常 approver login、status/错误/提交/刷新；不能从 `chat.sessionId` 或 `ExternalSessionBinding.external_session_id` 推 PD sessionKey。native handoff 保持独立。 | adapter/context 供 consumer；整合/原 root owner 注入；UI 插槽已实现 |
| PD `ui/src/composition/modules/staffdeck-sop.tsx` 的 `SopExtension` → `SopWaitBanner` | adapter 在原 extension session/project binding 提供已认证 `approval` snapshot 与 reply consumer，human wait 渲染 canonical `FormalSopApprovalInbox`（由整合单源分发）并从原 `SopWaitBanner` 的 human resume 路径退出；`external_task` 原 banner/行为保留。不得用 wait.kind + 本地随机 requestId 直接 human resume 绕过独立 approver 登录；缺映射显示真实错误/不可操作。 | adapter/context 提供 façade；整合入口/单源 vendor；UI canonical 已实现 |

这两条是需原 owner 应用的**精确入口 hunk**，不是授权 UI 修改 adapter、Gateway、PD chat state 或复制 native handoff。当前 SD `ChatDialogs` 插槽没有 consumer 注入、PD extension 也尚未替换；本提交不宣称两个入口已运行闭合。尤其 public handoff 所列生产跨 Host session 映射仍 503，UI 不以静态 sample 或本地 ID 填补。整合应同时接 canonical 文件与 PD vendor 单源副本，不允许自建第二呈现组件。

## 聚焦证据与限制

`/Users/a1/Documents/Codex/2026-09-27/ui-owner-01a0e22b/evidence/ui-formal-approval-inbox.log`：3/3 jsdom，验证 pinned DTO 原对象回调、无审批/错误/非法 revision 禁提交、wait 切换清空输入、EN/ZH 产品标签与用户值边界。`git diff --check` 和两 JSON 解析通过。没有外部认证/跨 Host 映射/真实审批运行；唯一矩阵相应行仍 NOT RUN，不能以 UI 测试签 gate。

延期目标仍 2026-09-28 Asia/Shanghai；员工/team 排除与已批准公开 SDK 白名单、`sops:cancel` 继续有效。无 push/merge/部署/归档、新轮次或第二审批 state。
