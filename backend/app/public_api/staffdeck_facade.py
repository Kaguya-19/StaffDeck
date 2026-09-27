"""Bounded public facades for formal SOP/UI operations missing from public v1.

The API key is resolved by the public principal. Calls below explicitly pass its
actor and tenant to the existing owner operations; FastAPI dependencies on the
enterprise routes are never assumed to run during a direct Python call.
"""
from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from app.agents.branching import get_agent
from app.api import agents as native_agents
from app.api import general_skills as native_general_skills
from app.api import knowledge_bases as native_knowledge_bases
from app.api import skills as native_skills
from app.api import tools as native_tools
from app.db import get_session
from app.db.models import ModelConfig, User
from app.public_api.auth import PublicPrincipal, enforce_agent_access, require_scopes
from app.public_api.errors import PublicAPIError
from app.public_api.sessions import ensure_public_agent
from app.security.permissions import ensure_agent_scope_manager, require_agent_scope_viewer
from app.skills.skill_schema import SkillCard, SkillDistillRequest, SkillRewriteRequest
from app.tools.tool_schema import ToolProbeRequest

router = APIRouter(tags=["staffdeck-public-facade"])
_preview_agents: OrderedDict[str, str | None] = OrderedDict()
_preview_agents_lock = Lock()


def _register_preview_job(job_id: str, agent_id: str | None) -> None:
    # The native transient store records tenant and actor, but not agent. Keep
    # the path binding for the same in-memory lifetime as that store.
    with _preview_agents_lock:
        _preview_agents[job_id] = agent_id
        while len(_preview_agents) > 200:
            _preview_agents.popitem(last=False)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreviewGenerate(_Strict):
    title: str = Field(min_length=1)
    raw_content: str = Field(min_length=1)
    business_domain: str | None = None
    model_config_id: str | None = None
    available_tools: list[dict[str, Any]] = Field(default_factory=list)
    available_general_skills: list[dict[str, Any]] = Field(default_factory=list)
    available_knowledge_bases: list[dict[str, Any]] = Field(default_factory=list)


class PreviewRewrite(_Strict):
    current_skill: SkillCard
    instruction: str = Field(min_length=1)
    model_config_id: str | None = None
    target_path: str = "all"
    target_paths: list[str] = Field(default_factory=list)
    target_label: str | None = None
    conversation: list[dict[str, str]] = Field(default_factory=list)
    available_tools: list[dict[str, Any]] = Field(default_factory=list)
    available_sops: list[dict[str, Any]] = Field(default_factory=list)


def _agent(db: Session, principal: PublicPrincipal, agent_id: str, *, write: bool = False) -> None:
    enforce_agent_access(principal, agent_id, write=write)
    ensure_public_agent(db, principal, agent_id)
    if write:
        # Preserve the enterprise resource PEP, not just API-key scopes.
        ensure_agent_scope_manager(db, principal.tenant_id, agent_id, principal.actor_user)


def _team(db: Session, principal: PublicPrincipal) -> None:
    if principal.agent_id is not None:
        raise PublicAPIError(403, "TEAM_SCOPE_REQUIRES_ACCOUNT", "Team scope requires an account credential.")
    require_agent_scope_viewer(principal.tenant_id, None, principal.actor_user, db)


def _payload(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude={"tenant_id"})
    return value


