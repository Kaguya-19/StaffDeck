# 审批 native User 消费兼容增量

本批基于 SD `56c6fb60d9042fbfa3ca86c79ad6ea576f0725da`，保留原审批集中任务。固定 commit 为包含本文的提交；整合仅接以下两文件增量及本文，不覆盖 root/HTTP/RPC/adapter：

- `backend/app/public_api/pilotdeck_approvals.py`
- `backend/tests/test_public_pilotdeck_approvals.py`

## 准确处置

移除对真实 native `User` 不存在的 `disabled` 属性访问。native 模式继续使用原 `get_current_user` 验证 Bearer、持久 User 及 token tenant；router 核固定 tenant、source=web、admin/member。未新增 User/core 字段，也未以属性默认值生成外部成员事实。

external 模式调用现有 `identity_directory.resolve_members`，以配置 control provider 的权威目录解析登录主体。目录不可用/无效维持原 503；主体缺失、disabled 或 source/role 与登录投影不一致拒绝 403。disabled 必须是 MemberRecord 显式提供的字段，缺事实为 `MEMBER_DIRECTORY_INVALID` 503，不能用其模型默认 false 放行。原目录的 tenant/source/ID/role 验证不变；未另建身份源或 store。

两路仍通过同原 approval client 保留服务身份与正常审批 Bearer 分离、原 owner 错误/receipt；没有 pending preflight、自动 continue 或第二 wait。函数仅增加 FastAPI `get_session` 依赖，与原认证共享 session；HTTP DTO/export 无变更。

## 聚焦自验

在本隔离树执行：

```sh
PYTHONPATH=backend /Users/a1/Documents/Codex/2026-09-27/public-runtime-01a0e22b/staffdeck/backend/.venv/bin/python -m pytest -q backend/tests/test_public_pilotdeck_approvals.py
```

结果 14 passed。新增检查以真实 native User（明确无 disabled 属性）、原 get_current_user 和正常 token 验证 status/reply 消费；覆盖 tenant/source/role/缺 Bearer 拒绝、external 显式 enabled/disabled/缺事实/角色不一致及目录不可用。external 测试只替换已认证 User 依赖，不声称外部认证生产连通。`git diff --check` 通过。

原整合首 AttributeError raw 未删除/覆盖。本批仅消费者兼容验证，不是业务或外部运行、完整 candidate 或 G gate PASS。19 项 provider/DI/profile 与实际审批/continue/newold pin 仍保持未闭合状态，本增量不替代这些交付。
