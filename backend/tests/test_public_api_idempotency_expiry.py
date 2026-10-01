from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import Request
from sqlmodel import Session, SQLModel, create_engine, select

from app.db.models import APIIdempotencyRecord, User
from app.public_api import idempotency
from app.public_api.auth import PublicPrincipal
from app.public_api.errors import PublicAPIError


@pytest.fixture
def persisted_request(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'idempotency.sqlite'}")
    SQLModel.metadata.create_all(engine)
    principal = PublicPrincipal("tenant", User(id="actor", tenant_id="tenant", username="actor", password_hash="unused"),
                                frozenset({"runs:create"}), credential_id="credential")
    request = Request({"type": "http", "method": "POST", "path": "/runs", "scheme": "http",
                       "server": ("localhost", 80), "query_string": b"",
                       "headers": [(b"idempotency-key", b"same-request")]})
    clock = {"now": datetime(2026, 10, 1, tzinfo=UTC)}
    monkeypatch.setattr(idempotency, "utc_now", lambda: clock["now"])
    monkeypatch.setattr(idempotency, "get_settings", lambda: SimpleNamespace(public_api_idempotency_ttl_seconds=30))
    with Session(engine) as db:
        idempotency.store_idempotent_response(db, principal, request, {"prompt": "original"},
                                             {"id": "original-run"}, status_code=201)
    yield engine, principal, request, clock
    engine.dispose()


@pytest.mark.parametrize("elapsed,expired", [(29, False), (30, True), (31, True)])
def test_persisted_expiry_boundary(persisted_request, elapsed, expired):
    engine, principal, request, clock = persisted_request
    clock["now"] += timedelta(seconds=elapsed)
    # Use a new Session: this exercises the database timestamp decoder, not an in-memory row.
    with Session(engine) as db:
        result = idempotency.replay_idempotent_response(db, principal, request, {"prompt": "original"})
        assert result == (None if expired else (201, {"id": "original-run"}))
    with Session(engine) as db:
        assert len(db.exec(select(APIIdempotencyRecord)).all()) == (0 if expired else 1)


def test_repeated_replay_preserves_original_record(persisted_request):
    engine, principal, request, clock = persisted_request
    with Session(engine) as db:
        original = db.exec(select(APIIdempotencyRecord)).one()
        original_id, expiry = original.id, original.expires_at
    for _ in range(2):
        with Session(engine) as db:
            assert idempotency.replay_idempotent_response(db, principal, request, {"prompt": "original"}) == (201, {"id": "original-run"})
    with Session(engine) as db:
        row = db.exec(select(APIIdempotencyRecord)).one()
        assert (row.id, row.expires_at) == (original_id, expiry)


def test_unexpired_changed_payload_conflicts_without_replacing_record(persisted_request):
    engine, principal, request, clock = persisted_request
    with Session(engine) as db:
        with pytest.raises(PublicAPIError) as error:
            idempotency.replay_idempotent_response(db, principal, request, {"prompt": "changed"})
        assert error.value.status_code == 409
        assert error.value.code == "IDEMPOTENCY_CONFLICT"
    with Session(engine) as db:
        assert db.exec(select(APIIdempotencyRecord)).one().response_json == {"id": "original-run"}


def test_expired_key_can_be_reused_and_replayed_after_reopen(persisted_request):
    engine, principal, request, clock = persisted_request
    clock["now"] += timedelta(seconds=30)
    with Session(engine) as db:
        assert idempotency.replay_idempotent_response(db, principal, request, {"prompt": "changed"}) is None
        idempotency.store_idempotent_response(db, principal, request, {"prompt": "changed"},
                                             {"id": "new-run"}, status_code=202)
    with Session(engine) as db:
        assert idempotency.replay_idempotent_response(db, principal, request, {"prompt": "changed"}) == (202, {"id": "new-run"})
        assert len(db.exec(select(APIIdempotencyRecord)).all()) == 1
