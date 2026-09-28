# 最小链路：无 KB ID 的文件上传

本批 SDK operation 固定为 `upload_knowledge_document_auto`，账户 scope `knowledge:write`，selected scope 仍只允许固定 target agent；不新增员工/team范围。SD `POST /api/v1/agents/{agent_id}/knowledge/documents:auto-create` multipart 字段仅 `file,title?,capability_scope?`（general/sop_specific，默认general），不接受/猜测KB ID、tenant、actor或来源metadata。200 原 KnowledgeIngestJobRead；不是202/APIJob。返回的 knowledge_base_id 为这次原owner新建的KB。

复用 native upload_document 的同一 owner 实现，保持唯一名称、私有target分支/version、source_filename/created_from_document_upload、原 creator metadata 和 ingest job。enforce_public_knowledge_pep(write=True)先验target manager/原权限，原owner再次核权限。server-only `upload_document_for_public_host` 单独接已认证 principal 的来源；浏览器/native metadata 不构成该来源。worker再核 active credential、knowledge:write、tenant/actor、target PEP。内部来源只留原job内部metadata，不复制到KB/document/source，job_read过滤之；不加DB/core字段。

原 owner 是先提交KB/version、后建job/enqueue，保留其部分失败语义：enqueue或worker失败不补偿删除KB、无自动重传/新建KB、不声称原子事务。200仅为任务创建成功，后续原job失败按原状态/事件呈现。无KB ID调用不得由adapter先createKB再upload，两次写入不等价原语。

## PD gateway / adapter 精确接线（原owner应用）

PD planner输入 `{body:{filename,title?,content_base64,media_type?,capability_scope?}}`、无knowledgeBaseId，path `agents/{target}/knowledge/documents:auto-create`，shape knowledge-ingest-job。命名表加入此operation，默认授权仍空；production只显式启用已批准的具名operation。

整合modules.js：PUBLIC_FILE_OPERATIONS添加 `upload_knowledge_document_auto`；`/staffdeck-sdk/file` allowlist添加 `capability_scope`，auto不要求KB字段且不传伪KB；保file原bytes、title、media_type；`.file()`在multipart中准确追加capability_scope。现SDK auto planner会拒knowledgeBaseId、额外body字段及错误scope。signal/真实HTTP status/body/headers沿既有传输不改。

adapter：canonical无KB上传调用该具名multipart operation；200验证id/status及非空返回knowledge_base_id，不用输入KB相等检查。正常显式base上传保原operation，不改页面源码/偷换JSON/猜base。浏览器不import server helpers/secret。

聚焦证据：SD auto/native owner消费3项+domain7项+审批14项共24 passed；SDK14/14。覆盖无base、capability_scope、同native job回应、credential/PEP、内部来源不可由native请求伪造/不可落source、worker再核认证。diffcheck通过；非真实业务/有限版PASS，生产root/文件gateway接线仍由整合者应用。
