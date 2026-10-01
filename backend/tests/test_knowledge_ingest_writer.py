from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.auth import _ensure_account_api_client
from app.db.models import KnowledgeBucket, KnowledgeChunk, KnowledgeDocument, KnowledgeIngestJob, User
from app.knowledge.service import KnowledgeIngestCancelled, KnowledgeService


def test_chunk_build_allows_account_refresh_and_durable_cancel(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'ingest.sqlite'}", connect_args={"timeout": 0})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id="actor", tenant_id="tenant", username="actor", display_name="Actor", password_hash="unused-fixture")
        document = KnowledgeDocument(tenant_id="tenant", knowledge_base_id="kb", filename="long.md", file_type="md")
        bucket = KnowledgeBucket(tenant_id="tenant", knowledge_base_id="kb", document_id=document.id,
                                 bucket_key="section", title="Section", summary="Section",
                                 metadata_json={"section_ids": ["section"]})
        job = KnowledgeIngestJob(tenant_id="tenant", knowledge_base_id="kb", filename="long.md",
                                 document_id=document.id, status="running")
        db.add_all([user, document, bucket, job])
        _ensure_account_api_client(db, "tenant", user)
        db.commit()
        job_id, document_id, bucket_id = job.id, document.id, bucket.id
    refreshed = []
    with Session(engine) as worker:
        job = worker.get(KnowledgeIngestJob, job_id)
        document = worker.get(KnowledgeDocument, document_id)
        bucket = worker.get(KnowledgeBucket, bucket_id)

        def concurrent_management(connection, cursor, statement, parameters, context, many):
            if refreshed or not statement.lstrip().upper().startswith("SELECT"):
                return
            if not any(isinstance(row, KnowledgeChunk) for row in [*worker.new, *worker.identity_map.values()]):
                return
            refreshed.append(True)
            with Session(engine) as management:
                actor = management.get(User, "actor")
                _ensure_account_api_client(management, "tenant", actor)
                managed_job = management.get(KnowledgeIngestJob, job_id)
                KnowledgeService(management).cancel_ingest_job(job_id, "tenant")
                assert managed_job.status == "cancel_requested"

        event.listen(engine, "before_cursor_execute", concurrent_management)
        try:
            with pytest.raises(KnowledgeIngestCancelled):
                KnowledgeService(worker)._build_chunks("tenant", "kb", document, [bucket], [{
                    "section_id": "section", "path": "Section", "content": "First paragraph.\n\n" + "Evidence " * 1000,
                }], job)
            worker.rollback()
        finally:
            event.remove(engine, "before_cursor_execute", concurrent_management)
    with Session(engine) as db:
        assert refreshed == [True]
        assert db.get(KnowledgeIngestJob, job_id).status == "cancel_requested"
        assert list(db.exec(select(KnowledgeChunk)).all()) == []
