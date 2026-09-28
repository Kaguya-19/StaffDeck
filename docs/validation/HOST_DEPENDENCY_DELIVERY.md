# HOST_DEPENDENCY_DELIVERY

目标交付日：2026-09-28（Asia/Shanghai）。本表沿 `DELIVERY_PLAN_20260928.md` 和既有 `SDK_OWNER_HANDOFF` ownership 接续；不重开轮次，不替代 `FIXED_012_CONSOLIDATED_AUDIT.md`，也不把未运行项目标为 PASS。

## 当日最小链路窄核（用户已接受范围例外）

按 `DELIVERY_SCOPE_OPTION_20260928.md`，今天只要求双宿主正式 Knowledge 单文档导入/读取/查询及模型引用，和正式 SOP 无审批分支的编辑/保存/校验/发布/正常运行。审批真实等待、复杂图/管理、全双语/双主题与模块排列保原状态，不作为今天的 UI 首修范围。下表仅核已提交源码入口，**不是**浏览器业务 PASS。

| 宿主/必要页面 | 已提交正式消费链 | 首轮 UI 处置 | 尚需同一候选运行证明 |
|---|---|---|---|
| SD Knowledge | `App.tsx` `/enterprise/knowledge`、`/enterprise/knowledge/new` → `pages/KnowledgePage.tsx` → `@staffdeck/business-ui/KnowledgePage` + `KnowledgePageHostProvider` → `business-ui/knowledge-host.tsx` 原组件、Markdown、notify/nav/API | 原 shared 页面、导入 Dialog、表格、查询和引用呈现均有正式入口；不新增 UI hunk | 真实正常身份、单文档入库状态/刷新/查询、模型引用及页面 AX/DOM |
| PD Knowledge | `staffdeck-knowledge.tsx` `/knowledge`、`/knowledge/new` → vendored 同源 `KnowledgePage` → `PilotDeckKnowledgePageProvider` + `StaffDeckHostBinding`；Host map 用正式 primitive、图谱/Markdown、导入和分页 | 既有 `host-presentation-integration` 覆盖进度/Scope/分页原 props；无本轮新增组件注册 | enabled profile 实际路由可见、Host Port/adapter/身份、导入/查询/引用及 vendor 同源版本 |
| SD SOP | `App.tsx` `/enterprise/skills` → `pages/SkillsPage.tsx` → `@staffdeck/business-ui/SkillsPage` + `SkillsPageHostProvider`；编辑器经原 `DistillPage`/Host | 已有真实 draft row 选择与 selected `draft_id` publish hunk；保 ETag/dirty/原校验与版本动作 | 真实编辑、保存、校验、发布、无审批正常触发与终态回读 |
| PD SOP | `staffdeck-sop.tsx` `/sop`、`/sop/distill` → vendored 同源 `SkillsPage`/`DistillPage` → `PilotDeckSkillsPageProvider`/`PilotDeckDistillPageProvider` + `StaffDeckHostBinding`/`PublishRuntimeProvider` | 既有 formal Dialog/Dropdown/ActionCombobox/graph 和 notify/nav slot；本轮无独立呈现差异可改；human 审批 mount 保留但延期真实运行 | enabled profile 真实路由、原 draft/ETag、公共 Port/身份、无审批分支正常运行及同源版本 |

以上是当前整合已提交入口的窄源码核对；公开 adapter、root、vendor/lock 和最终 cleanpair 仍由各唯一 owner 处理。不能从本表或局部 jsdom 推断“可见、可操作、同源消费”已在新候选通过。首轮若出现具体 AX/DOM/样式差异，UI 只对该差异交窄修复，不为延期项扩全矩阵。

UI 固定输入：SD `7bbdbdb6e68d165d993382471842b39399aca663`、PD `904d132d9bf57a31497230bcc2644d6b6d2cd1d3`。这两项既有交付继续有效，本表只补依赖闭合与复用边界。

## 前端复用表

