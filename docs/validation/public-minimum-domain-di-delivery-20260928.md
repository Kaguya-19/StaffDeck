# 9月28日最小链路：SD Knowledge 导入消费 PD 文件 Port

基线 SD `b33f37ce`；本批改 `backend/app/public_api/pilotdeck_domain_host.py`、`resources.py`、`backend/app/knowledge/service.py` 及聚焦测试；后续同批窄增量增加 `backend/app/knowledge/public_host_selection.py` 与 `backend/app/api/knowledge.py` 内部模型选择守卫。固定提交见本文件所在提交；与原审批 router 增量分开，保留其测试/首失败 raw。

公开导入在原 `execute_knowledge_ingest` 调用原 KB/文档 PEP、原 APIJob credential 复核及 `_job_actor` 后，把固定 agent 和真实 actor 标入本次原 KnowledgeIngestJob 的 metadata。worker 的原 `parsing` 阶段遇此来源调用 `PilotDeckDomainHostClient.file_parse`，用当前原 job tenant、由原认证生成的 creator actor、固定 agent 和原文件字节经 PD `/api/module-host/call` 解析。`created_by_user_id` 必须与来源 actor 一致。随后沿原 normalizing/document/bucket/chunk/terminal/事件状态机继续。原生 SD 导入仍按原 parser；公开导入若未绑定 PD client、PD 返回错误或文件格式不支持则原任务失败，不回退 SD parser/伪成功，不造第二任务。

`PilotDeckDomainHostClient(origin, bridge_token, pilotdeck_user_id, transport?)` 为纯服务端绑定；token 为部署端已有 PD Gateway 服务凭据，pilotdeck_user_id 必须是该固定部署的真实已认证 PD 用户 ID，不能拿 SD actor/账户 key 冒充。`bind_pilotdeck_domain_host(client)` 需由整合者在 SD 应用启动时、开放导入前显式调用；配置失败不应开放有限版导入。整合应以实际 enabled profile 的 Gateway origin/token/PD user 及固定 tenant/target 验证连接。此客户端从原 `PublicPrincipal`/`_job_actor` 派生 tenant/actor/agent，不能接受浏览器自填的 PD principal。未新增 scope/PEP/DB 字段。没有可验证的 PD 用户配置或正确服务凭据时保持阻塞，不填 placeholder。

原 multipart -> APIJob202 -> 原 KnowledgeIngestJob -> events/terminal 仍保留。PD `file_parse` 仅抽文本，没有任务状态；Bash task 不映成 ingest。公开 Knowledge 导入的 service 实例在原 worker 内读入来源标记，内部 bucket/discovery 不查询或使用 SD 默认模型；公开 Knowledge search 在原 native PEP/版本可见性链中以 request-local 选择禁用 SD 模型路由，显式 SD model_config_id 被拒绝。原生 SD 导入和搜索保持原模型语义。有限路径因此使用 Knowledge 原词法检索及引用数据，正常 PD 对话由已绑定的 PD ModelInvoker 完成回答；实际模型调用与引用必须独立验收。PD 模型回调不被伪装为 SD LLMClient，若其他最小流程仍触发 SD LLMClient，则该流程仍 FAIL。SOP 正常无审批分支依 PD 原 AgentLoop/发布 bundle；审批映射延期，未装配时显错禁提交。

聚焦测试 `test_public_pilotdeck_domain_host.py` 5/5，连同原审批消费者共19/19。覆盖服务 Bearer 与原 job 身份字段、PD 回应、缺绑定时不回退、原生路径保留、缺身份与上游415。Python compileall 和 diff check 通过。生产 root/client binding、effective profile、入库运行、模型引用、SOP 完成均 NOT RUN；无 G gate 或有限版 PASS 主张。
