from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from app.db import database
from app.db.models import (
    AgentKnowledgeBranch, AgentResourceBinding, KnowledgeBase, KnowledgeBaseVersion,
    KnowledgeDocument, Tenant,
)


def test_current_multidocument_and_edit_versions_survive_schema_restart(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'knowledge.sqlite'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Tenant(id="tenant", name="Tenant"))
        db.add(KnowledgeBase(id="base", tenant_id="tenant", name="Private sources",
                             metadata_json={"private": True}))
        for version in ("1.0.0", "1.0.1"):
            db.add(KnowledgeBaseVersion(id=f"version-{version}", tenant_id="tenant",
                                       knowledge_base_id="base", version=version,
                                       name="Private sources"))
        for index, version in enumerate(("1.0.0", "1.0.0", "1.0.1")):
            db.add(KnowledgeDocument(id=f"doc-{index}", tenant_id="tenant",
                                    knowledge_base_id="base",
                                    knowledge_base_version_id=f"version-{version}",
                                    filename=f"source-{index}.md", file_type="md",
                                    model_config_id="model", status="ready"))
        db.add(AgentKnowledgeBranch(id="branch", tenant_id="tenant", agent_id="owner",
                                    knowledge_base_id="base", head_version="1.0.1"))
        db.add(AgentResourceBinding(id="binding", tenant_id="tenant", agent_id="owner",
                                   resource_type="knowledge_base", resource_id="base",
                                   metadata_json={"private": True}))
        db.commit()
    for _ in range(2):
        inspector = inspect(engine)
        with engine.begin() as conn:
            database._migrate_knowledge_base_schema(conn, inspector, set(inspector.get_table_names()))
        with Session(engine) as db:
            docs = db.exec(select(KnowledgeDocument).order_by(KnowledgeDocument.id)).all()
            assert [(row.knowledge_base_id, row.knowledge_base_version_id) for row in docs] == [
                ("base", "version-1.0.0"), ("base", "version-1.0.0"), ("base", "version-1.0.1"),
            ]
            assert db.get(AgentKnowledgeBranch, "branch").head_version == "1.0.1"
            binding = db.get(AgentResourceBinding, "binding")
            assert (binding.resource_id, binding.metadata_json) == ("base", {"private": True})
            assert not db.exec(select(KnowledgeBase).where(KnowledgeBase.id.like("kb_doc_%"))).all()
    engine.dispose()
