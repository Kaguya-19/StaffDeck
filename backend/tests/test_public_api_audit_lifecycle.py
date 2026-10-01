from __future__ import annotations

import pytest
from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.agents.branching import ensure_agent_skill_branch
from app.db import get_session
from app.db.models import APIAuditLog, AgentProfile, AgentSkillBranch, Skill, Tenant
from app.public_api.app import create_public_api_app


@pytest.mark.parametrize("mode,status", [("read", 200), ("commit", 200), ("http_error", 409), ("crash", 500), ("stream", 200)])
@pytest.mark.parametrize("audit_fails", [False, True])
def test_audit_waits_for_route_session_cleanup(tmp_path, monkeypatch, mode, status, audit_fails):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'audit.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 0.05},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Tenant(id="tenant", name="Tenant"))
        db.add(AgentProfile(id="agent", tenant_id="tenant", name="Agent"))
        db.add(Skill(id="skill", tenant_id="tenant", skill_id="sop", version="1.0.0", name="SOP", content_json={}))
        db.add(AgentSkillBranch(id="branch", tenant_id="tenant", agent_id="agent", skill_id="sop", source_skill_id="skill", content_json={}, metadata_json={}))
        db.commit()
    monkeypatch.setattr("app.db.database.engine", engine)
    monkeypatch.setattr("app.public_api.app.engine", engine)
    if audit_fails:
        def failing_audit(db, request, principal, **kwargs):
            db.add(APIAuditLog(request_id=request.state.request_id, method=request.method,
                               path=request.url.path, **kwargs))
            db.flush()
            raise RuntimeError("Audit write failed before commit")

        monkeypatch.setattr("app.public_api.app.audit_request", failing_audit)
    events = []

    @event.listens_for(engine, "after_cursor_execute")
    def record_sql(conn, cursor, statement, parameters, context, executemany):
        if "UPDATE agent_skill_branches" in statement:
            events.append(("branch_update", id(conn)))
        if "INSERT INTO api_audit_logs" in statement:
            events.append(("audit_insert", id(conn)))

    @event.listens_for(engine, "rollback")
    def record_rollback(conn):
        events.append(("rollback", id(conn)))

    @event.listens_for(engine, "commit")
    def record_commit(conn):
        events.append(("commit", id(conn)))

    app = create_public_api_app()

    @app.get("/lifecycle")
    def lifecycle(db: Session = Depends(get_session)):
        branch = ensure_agent_skill_branch(db, "tenant", "agent", db.get(Skill, "skill"))
        assert branch.metadata_json["owner_agent_id"] == "agent"
        db.flush()
        if mode == "commit":
            db.commit()
        if mode == "http_error":
            raise HTTPException(409, "Rejected")
        if mode == "crash":
            raise RuntimeError("Failed route")
        if mode == "stream":
            def body():
                assert db.get(AgentSkillBranch, "branch") is not None
                yield "complete"
            return StreamingResponse(body())
        return {"ok": True}

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/lifecycle", headers={"X-Request-ID": "lifecycle-request"})
    assert response.status_code == status
    if mode == "stream":
        assert response.text == "complete"
    with Session(engine) as db:
        audits = db.exec(select(APIAuditLog)).all()
        assert len(audits) == (0 if audit_fails else 1)
        if not audit_fails:
            assert audits[0].status_code == status
            assert audits[0].request_id == "lifecycle-request"
        assert bool(db.get(AgentSkillBranch, "branch").metadata_json) == (mode == "commit")
    writer = next(conn for kind, conn in events if kind == "branch_update")
    closure = next(i for i, (kind, conn) in enumerate(events) if conn == writer and kind in {"commit", "rollback"})
    audit = next(i for i, (kind, conn) in enumerate(events) if kind == "audit_insert")
    assert closure < audit
    engine.dispose()