@router.post("/agents/{agent_id}/sops:preview-generate", status_code=202)
def preview_generate(
    agent_id: str,
    body: PreviewGenerate,
    principal: PublicPrincipal = Depends(require_scopes("sops:write")),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    _agent(db, principal, agent_id, write=True)
    request = SkillDistillRequest(tenant_id=principal.tenant_id, agent_id=agent_id, **body.model_dump())
    # This is the original transient stream job. It never creates APISOPDraft.
    result = native_skills.create_distill_job(request, db, principal.actor_user)
    _register_preview_job(result["job_id"], agent_id)
    return result


@router.post("/team/sops:preview-generate", status_code=202)
def team_preview_generate(
    body: PreviewGenerate,
    principal: PublicPrincipal = Depends(require_scopes("sops:write")),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    _team(db, principal)
    request = SkillDistillRequest(tenant_id=principal.tenant_id, agent_id=None, **body.model_dump())
    result = native_skills.create_distill_job(request, db, principal.actor_user)
    _register_preview_job(result["job_id"], None)
    return result


@router.post("/agents/{agent_id}/sops/{sop_id}:preview-rewrite", status_code=202)
def preview_rewrite(
    agent_id: str,
    sop_id: str,
    body: PreviewRewrite,
    principal: PublicPrincipal = Depends(require_scopes("sops:write")),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    _agent(db, principal, agent_id, write=True)
    request = SkillRewriteRequest(tenant_id=principal.tenant_id, agent_id=agent_id, **body.model_dump())
    result = native_skills.create_rewrite_job(sop_id, request, db, principal.actor_user)
    _register_preview_job(result["job_id"], agent_id)
    return result


@router.post("/team/sops/{sop_id}:preview-rewrite", status_code=202)
def team_preview_rewrite(
    sop_id: str,
    body: PreviewRewrite,
    principal: PublicPrincipal = Depends(require_scopes("sops:write")),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    _team(db, principal)
    request = SkillRewriteRequest(tenant_id=principal.tenant_id, agent_id=None, **body.model_dump())
    result = native_skills.create_rewrite_job(sop_id, request, db, principal.actor_user)
    _register_preview_job(result["job_id"], None)
    return result


def _preview_job(principal: PublicPrincipal, agent_id: str | None, job_id: str, db: Session):
    if agent_id is None:
        _team(db, principal)
    else:
        _agent(db, principal, agent_id)
    with _preview_agents_lock:
        if job_id not in _preview_agents or _preview_agents[job_id] != agent_id:
            raise PublicAPIError(404, "JOB_NOT_FOUND", "Job not found for this agent.")
    # Native stream jobs are tenant + actual actor owned, not APIJob IDs.
    return native_skills._owned_stream_job(job_id, principal.actor_user)


@router.get("/agents/{agent_id}/sop-preview-jobs/{job_id}")
def get_preview_job(
    agent_id: str,
    job_id: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:read")),
    db: Session = Depends(get_session),
) -> dict[str, object]:
    _preview_job(principal, agent_id, job_id, db)
    return native_skills.get_skill_stream_job(job_id, principal.actor_user)


@router.get("/agents/{agent_id}/sop-preview-jobs/{job_id}/events")
def preview_job_events(
    agent_id: str,
    job_id: str,
    after_seq: int = Query(0, ge=0),
    principal: PublicPrincipal = Depends(require_scopes("sops:read")),
    db: Session = Depends(get_session),
) -> StreamingResponse:
    _preview_job(principal, agent_id, job_id, db)
    return native_skills.stream_existing_skill_job(job_id, after_seq, principal.actor_user)


@router.post("/agents/{agent_id}/sop-preview-jobs/{job_id}:cancel")
def cancel_preview_job(
    agent_id: str,
    job_id: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:cancel")),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    _preview_job(principal, agent_id, job_id, db)
    return native_skills.cancel_skill_stream_job(job_id, principal.actor_user)


@router.get("/team/sop-preview-jobs/{job_id}")
def get_team_preview_job(
    job_id: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:read")),
    db: Session = Depends(get_session),
) -> dict[str, object]:
    _preview_job(principal, None, job_id, db)
    return native_skills.get_skill_stream_job(job_id, principal.actor_user)


@router.get("/team/sop-preview-jobs/{job_id}/events")
def team_preview_job_events(
    job_id: str,
    after_seq: int = Query(0, ge=0),
    principal: PublicPrincipal = Depends(require_scopes("sops:read")),
    db: Session = Depends(get_session),
) -> StreamingResponse:
    _preview_job(principal, None, job_id, db)
    return native_skills.stream_existing_skill_job(job_id, after_seq, principal.actor_user)


@router.post("/team/sop-preview-jobs/{job_id}:cancel")
def cancel_team_preview_job(
    job_id: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:cancel")),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    _preview_job(principal, None, job_id, db)
    return native_skills.cancel_skill_stream_job(job_id, principal.actor_user)


@router.get("/team/tools")
def list_team_tools(
    principal: PublicPrincipal = Depends(require_scopes("tools:read")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _team(db, principal)
    from app.public_api.resources import _masked_tool
    rows = native_tools.list_tools(principal.tenant_id, None, None, db)
    return {"data": [_masked_tool(row) for row in rows], "next_cursor": None}


@router.get("/team/general-skills")
def list_team_general_skills(
    principal: PublicPrincipal = Depends(require_scopes("skills:read")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _team(db, principal)
    rows = native_general_skills.list_general_skills(principal.tenant_id, db, None)
    return {"data": [_payload(row) for row in rows], "next_cursor": None}


@router.get("/team/sops")
def list_team_sops(
    principal: PublicPrincipal = Depends(require_scopes("sops:read")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _team(db, principal)
    rows = native_skills.list_skills(principal.tenant_id, db, None)
    return {"data": [_payload(row) for row in rows], "drafts": [], "next_cursor": None}


@router.get("/team/sops/{sop_id}/versions")
def list_team_sop_versions(
    sop_id: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:read")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _team(db, principal)
    rows = native_skills.list_skill_versions(sop_id, principal.tenant_id, db, None)
    return {"data": [_payload(row) for row in rows]}


@router.get("/team/sops/{sop_id}/versions/{version}")
def get_team_sop_version(
    sop_id: str,
    version: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:read")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _team(db, principal)
    rows = native_skills.list_skill_versions(sop_id, principal.tenant_id, db, None)
    for row in rows:
        if row.version == version:
            return _payload(row)
    raise PublicAPIError(404, "SOP_VERSION_NOT_FOUND", "SOP version not found.")


@router.get("/team/knowledge-bases")
def list_team_knowledge_bases(
    principal: PublicPrincipal = Depends(require_scopes("knowledge:read")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _team(db, principal)
    rows = native_knowledge_bases.list_knowledge_bases(principal.tenant_id, None, db)
    return {"data": [_payload(row) for row in rows], "next_cursor": None}


@router.post("/agents/{agent_id}/sops/{sop_id}:move-to-draft")
def move_to_draft(
    agent_id: str,
    sop_id: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _agent(db, principal, agent_id, write=True)
    return _payload(native_skills.draft_skill(sop_id, principal.tenant_id, agent_id, db, principal.actor_user))


@router.delete("/agents/{agent_id}/sops/{sop_id}")
def remove_sop(
    agent_id: str,
    sop_id: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:write")),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    _agent(db, principal, agent_id, write=True)
    return native_skills.delete_skill(sop_id, principal.tenant_id, db, agent_id, principal.actor_user)


@router.post("/agents/{agent_id}/sops/{sop_id}:sync-from-overall")
def sync_from_overall(
    agent_id: str,
    sop_id: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:write")),
    db: Session = Depends(get_session),
) -> dict[str, object]:
    _agent(db, principal, agent_id, write=True)
    return native_agents.sync_agent_skill_from_overall(agent_id, sop_id, principal.tenant_id, db, principal.actor_user)


@router.post("/agents/{agent_id}/sops/{sop_id}:promote-to-overall")
def promote_to_overall(
    agent_id: str,
    sop_id: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:publish")),
    db: Session = Depends(get_session),
) -> dict[str, object]:
    _agent(db, principal, agent_id, write=True)
    return native_agents.promote_agent_skill_to_overall(agent_id, sop_id, principal.tenant_id, db, principal.actor_user)


@router.delete("/agents/{agent_id}/sops/{sop_id}/versions/{version}")
def delete_sop_version(
    agent_id: str,
    sop_id: str,
    version: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:publish")),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    _agent(db, principal, agent_id, write=True)
    agent = get_agent(db, principal.tenant_id, agent_id)
    if not agent or not agent.is_overall:
        raise PublicAPIError(403, "OVERALL_SOP_REQUIRED", "Only overall SOP history can be deleted.")
    return native_skills.delete_skill_version(sop_id, version, principal.tenant_id, db, principal.actor_user)


@router.post("/agents/{agent_id}/tools:probe")
def probe_unsaved_tool(
    agent_id: str,
    body: dict[str, Any],
    principal: PublicPrincipal = Depends(require_scopes("tools:test")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _agent(db, principal, agent_id, write=True)
    if "tenant_id" in body or "agent_id" in body:
        raise PublicAPIError(400, "PUBLIC_SCOPE_OVERRIDE", "Scope is determined by the public principal.")
    request = ToolProbeRequest.model_validate({**body, "tenant_id": principal.tenant_id})
    return _payload(native_tools.probe_tool(request, db, principal.actor_user))


@router.delete("/agents/{agent_id}/tools/{tool_id}")
def remove_tool(
    agent_id: str,
    tool_id: str,
    principal: PublicPrincipal = Depends(require_scopes("tools:write")),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    _agent(db, principal, agent_id, write=True)
    return native_tools.delete_tool(tool_id, principal.tenant_id, db, agent_id, principal.actor_user)


@router.post("/agents/{agent_id}/sops:extract-file")
def extract_sop_file(
    agent_id: str,
    body: native_skills.SkillFileExtractRequest,
    principal: PublicPrincipal = Depends(require_scopes("sops:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _agent(db, principal, agent_id, write=True)
    return _payload(native_skills.extract_skill_file(body))


@router.get("/agents/{agent_id}/model-catalog")
def visible_model_catalog(
    agent_id: str,
    principal: PublicPrincipal = Depends(require_scopes("sops:read")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _agent(db, principal, agent_id)
    # Only non-secret selection metadata. Agent binding/runtime readiness is a separate read.
    rows = db.exec(select(ModelConfig).where(ModelConfig.tenant_id == principal.tenant_id)).all()
    return {"data": [
        {"id": row.id, "name": row.name, "model": row.model,
         "provider": row.provider, "enabled": row.enabled, "is_default": row.is_default}
        for row in rows
    ]}


@router.get("/agents/{agent_id}/handoff-users")
def visible_handoff_users(
    agent_id: str,
    principal: PublicPrincipal = Depends(require_scopes("agents:read")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _agent(db, principal, agent_id)
    from staffdeck_harness.runtime.control_auth import provider
    if provider() is not None:
        # The external directory requires a control subject/token. A public API
        # key is not a control token, so no fallback to local shadow rows.
        raise PublicAPIError(503, "USER_DIRECTORY_UNAVAILABLE", "The selected identity source has no public directory reader.")
    statement = select(User).where(User.tenant_id == principal.tenant_id, User.source == "web")
    rows = db.exec(statement.order_by(User.created_at.desc())).all()
    return {"data": [{"id": row.id, "username": row.username, "display_name": row.display_name,
                      "role": row.role} for row in rows]}