| 页面/调用 | 原 UI 需要 | PilotDeck/shared 复用点 | 处理 | owner / 证据 |
|---|---|---|---|---|
| Knowledge 列表、导入、详情 | Dialog、Content/Title/Footer、Select、Dropdown、Accordion、Input/Textarea、Button、分页、Status/Detail、Portal 与受控关闭 | `KnowledgePageHost.tsx` 的 `components`/`icons` 注入；PD `pilotDeckFormalComponents` 和 `FormalHostPrimitiveProvider` | 直接复用 formal primitive；Dialog 的 `Escape`、Close、Portal、ref 语义沿既有提交 | UI；`formal-primitive-contract`、`formal-overlay-contract` |
| Knowledge 图谱与引用 | 主 graph renderer/model、节点详情、Markdown blocks、图谱用户文本边界 | `KnowledgeGraphVisualization`、`renderMarkdownBlocks` Host slot；PD `FormalKnowledgeGraphVisualization`/`FormalMarkdown` | 复用 canonical renderer 和 block renderer；不以 canvas/空 div 或 span fallback 代替；用户节点名、tag、Markdown 正文保持 ignore | UI；`ui-graph-content.patch`、graph boundary evidence |
| Skills 列表、版本、导入/发布菜单 | Dropdown/Confirm/Dialog、DataTable、ResourceImportDialog、selected row draft query、scope/navigation/notify | `SkillsPageHost.tsx` 的 component map；PD `PilotDeckDataTable`、`PilotDeckResourceImportDialog`、formal Dialog/Dropdown | 复用已交真实 draft row；publish 只追加选中 `row.draft_id`；不从 latest list 猜 draft，不自动 publish | UI + adapter；`33238719`、`e56bcdf3c`、selected-draft evidence |
| Distill 编辑器与 graph | Input/Textarea、Popover、Tooltip、Select、Dialog、ActionCombobox、stream、warning/info/success/error、scope/nav | `DistillPageHost.tsx` 的 API/stream/notify/nav/context 接口；PD `pilotDeckFormalComponents` | UI 只消费 Host 合同；ActionCombobox 使用正式 Popover，保 `type=text`、autofocus、Enter、Escape；API/context 由 adapter 提供 | UI；`7bbdbdb6`、`904d132d`、action-picker evidence |
| 三页双语与 Portal | 可见产品 label、aria/title 模板、Portal root、用户文本边界 | SD native i18n boundary；PD `StaffDeckLocaleBoundary` + `[data-staffdeck-portal-root]` | 模板 capture 中用户 slot 原样插入；`data-i18n-ignore` 保护正文；`data-i18n-ignore-title` 只保护用户 title，不屏蔽邻近产品 label | UI；dynamic/mixed-title evidence |
| Notify / navigation | `success/warning/error[/info]`、navigate、tenant、scope read | 各 `*PageHost` provider 的纯函数接口；PD `pilotDeckNotify` 仅映射 toast 事件 | 直接调用现有 Host；不复制 global store，不把 API/context 实现搬进 shared JSX；错误投影、账户/团队 scope 由 adapter 保持 | adapter owner；UI 仅消费，不新增协议 |

## 三页 Host 合同与 owner 边界

| Host | UI 可依赖的正式接口 | 交 adapter 的协议 | 当前状态 |
|---|---|---|---|
| `KnowledgePageHost` | `components/icons`、`renderMarkdownBlocks`、`getDateLocale`、`navigate`、`notify`、`agentScope` | `api` 的路径/query/body/ETag、employee/team visibility、tenant/actor/context | UI 接线已存在；深层 API、multipart、全文、bucket/chunk、concept/job 由 adapter/public owner 按计划继续闭合 |
| `SkillsPageHost` | formal DataTable/Import/Dialog/Dropdown、`editorQuery`、scope/nav/notify | SOP list/detail/create/replace/publish、真实 draft/ETag/dirty、权限/target | selected draft publish 已固定；其余管理 API 继续由 adapter 维护，UI 不重写 |
| `DistillPageHost` | formal primitive/icon map、`render`/layout、纯 action picker、scope/nav/notify 消费 | `api`、`streamGet/streamPost`、Abort/error、tenant/context、SSE/ETag | UI 只消费已有协议；真实 SSE、业务错误投影与 context 语义不在本提交新增 |

Host providers 必须保持原 owner、ETag、dirty/cache、controlledClose、Escape preventDefault、tenant 与 scope namespace。`activeHost` 只作为现有页面模块的桥接实现，不能被扩成 global store 或跨页面共享业务状态。

## PD 正式复用清单

`ui/src/composition/modules/staffdeck/vendor/formal-primitives/index.ts` 已导出 Accordion、Select、DropdownMenu、Popover、Tooltip、Checkbox、Progress、Input、Textarea、AlertDialog、Pagination、Switch、UIButton。`host-components.tsx` 以同一 `primitives` map 包装 `ConfirmDialog`、`Paginator`、`CapabilityScopeControl`、`ModelConfigDropdown` 和 `KnowledgeGraphVisualization`，三正式 Host 使用同一 map：

- Knowledge：`knowledge-host-adapter.tsx` 的 `components` spread，另覆写 DataTable/ResourceImportDialog；
- Skills：`skills-host-adapter.tsx` 的 `components` spread，另覆写 DataTable/ResourceImportDialog；
- Distill：`createPilotDeckDistillPageHost` 的 `components: pilotDeckFormalComponents`。

本批没有新的组件注册 key 或 adapter hunk。上述接线是已交 PD 固定树中的既有合同；整合者同步 canonical/vendor 时必须保留同一 map 和两个业务 override。

## 2026-09-27 PilotDeck capability 决策增量

