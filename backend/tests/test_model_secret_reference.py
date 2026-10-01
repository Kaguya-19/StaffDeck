from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from app.api import auth, model_configs
from app.api.model_configs import create_model_config
from app.config import get_settings
from app.db import database, get_session
from app.db.models import ModelConfig, Tenant, User
from app.llm.client import LLMClient
from app.llm.model_config_resolver import resolve_model_config_for_runtime
from app.llm.schemas import ModelConfigCreateRequest
from app.security.auth import hash_password


def test_native_model_accepts_process_secret_reference_without_persisting_key(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "model_secret_bindings", {
        "tenant_a": {"discovery": {"env": "R105_TEST_MODEL_KEY", "revision": "1"}},
    }, raising=False)
    monkeypatch.setenv("R105_TEST_MODEL_KEY", "test-only-in-memory")
    engine = create_engine(f"sqlite:///{tmp_path / 'models.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Tenant(id="tenant_a", name="A"))
        db.commit()
        row = create_model_config(ModelConfigCreateRequest(
            tenant_id="tenant_a", name="Discovery", model="model-a", secret_ref="discovery",
        ), db=db, current_user=User(
            id="admin", tenant_id="tenant_a", username="admin", role="admin", password_hash="unused",
        ))
        assert row.secret_ref == "discovery"
        assert row.secret_ref_revision == "1"
        assert row.api_key_masked == ""
        assert not row.enabled
    engine.dispose()
    assert b"test-only-in-memory" not in (tmp_path / "models.db").read_bytes()


@pytest.fixture
def native_api(tmp_path, monkeypatch):
    # Deterministic provider transport fixture, not a real-model acceptance result.
    state = {"failed": False, "probes": []}

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            valid_auth = self.headers.get("Authorization") == f"Bearer {os.environ['R105_TEST_MODEL_KEY']}"
            assert valid_auth
            state["probes"].append("stream" if payload.get("stream") else "text_or_json")
            if state["failed"]:
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"error":{"message":"fixture rejection"}}')
            elif payload.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                chunk = {"id": "fixture", "object": "chat.completion.chunk", "model": "fixture", "choices": [{"index": 0, "delta": {"content": "stream-ok"}, "finish_reason": None}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode())
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"id": "fixture", "object": "chat.completion", "model": "fixture", "choices": [{"index": 0, "message": {"role": "assistant", "content": '{"ok":true}'}, "finish_reason": "stop"}]}).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("R105_TEST_MODEL_KEY", "fixture-process-only-key")
    monkeypatch.setattr(get_settings(), "model_secret_bindings", {
        "tenant_a": {"discovery": {"env": "R105_TEST_MODEL_KEY", "revision": "1"}},
    })
    path = tmp_path / "native-api.db"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        for tenant in ("tenant_a", "tenant_b"):
            db.add(Tenant(id=tenant, name=tenant))
        for username, tenant, role in (("admin", "tenant_a", "admin"), ("member", "tenant_a", "member"), ("other", "tenant_b", "admin")):
            db.add(User(id=username, username=username, tenant_id=tenant, role=role, password_hash=hash_password("fixture-password")))
        db.commit()
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(model_configs.router)

    def sessions():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = sessions
    with TestClient(app) as client:
        tokens = {}
        for username, tenant in (("admin", "tenant_a"), ("member", "tenant_a"), ("other", "tenant_b")):
            response = client.post("/api/auth/login", json={"tenant_id": tenant, "username": username, "password": "fixture-password"})
            assert response.status_code == 200
            tokens[username] = {"Authorization": f"Bearer {response.json()['token']}"}
        yield client, engine, path, tokens, state, f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()
    server.server_close()
    thread.join()
    engine.dispose()


def _create(native_api, **overrides):
    client, _, _, tokens, _, url = native_api
    payload = {"tenant_id": "tenant_a", "name": "Discovery", "model": "fixture", "base_url": url, "secret_ref": "discovery"}
    payload.update(overrides)
    return client.post("/api/enterprise/model-configs?verify_before_save=true", json=payload, headers=tokens["admin"])


