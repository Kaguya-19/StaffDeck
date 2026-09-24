from __future__ import annotations

from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine, select

from app.agents.branching import ensure_agent_skill_branch
from app.db.models import AgentProfile, AgentResourceBinding, AgentSkillBranch, Skill, Tenant
from staffdeck_harness.composition.local_sources import LocalSopSource
from staffdeck_harness.contracts.sources import SourceContext


def _content(version: str, node_ids: list[str]) -> dict:
    return {
        "skill_id": "project_delivery_plan",
        "name": "Project delivery plan",
        "version": version,
        "nodes": [
            {"node_id": node_id, "type": "response", "name": node_id}
            for node_id in node_ids
        ],
        "edges": [],
        "start_node_id": node_ids[0],
        "terminal_node_ids": [node_ids[-1]],
    }


def test_runtime_sop_source_reads_committed_branch_after_publication(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'staffdeck.sqlite3'}")
    SQLModel.metadata.create_all(engine)
    initial = _content("1.0.0", ["n1_collect", "n2_plan"])
    with Session(engine) as db:
        db.add_all([
            Tenant(id="tenant", name="Tenant"),
            AgentProfile(id="agent", tenant_id="tenant", name="Project", status="active"),
            Skill(
                id="skill-row",
                tenant_id="tenant",
                skill_id="project_delivery_plan",
                version="1.0.0",
                name="Project delivery plan",
                content_json=initial,
                status="published",
            ),
            AgentResourceBinding(
                id="binding",
                tenant_id="tenant",
                agent_id="agent",
                resource_type="skill",
                resource_id="skill-row",
                status="active",
                metadata_json={"scope": "agent_private"},
            ),
        ])
        db.commit()
        branch_id = ensure_agent_skill_branch(db, "tenant", "agent", db.get(Skill, "skill-row")).id
        db.commit()

        # The request session has already observed the pre-publication branch.
        source = LocalSopSource(db)
        context = SourceContext("tenant", "agent", session_id="new-session")
        assert source.resolve(context, SimpleNamespace(staff_id="agent"))[0].version == "1.0.0"

    stale_request = Session(engine)
    # Load the old branch into the request session before publication. The
    # runtime source must not reuse this identity-mapped row.
    assert stale_request.get(AgentSkillBranch, branch_id).head_version == "1.0.0"

    published = _content("1.1.0", ["n1_collect", "build_plan", "confirm_scope", "finalize_plan"])
    with Session(engine) as publisher:
        branch = publisher.exec(select(AgentSkillBranch)).first()
        branch.head_version = "1.1.0"
        branch.content_json = published
        branch.sync_state = "diverged"
        publisher.add(branch)
        publisher.commit()

    source = LocalSopSource(stale_request)
    context = SourceContext("tenant", "agent", session_id="new-session")
    # Runtime resolution uses a fresh committed read, so the native planner
    # receives the published graph while old task pins remain independent.
    views = source.resolve(context, SimpleNamespace(staff_id="agent"))
    assert len(views) == 1
    assert views[0].version == "1.1.0"
    assert [node["node_id"] for node in views[0].content["nodes"]] == [
        "n1_collect", "build_plan", "confirm_scope", "finalize_plan"
    ]
    stale_request.close()
    engine.dispose()
