# SD 正常 Harness turn 使用 PD 模型公共 Port

源基线 `23d9319d2a813dd8b5d2e68b2165da253fd893ce`。本提交在 SD 的认证固定 PD domain binding 下选择唯一 PD catalog 默认模型，并通过现有 `model_stream` 完成正常 chat、Knowledge 对话和 SOP turn 的原 Harness 请求。`PilotDeckHarnessModel` 仅为本轮非持久选模值；没有 SD `ModelConfig`、第二 provider 或失败自动回退。Gateway 仍持固定 tenant/actor/agent/PD user 与服务凭据，`engine_host` 仍先通过原 `resolve_staff` 进行 staff.use/PEP，Knowledge 与 SOP 使用原领域状态和可见性规则。

`pilotdeck_harness_model.select_harness_model(context, model_id)` 接受已授权 `SourceContext` 与可选显式 PD model ID，拒绝固定身份不匹配/目录无匹配。`stream_model_events(selection, canonical_request)` 调认证 `/api/module-host/call` 的 `model_stream` 并校验 NDJSON。`pilotdeck_model_wire.canonical_request/openai_chunks` 映射 Harness OpenAI wire 与 PD canonical messages/tools/events；无法同语义表示的输入显式 400。`timeout_seconds` 是 SD 本地 HTTP 等待，只作内部 `dataclasses.replace` 派生值，不进入 PD 选模或 canonical payload。Memory JSON 与 Knowledge 原文档/索引模型路由调用同一公开 PD Port；域内 PEP、原路由失败处理未改。

不要求整合修改 `modules.js`、浏览器 adapter 或 PD core；这组 SD hunk 可直接整合。运行方需沿既有正式 startup 将 `PILOTDECK_DOMAIN_HOST_ENABLED=true`、固定身份 tuple、Gateway URL/token path 与 PD user 绑定；未绑定及不匹配均显错。PD Gateway 必须公开 `list_model_catalog`、`model_stream`，不需要新增 scope。账户 secret 仅留在服务端启动输入。

聚焦检查：`backend/tests_harness/test_model_gateway.py` 与 `test_pilotdeck_harness_model.py` 共 16 passed；修改文件 `compileall`、`git diff --check` 通过。隔离运行的完整 raw、request ID、进程输入和逐条结果见 [HARNESS_PD_MODEL_DEBUG_DELIVERY.md](/Users/a1/Documents/Codex/2026-09-28/public-harness-model-debug-1/HARNESS_PD_MODEL_DEBUG_DELIVERY.md)。B4 首失败原件保持原样。

隔离运行在既有配置下取得正常 chat、Knowledge 唯一事实及文档引用、无审批 SOP 终态与持久回读；切换用户指定 `/tmp/codex-minimum-model-test-20260928/credentials.json` 后，认证 PD catalog 仍可读，两个正常 turn 的模型流在上游 incomplete chunk 处失败，raw 保留。该测试凭据 profile 下不可记业务 PASS，不能据此归因于密钥、网络或模型服务任一单项；无换 key、降级或 fallback。初始配置下的结果也不替代指定凭据下的结果。