按 `PILOTDECK_HOST_CAPABILITY_DECISION.md`，工具/通用技能目录、模型配置与调用、文件解析/任务/事件流的能力真源改为 PilotDeck 宿主公共 Port；本 UI 线只保留页面调用形状和呈现，不新增目录、模型或任务 store。

| UI 现有 call-site | UI 保留的形状 | adapter / PD Port 责任 | 领域状态 owner |
|---|---|---|---|
| `DistillPage.tsx:818–841` capability catalog（tools、general-skills、Knowledge、SOP） | `tools/generalSkills/knowledgeBases/sopSkills` props/state 及刷新事件；SOP/Knowledge 目录仍按各自定义渲染 | tools/general-skills 的发现/读取/管理接 PD `ToolPort`/`SkillModulePort`；SOP 与 Knowledge 的领域目录不混入通用目录；schema 不等价时交窄 adapter | Tool/GeneralSkill：PD host；SOP：SOP owner；Knowledge：Knowledge owner |
| `DistillPage.tsx:851–873` model config 与 `FormalModelConfigDropdown` | `models`, selected id、local UI selection、错误/空态呈现 | PD `ModelInvokerPort` 与配置 provider 为唯一真源；adapter 映射 `model_config_id`、profile、取消/预算/错误和事件；browser 不持 key | 模型配置/调用：PD host；draft/content：SOP owner |
| `KnowledgePage.tsx:1236` 与搜索/配置 state | 既有模型选择 props 和搜索呈现 | Knowledge 的模型操作消费注入的 PD 模型能力，不另建 SD/PD UI 配置副本；原 Knowledge request/context 由 adapter 维持 | Knowledge 数据/引用：Knowledge owner；模型执行：PD host |
| `KnowledgePage.tsx:1805–1883` upload、ingest job list/status/cancel、discovery refresh | 文件名、进度、状态、取消按钮及错误呈现 | 文件解析和通用任务/事件接 PD 公共 Port；必须声明格式/大小/输出、job start/status/result/cancel、seq/cursor/恢复/终态和资源释放。`BackgroundTaskPort` 仅 Bash 后台任务，不能冒充 ingest/APIJob/preview | Knowledge job、文档/index、discovery：Knowledge owner；通用执行/事件传输：PD host |
| `DistillPage.tsx:801–810, 985–1119, 1277–1324` stream/resume/cancel | 既有 `streamGet/streamPost`、`jobId`、`lastSeq`、自然错误和取消呈现 | adapter 将文件/解析/任务/事件映射到 PD provider；保留 canonical request、seq/cursor、Abort、终态，不把 Bash task 或 preview 状态硬映成 SOP job | SOP draft/job/版本/ETag：SOP owner；宿主事件/执行：PD host |

这些 call-site 目前不需要 UI hunk：props 和 Host API 已是窄边界，UI 不直接 import `runtimePorts`/`domainPorts` 的内部实现，也不把 SD SDK 请求继续当作 PD 目录真源。adapter 必须从这些既有路径接入 PD binding，并把真实缺失合同（schema、模型 profile、文件输出、job event cursor、取消/资源释放）单独列出。不得默认第二目录、第二模型真源、自动 fallback 或双活。

AgentLoop 仍是可插拔宿主实现；页面只消费 Host callbacks/adapter 合同。SOP 与 Knowledge 保留各自版本、ETag、dirty、持久领域状态；Session/Turn/Run/Transcript 及通用能力执行归宿主。该决定不改变原页面导航、notify、scope、controlledClose、Escape 或权限边界。

## 依赖闭合处置

已闭合的 UI 依赖：formal primitive 的 ref/props/focus/keyboard/Portal、graph/Markdown 呈现、动态 Dialog title/aria 用户 slot、用户 title boundary、Dropdown/Popover/Tooltip/Accordion 实际消费者、三页 notify/nav/scope 调用入口。

交 adapter/public owner 的依赖：Knowledge 深层 API 与公开 facade、multipart/全文/图谱任务/SSE/ETag/error projection、context/actor/tenant/target 合同。UI 不复制 API client、global store 或 backend。

新决策后的交 adapter/public owner 依赖：PD Tool/Skill catalog 与 management、ModelInvokerPort/profile/事件、解析与 job/event Port。此处只确认 UI consumer mapping，不宣称这些 Port 已经在当前 UI 隔离树完成接线或通过业务验收。

只属于整合/运行验收：canonical/vendor 同源分发、锁和串行 build；三页 mounted 真实流程；真实模型、审批、SSE、浏览器 dark/light/responsive、完整 DB/auth/HOME fresh 连续链。它们仍按唯一矩阵记录，不能由本表或 jsdom 测试代签 G1–G7。

员工/team 例外、已批准公开 SDK 白名单和 `sops:cancel` 按新计划继续有效；本表不把它们重新列为权限 pending，也不扩大 scope、换 key/token、push、merge、部署或归档。
