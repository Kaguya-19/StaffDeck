from sqlmodel import Session, select

from app.db.models import APISOPDraft, Skill
from test_public_api_v1 import _client, _tenant_key, _skill_card


def test_first_edit_uses_target_publication_and_validates_explicit_history(monkeypatch, tmp_path):
    client, engine, token = _client(monkeypatch, database_url=f"sqlite:///{tmp_path / 'publication.sqlite'}")
    key = _tenant_key(client, token, ["sops:read", "sops:write", "sops:publish"])
    headers = {"Authorization": f"Bearer {key}"}
    content = {**_skill_card(), "version": "2.3.4"}
    created = client.post("/agents/agent_api/sops", headers=headers, json={"content": _skill_card()})
    assert created.status_code == 201, created.text
    published = client.post("/sops/expense_policy_v1:publish?agent_id=agent_api", headers=headers, json={"draft_id": created.json()["id"]})
    assert published.status_code == 200, published.text
    branch_draft = client.post("/agents/agent_api/sops", headers=headers, json={"content": content}).json()
    replaced = client.put(f"/agents/agent_api/sops/expense_policy_v1?draft_id={branch_draft['id']}",
                          headers={**headers, "If-Match": branch_draft["etag"]}, json={"content": content})
    assert replaced.status_code == 200, replaced.text
    published = client.post("/sops/expense_policy_v1:publish?agent_id=agent_api", headers=headers,
                            json={"draft_id": branch_draft["id"]})
    assert published.status_code == 200, published.text
    with Session(engine) as db:
        global_row = db.exec(select(Skill).where(Skill.skill_id == "expense_policy_v1")).one()
        assert global_row.version == "1.0.0"  # The private employee publication is independent.
    selected = client.get("/sops/expense_policy_v1/versions/2.3.4?agent_id=agent_api", headers=headers)
    assert selected.status_code == 200, selected.text
    edited = {**selected.json()["content"], "name": "Reviewed", "version": "99.0.0"}
    first = client.post("/agents/agent_api/sops", headers={**headers, "Idempotency-Key": "selected-edit"},
                        json={"content": edited, "base_version": "2.3.4"})
    assert first.status_code == 201, first.text
    draft = first.json()
    assert (draft["base_version"], draft["draft_version"], draft["content"]["version"]) == ("2.3.4", "2.3.5", "2.3.5")
    replay = client.post("/agents/agent_api/sops", headers={**headers, "Idempotency-Key": "selected-edit"},
                         json={"content": edited, "base_version": "2.3.4"})
    assert replay.json()["id"] == draft["id"]
    before = len(client.get("/agents/agent_api/sops", headers=headers).json()["drafts"])
    denied = client.post("/agents/agent_api/sops", headers=headers, json={"content": edited, "base_version": "9.9.9"})
    assert denied.status_code == 404, denied.text
    assert len(client.get("/agents/agent_api/sops", headers=headers).json()["drafts"]) == before
    foreign = client.post("/agents/agent_other/sops", headers=headers, json={"content": edited, "base_version": "2.3.4"})
    assert foreign.status_code == 404, foreign.text
    stale = client.put(f"/agents/agent_api/sops/expense_policy_v1?draft_id={draft['id']}", headers={**headers, "If-Match": '"old"'}, json={"content": edited})
    assert stale.status_code == 412
    with Session(engine) as db:
        assert db.get(APISOPDraft, draft["id"]).content_json["name"] == "Reviewed"