def test_formal_api_verifies_all_probes_and_default_then_restart_requires_reverification(native_api):
    client, engine, path, tokens, state, _ = native_api
    response = _create(native_api)
    assert response.status_code == 200, response.text
    model = response.json()
    assert model["trust_status"] == "verified"
    assert model["enabled"] and model["is_default"] and model["credential_configured"]
    assert model["api_key_masked"] == ""
    assert state["probes"] == ["text_or_json", "stream", "text_or_json"]
    with Session(engine) as db:
        row = db.get(ModelConfig, model["id"])
        assert row.api_key_encrypted == ""
        assert row.secret_ref == "discovery" and row.secret_ref_revision == "1"
        resolved = resolve_model_config_for_runtime(db, "tenant_a", row.id)
        assert LLMClient(resolved).generate_json("Return JSON", {}) == {"ok": True}
    from app.knowledge.service import KnowledgeService
    with Session(engine) as db:
        service = KnowledgeService(db)
        assert service._default_model_config("tenant_a").secret_ref == "discovery"
        service._public_host_ingest = True
        assert service._default_model_config("tenant_a") is None
    # A genuinely new Python process reloads only the persisted reference metadata.
    script = '''
import os
from fastapi import HTTPException
from sqlmodel import Session, create_engine
from app.llm.model_config_resolver import resolve_model_config_for_runtime
from app.db.models import ModelConfig
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api import auth, model_configs
from app.db import get_session
engine = create_engine("sqlite:///" + os.environ["R105_TEST_DB"])
with Session(engine) as db:
    row = db.get(ModelConfig, os.environ["R105_TEST_CONFIG"])
    assert row.secret_ref == "discovery" and row.api_key_encrypted == ""
    try:
        resolve_model_config_for_runtime(db, row.tenant_id, row.id)
    except HTTPException as exc:
        assert exc.status_code == 409 and exc.detail == "MODEL_CONFIG_VERIFICATION_REQUIRED"
    else:
        raise AssertionError("restart inherited process-bound trust")
app = FastAPI()
app.include_router(auth.router)
app.include_router(model_configs.router)
def sessions():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_session] = sessions
with TestClient(app) as client:
    login = client.post("/api/auth/login", json={"tenant_id":"tenant_a","username":"admin","password":"fixture-password"})
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["token"]}
    result = client.post("/api/enterprise/model-configs/" + os.environ["R105_TEST_CONFIG"] + "/test?tenant_id=tenant_a&activate_if_initial=true", headers=headers)
    assert result.status_code == 200 and result.json()["success"]
with Session(engine) as db:
    resolve_model_config_for_runtime(db, "tenant_a", os.environ["R105_TEST_CONFIG"])
print("restart metadata readback, old trust rejection, authenticated reverify PASS")
'''
    child_env = {**os.environ, "R105_TEST_DB": str(path), "R105_TEST_CONFIG": model["id"], "MODEL_SECRET_BINDINGS": json.dumps(get_settings().model_secret_bindings)}
    result = subprocess.run([sys.executable, "-c", script], env=child_env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    with Session(engine) as db, pytest.raises(HTTPException) as error:
        resolve_model_config_for_runtime(db, "tenant_a", model["id"])
    assert error.value.detail == "MODEL_CONFIG_VERIFICATION_REQUIRED"
    readback = client.get("/api/enterprise/model-configs?tenant_id=tenant_a", headers=tokens["admin"])
    assert readback.json()[0]["secret_ref"] == "discovery"
    assert b"fixture-process-only-key" not in path.read_bytes()


@pytest.mark.parametrize("change", ["value", "revision", "env", "restart"])
def test_binding_changes_reject_old_runtime_and_snapshot_then_formal_reverify(native_api, monkeypatch, change):
    client, engine, _, tokens, _, _ = native_api
    response = _create(native_api)
    assert response.status_code == 200
    model = response.json()
    with Session(engine) as db:
        snapshot = resolve_model_config_for_runtime(db, "tenant_a", model["id"])
    if change == "value":
        monkeypatch.setenv("R105_TEST_MODEL_KEY", "rotated-process-key")
    elif change == "revision":
        monkeypatch.setattr(get_settings(), "model_secret_bindings", {"tenant_a": {"discovery": {"env": "R105_TEST_MODEL_KEY", "revision": "2"}}})
    elif change == "env":
        monkeypatch.setenv("R105_TEST_OTHER_KEY", os.environ["R105_TEST_MODEL_KEY"])
        monkeypatch.setattr(get_settings(), "model_secret_bindings", {"tenant_a": {"discovery": {"env": "R105_TEST_OTHER_KEY", "revision": "1"}}})
    else:
        from app.llm import model_credentials
        monkeypatch.setattr(model_credentials, "_bindings", {})
    with Session(engine) as db, pytest.raises(HTTPException) as error:
        resolve_model_config_for_runtime(db, "tenant_a", model["id"])
    assert error.value.status_code == 409
    with pytest.raises(HTTPException):
        LLMClient(snapshot)
    retest = client.post(f"/api/enterprise/model-configs/{model['id']}/test?tenant_id=tenant_a&activate_if_initial=true", headers=tokens["admin"])
    assert retest.status_code == 200 and retest.json()["success"], retest.text
    assert retest.json()["model"]["security_revision"] == model["security_revision"] + 1
    with Session(engine) as db:
        resolve_model_config_for_runtime(db, "tenant_a", model["id"])


@pytest.mark.parametrize("actor", ["member", "other"])
def test_nonadmin_and_cross_tenant_admin_cannot_configure_reference(native_api, actor):
    client, engine, _, tokens, _, url = native_api
    response = client.post("/api/enterprise/model-configs", json={"tenant_id": "tenant_a", "name": "No", "model": "fixture", "base_url": url, "secret_ref": "discovery"}, headers=tokens[actor])
    assert response.status_code == 403
    with Session(engine) as db:
        assert db.exec(select(ModelConfig)).all() == []


def test_reference_alias_does_not_resolve_from_another_tenant(native_api):
    client, _, _, tokens, _, url = native_api
    response = client.post("/api/enterprise/model-configs", json={"tenant_id": "tenant_b", "name": "No", "model": "fixture", "base_url": url, "secret_ref": "discovery"}, headers=tokens["other"])
    assert response.status_code == 422 and response.json()["detail"] == "MODEL_SECRET_REFERENCE_NOT_CONFIGURED"


@pytest.mark.parametrize("overrides,code", [
    ({"secret_ref": "absent"}, "MODEL_SECRET_REFERENCE_NOT_CONFIGURED"),
    ({"secret_ref": None}, "MODEL_API_KEY_REQUIRED"),
    ({"api_key": "literal"}, "MODEL_CREDENTIAL_SOURCE_CONFLICT"),
])
def test_invalid_reference_requests_fail_without_model_row(native_api, overrides, code):
    response = _create(native_api, **overrides)
    assert response.status_code == 422 and response.json()["detail"] == code
    with Session(native_api[1]) as db:
        assert db.exec(select(ModelConfig)).all() == []


def test_missing_env_and_failed_probes_never_activate_or_persist_key(native_api, monkeypatch):
    monkeypatch.delenv("R105_TEST_MODEL_KEY")
    response = _create(native_api)
    assert response.status_code == 422 and response.json()["detail"] == "MODEL_SECRET_REFERENCE_UNAVAILABLE"
    monkeypatch.setenv("R105_TEST_MODEL_KEY", "fixture-process-only-key")
    native_api[4]["failed"] = True
    assert _create(native_api).status_code == 502
    with Session(native_api[1]) as db:
        assert db.exec(select(ModelConfig)).all() == []


def test_reference_to_literal_and_back_obey_security_revisions(native_api):
    client, engine, _, tokens, _, _ = native_api
    model = _create(native_api).json()
    url = f"/api/enterprise/model-configs/{model['id']}"
    literal = client.put(url, headers=tokens["admin"], json={"tenant_id": "tenant_a", "api_key": "literal-compatible-key"})
    assert literal.status_code == 200
    assert literal.json()["secret_ref"] is None and not literal.json()["enabled"]
    assert literal.json()["security_revision"] == 2
    reference = client.put(url + "?verify_before_save=true", headers=tokens["admin"], json={"tenant_id": "tenant_a", "secret_ref": "discovery", "enabled": True})
    assert reference.status_code == 200, reference.text
    assert reference.json()["security_revision"] == 3
    with Session(engine) as db:
        row = db.get(ModelConfig, model["id"])
        assert row.api_key_encrypted == "" and row.secret_ref == "discovery"
        resolve_model_config_for_runtime(db, "tenant_a", row.id)


def test_reference_migration_is_additive_and_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE model_configs (id VARCHAR PRIMARY KEY, api_key_encrypted VARCHAR, trust_status VARCHAR)"))
        conn.execute(text("INSERT INTO model_configs VALUES ('literal', 'existing-encrypted', 'verified')"))
        database._migrate_model_secret_references(conn, {"model_configs"})
        database._migrate_model_secret_references(conn, {"model_configs"})
        row = conn.execute(text("SELECT * FROM model_configs")).mappings().one()
        assert row["api_key_encrypted"] == "existing-encrypted" and row["trust_status"] == "verified"
        assert row["secret_ref"] is None and row["secret_ref_revision"] is None
    assert {"secret_ref", "secret_ref_revision"} <= {col["name"] for col in inspect(engine).get_columns("model_configs")}
    engine.dispose()


def test_binding_rotated_after_probes_cannot_be_committed_as_verified(native_api, monkeypatch):
    original = model_configs._run_verification_probes

    def rotate_after_probes(config):
        result = original(config)
        monkeypatch.setenv("R105_TEST_MODEL_KEY", "post-probe-rotation")
        return result

    monkeypatch.setattr(model_configs, "_run_verification_probes", rotate_after_probes)
    response = _create(native_api)
    assert response.status_code == 409 and response.json()["detail"] == "MODEL_VERIFICATION_STALE"
    with Session(native_api[1]) as db:
        assert db.exec(select(ModelConfig)).all() == []
