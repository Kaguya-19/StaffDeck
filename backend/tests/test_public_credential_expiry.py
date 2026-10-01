from datetime import UTC, datetime, timedelta, timezone
import json
import subprocess
import sys

import pytest
from sqlmodel import Session, create_engine

from app.api.auth import AccountAPICredentialCreateRequest, create_account_api_credential
from app.db.models import APICredential, User
from app.public_api import auth
from app.public_api.auth import principal_for_credential
from app.public_api.errors import PublicAPIError
from test_public_api_v1 import _client


@pytest.mark.parametrize("creation", ["account", "client"])
@pytest.mark.parametrize("offset", [0, 8, -5, None])
def test_credential_deadline_roundtrip_and_deferred_revalidation(tmp_path, monkeypatch, creation, offset):
    url = f"sqlite:///{tmp_path / 'credentials.sqlite'}"
    client, engine, admin_token = _client(monkeypatch, database_url=url)
    instant = datetime(2030, 1, 1, tzinfo=UTC)
    clock = {"now": instant}
    monkeypatch.setattr(auth, "utc_now", lambda: clock["now"])
    expiry = None if offset is None else (instant + timedelta(seconds=10)).astimezone(timezone(timedelta(hours=offset)))
    if creation == "account":
        with Session(engine) as db:
            actor = db.get(User, "user_api_admin")
            created = create_account_api_credential(AccountAPICredentialCreateRequest(name="expiry", expires_at=expiry), actor, db)
            key, credential_id = created.api_key, created.id
    else:
        headers = {"Authorization": f"Bearer {admin_token}"}
        owner = client.post("/api-clients", headers=headers, json={"name": "expiry", "scopes": ["*"]})
        assert owner.status_code == 201
        created = client.post(f"/api-clients/{owner.json()['id']}/credentials", headers=headers,
                              json={"name": "expiry", "scopes": ["agents:read"], "expires_at": expiry.isoformat() if expiry else None})
        assert created.status_code == 201, created.text
        key, credential_id = created.json()["api_key"], created.json()["id"]
    headers = {"Authorization": f"Bearer {key}"}
    before = client.get("/agents/agent_api", headers=headers)
    assert before.status_code == 200, before.text
    with Session(engine) as db:
        stored = db.get(APICredential, credential_id).expires_at
        assert stored == (instant + timedelta(seconds=10)).replace(tzinfo=None) if expiry else stored is None
    engine.dispose()
    reopened = create_engine(url)
    if offset == 0:
        # A separate interpreter reopens the persisted grant, as deferred work
        # does after a service restart; no token or password crosses the pipe.
        script = """
import json, sys
from datetime import datetime
from sqlmodel import Session, create_engine
from app.public_api import auth
from app.public_api.errors import PublicAPIError
payload = json.load(sys.stdin)
auth.utc_now = lambda: datetime.fromisoformat(payload['now'])
with Session(create_engine(payload['url'])) as db:
    try:
        auth.principal_for_credential(db, payload['id'])
        print('200')
    except PublicAPIError as error:
        print(str(error.status_code) + ':' + error.code)
"""
        for elapsed, expected in ((9, "200"), (10, "401:API_KEY_EXPIRED")):
            result = subprocess.run([sys.executable, "-c", script], input=json.dumps({
                "url": url, "id": credential_id, "now": (instant + timedelta(seconds=elapsed)).isoformat(),
            }), text=True, capture_output=True)
            assert result.returncode == 0, result.stderr
            assert result.stdout.strip() == expected
    for elapsed in (9, 10, 11):
        clock["now"] = instant + timedelta(seconds=elapsed)
        response = client.get("/agents/agent_api", headers=headers)
        if expiry and elapsed >= 10:
            assert response.status_code == 401, response.text
            assert response.headers["content-type"].startswith("application/problem+json")
            assert response.json()["code"] == "API_KEY_EXPIRED"
            with Session(reopened) as db:
                with pytest.raises(PublicAPIError) as denied:
                    principal_for_credential(db, credential_id)
                assert (denied.value.status_code, denied.value.code) == (401, "API_KEY_EXPIRED")
        else:
            assert response.status_code == 200, response.text
            with Session(reopened) as db:
                assert principal_for_credential(db, credential_id).actor_user.id == "user_api_admin"
    reopened.dispose()
