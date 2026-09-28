# 9月28日最小链路：SD Knowledge 导入消费 PD 文件 Port

基线 SD `b33f37ce`；本批改 `backend/app/public_api/pilotdeck_domain_host.py`、`resources.py`、`backend/app/knowledge/service.py` 及聚焦测试。固定提交见本文件所在提交；与原审批 router 增量分开，保留其测试/首失败 raw。

公开导入在原 `execute_knowledge_ingest` 调用原 KB/文档 PEP、原 APIJob credential 复核及 `_job_actor` 后，把固定 agent 和真实 actor 标入本次原 KnowledgeIngestJob 的 metadata。worker 的原 `parsing` 阶段遇此来源调用 `PilotDeckDomainHostClient.file_parse`，用当前原 job tenant、由原认证生成的 creator actor、固定 agent 和原文件字节经 PD `/api/module-host/call` 解析。`created_by_user_id` 必须与来源 actor 一致。随后沿原 normalizing/document/bucket/chunk/terminal/事件状态机继续。原生 SD 导入仍按原 parser；公开导入若未绑定 PD client、PD 返回错误或文件格式不支持则原任务失败，不回退 SD parser/伪成功，不造第二任务。

`PilotDeckDomainHostClient(origin, bridge_token, pilotdeck_user_id, transport?)` 为纯服务端绑定；token 为部署端已有 PD Gateway 服务凭据，pilotdeck_user_id 必须是该固定部署的真实已认证 PD 用户 ID，不能拿 SD actor/账户 key 冒充。`bind_pilotdeck_domain_host(client)` 需由整合者在 SD 应用启动时、开放导入前显式调用；配置失败不应开放有限版导入。整合应以实际 enabled profile 的 Gateway origin/token/PD user 及固定 tenant/target 验证连接。此客户端从原 `PublicPrincipal`/`_job_actor` 派生 tenant/actor/agent，不能接受浏览器自填的 PD principal。未新增 scope/PEP/DB 字段。没有可验证的 PD 用户配置或正确服务凭据时保持阻塞，不填 placeholder。

原 multipart -> APIJob202 -> 原 KnowledgeIngestJob -> events/terminal 仍保留。PD `file_parse` 仅抽文本，没有任务状态；Bash task 不映成 ingest。本批未把 SD 的可选 LLMClient 映为 PD ModelInvoker：有限 profile 不得在 Knowledge ingress/search 路径配置第二 SD 模型；正常 PD 对话从已绑定的 PD 模型和 Knowledge 检索获取引用，实际路径须由整合/独立验收记录。若真实路径触发 SD LLMClient，则此项仍 FAIL，需补该具体领域 callback，不能声称 DI 完毕。SOP 正常无审批分支依 PD 原 AgentLoop/发布 bundle；审批映射延期，未装配时显错禁提交。

聚焦测试 `test_public_pilotdeck_domain_host.py` 3/3，连同原审批消费者共17/17。覆盖服务 Bearer 与原 job 身份字段、PD 回应、缺绑定时不回退、原生路径保留、缺身份与上游415。Python compileall 和 diff check 通过。生产 root/client binding、effective profile、入库运行、模型引用、SOP 完成均 NOT RUN；无 G gate 或有限版 PASS 主张。
