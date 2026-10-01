from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from sqlmodel import Session

from app.config import get_settings
from app.db import engine
from app.public_api import agents, credentials, examples, gallery, jobs, operations, resources, runs, sessions, sops, staffdeck_facade, webhooks
from app.public_api import pilotdeck_approvals, pilotdeck_knowledge_read
from app.public_api.errors import (
    PublicAPIError,
    public_api_error_handler,
    public_http_error_handler,
    public_validation_error_handler,
)
from app.public_api.utils import audit_request


class RequestAuditMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        request.state.request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
        started = perf_counter()
        status_code = 500

        async def send_response(message: Message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request.state.request_id
            await send(message)

        def persist_audit():
            try:
                with Session(engine) as db:
                    audit_request(
                        db, request, getattr(request.state, "public_principal", None),
                        status_code=status_code, duration_ms=(perf_counter() - started) * 1000,
                    )
            except Exception:
                pass

        try:
            await self.app(scope, receive, send_response)
        finally:
            # Dependency sessions (including streaming responses) have now closed.
            # Audit on a separate connection only after their write locks release.
            await run_in_threadpool(persist_audit)


def create_public_api_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} Open API",
        description="数字员工、Harness v2、SOP、知识与自动任务开放 API。",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    from app.public_api.pilotdeck_approval_binding import bind_pilotdeck_approval_client
    bind_pilotdeck_approval_client(app)
    from app.public_api.pilotdeck_domain_binding import bind_pilotdeck_domain_client
    bind_pilotdeck_domain_client(app)
    app.add_exception_handler(PublicAPIError, public_api_error_handler)
    app.add_exception_handler(HTTPException, public_http_error_handler)
    app.add_exception_handler(RequestValidationError, public_validation_error_handler)

    app.add_middleware(RequestAuditMiddleware)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "v1", "engine": "harness_v3"}

    app.include_router(pilotdeck_approvals.router)
    app.include_router(pilotdeck_knowledge_read.router)
    app.include_router(credentials.router)
    app.include_router(gallery.router)
    app.include_router(agents.router)
    app.include_router(sessions.router)
    app.include_router(runs.router)
    app.include_router(jobs.router)
    app.include_router(sops.router)
    app.include_router(staffdeck_facade.router)
    app.include_router(resources.router)
    app.include_router(operations.router)
    app.include_router(webhooks.router)
    app.include_router(examples.router)
    return app
