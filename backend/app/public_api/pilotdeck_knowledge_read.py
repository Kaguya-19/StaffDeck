"""Authenticated, read-only module protocol for the fixed PD Knowledge consumer."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlmodel import Session

from app.api import knowledge as native_knowledge
from app.db import get_session
from app.knowledge.public_host_selection import use_public_host_retrieval
from app.knowledge.schema import KnowledgeSearchRequest
from app.public_api.auth import PublicPrincipal, require_scopes
from app.public_api.errors import PublicAPIError
from app.public_api.knowledge_pep import enforce_public_knowledge_pep

router = APIRouter(tags=["pilotdeck-knowledge-read"])


class _ModuleCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    method: str
    messageId: str = Field(min_length=1)
    runId: str = Field(min_length=1)
    operationId: str = Field(min_length=1)
    requestId: str = Field(min_length=1)
    module: str
    payload: dict[str, Any]


_INPUT_FIELDS = {
    "query", "queryType", "desiredEvidence", "scope", "mode",
    "knowledgeBaseIds", "knowledgeBaseVersionIds", "documentIds",
    "maxBucketRounds", "maxBuckets", "maxChunks", "budgetTokens", "maxDepth", "needEvidencePack",
}


def _failure(call: _ModuleCall, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={
        "kind": "response", "messageId": f"response-{call.messageId}",
        "inReplyTo": call.messageId, "requestId": call.requestId, "ok": False,
        "code": code,
        "error": {"code": code, "message": message, "retryability": "unsafe", "details": {}},
    })


@router.get("/knowledge-module/module-manifest")
def read_manifest() -> dict[str, Any]:
    return {"protocolVersion": "2.0", "implementationId": "staffdeck.knowledge",
            "contract": "staffdeck.knowledge/v1", "transport": "module-http-v2",
            "methods": ["query"], "state": {"ownership": "module", "scope": "tenant",
                                               "persistence": "staffdeck-database"}}


@router.post("/agents/{agent_id}/knowledge-module/v2/module/call")
def read_module_call(
    agent_id: str,
    body: dict[str, Any],
    principal: PublicPrincipal = Depends(require_scopes("knowledge:read")),
    db: Session = Depends(get_session),
) -> JSONResponse:
    try:
        call = _ModuleCall.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(400, "Invalid module call envelope") from exc
    if call.kind != "request" or call.method != "module_call" or call.module != "knowledge" \
            or call.payload.get("operation") != "query":
        return _failure(call, 400, "MODULE_PROTOCOL_INCOMPATIBLE", "Only Knowledge query is available")
    raw = call.payload.get("input")
    if not isinstance(raw, dict) or set(raw) - _INPUT_FIELDS:
        return _failure(call, 400, "PUBLIC_SCOPE_OVERRIDE", "Query input cannot supply identity or undeclared fields")
    try:
        query = KnowledgeSearchRequest(
            tenant_id=principal.tenant_id,
            agent_id=agent_id,
            query=raw.get("query"),
            query_type=raw.get("queryType", "answer"),
            desired_evidence=raw.get("desiredEvidence"),
            scope=raw.get("scope") or {},
            mode=raw.get("mode", "chat"),
            knowledge_base_ids=raw.get("knowledgeBaseIds") or [],
            knowledge_base_version_ids=raw.get("knowledgeBaseVersionIds") or [],
            document_ids=raw.get("documentIds") or [],
            max_bucket_rounds=raw.get("maxBucketRounds", 2),
            max_buckets=raw.get("maxBuckets", 4),
            max_chunks=raw.get("maxChunks", 8),
            budget_tokens=raw.get("budgetTokens", 4000),
            max_depth=raw.get("maxDepth", 2),
            need_evidence_pack=raw.get("needEvidencePack", True),
        )
    except ValidationError:
        return _failure(call, 422, "KNOWLEDGE_INPUT_INVALID", "Knowledge query input is invalid")
    if not query.query.strip():
        return _failure(call, 422, "KNOWLEDGE_INPUT_INVALID", "Knowledge query is empty")
    try:
        enforce_public_knowledge_pep(db, principal, agent_id)
        with use_public_host_retrieval():
            result = native_knowledge.search_knowledge(query, db, principal.actor_user)
    except PublicAPIError as exc:
        return _failure(call, exc.status_code, exc.code, exc.detail)
    except HTTPException as exc:
        return _failure(call, exc.status_code, f"STAFFDECK_HTTP_{exc.status_code}", str(exc.detail))
    return JSONResponse(content={
        "kind": "response", "messageId": f"response-{call.messageId}",
        "inReplyTo": call.messageId, "requestId": call.requestId, "ok": True,
        "payload": {"result": result.model_dump(mode="json")},
    })
