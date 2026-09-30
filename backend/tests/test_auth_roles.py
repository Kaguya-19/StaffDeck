from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
import pytest

from app.api.auth import (
    LoginRequest,
    UserCreateRequest,
    UserUpdateRequest,
    create_user,
    login,
    update_user,
)
from app.db.models import Tenant, User
from app.security.auth import hash_password
from app.security.auth import create_access_token, get_current_user


def test_unknown_login_does_not_create_account() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        db.commit()

        try:
            login(LoginRequest(tenant_id="tenant_demo", username="missing", password="secret"), db=db)
        except HTTPException as error:
            assert error.status_code == 401
            assert error.detail == "Invalid username or password"
        else:
            raise AssertionError("unknown account must not be created during login")

        assert db.exec(select(User)).all() == []


def test_database_role_controls_account_management() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        member_named_admin = User(
            id="user_named_admin",
            tenant_id="tenant_demo",
            username="admin",
            role="member",
            password_hash=hash_password("secret"),
        )
        role_admin = User(
            id="user_role_admin",
            tenant_id="tenant_demo",
            username="ops",
            role="admin",
            password_hash=hash_password("secret"),
        )
        db.add(member_named_admin)
        db.add(role_admin)
        db.commit()

        try:
            create_user(
                UserCreateRequest(tenant_id="tenant_demo", username="blocked", password="secret"),
                member_named_admin,
                db,
            )
        except HTTPException as error:
            assert error.status_code == 403
        else:
            raise AssertionError("an admin-looking username must not grant administrator access")

        created = create_user(
            UserCreateRequest(
                tenant_id="tenant_demo",
                username="created_admin",
                password="secret",
                role="admin",
            ),
            role_admin,
            db,
        )
        assert created.role == "admin"

        updated = update_user(
            created.id,
            UserUpdateRequest(tenant_id="tenant_demo", role="member"),
            role_admin,
            db,
        )
        assert updated.role == "member"


def test_admin_password_update_allows_login_with_unique_display_name() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        admin = User(
            id="admin",
            tenant_id="tenant_demo",
            username="admin",
            role="admin",
            password_hash=hash_password("admin"),
        )
        member = User(
            id="user_demo",
            tenant_id="tenant_demo",
            username="user_demo",
            display_name="zongkelong",
            role="member",
            password_hash=hash_password("old-password"),
        )
        db.add(admin)
        db.add(member)
        db.commit()

        update_user(
            member.id,
            UserUpdateRequest(tenant_id="tenant_demo", password="123456"),
            admin,
            db,
        )

        session = login(
            LoginRequest(tenant_id="tenant_demo", username="zongkelong", password="123456"),
            db=db,
        )

        assert session.user.id == member.id
        assert session.user.username == "user_demo"


def test_duplicate_display_name_cannot_be_used_to_login() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        db.add(
            User(
                id="member_one",
                tenant_id="tenant_demo",
                username="member_one",
                display_name="duplicate",
                password_hash=hash_password("123456"),
            )
        )
        db.add(
            User(
                id="member_two",
                tenant_id="tenant_demo",
                username="member_two",
                display_name="duplicate",
                password_hash=hash_password("123456"),
            )
        )
        db.commit()

        try:
            login(
                LoginRequest(tenant_id="tenant_demo", username="duplicate", password="123456"),
                db=db,
            )
        except HTTPException as error:
            assert error.status_code == 401
            assert error.detail == "Invalid username or password"
        else:
            raise AssertionError("an ambiguous display name must not authenticate any account")


def test_admin_disable_blocks_login_and_existing_token_then_reenable_restores_access() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        admin = User(id="admin", tenant_id="tenant_demo", username="admin", role="admin", password_hash=hash_password("admin"))
        member = User(id="member", tenant_id="tenant_demo", username="member", role="member", password_hash=hash_password("secret"))
        db.add(admin)
        db.add(member)
        db.commit()
        old_token = create_access_token(member)

        updated = update_user(member.id, UserUpdateRequest(tenant_id="tenant_demo", disabled=True), admin, db)
        assert updated.disabled is True
        with pytest.raises(HTTPException) as login_error:
            login(LoginRequest(tenant_id="tenant_demo", username="member", password="secret"), db=db)
        assert login_error.value.status_code == 403
        assert login_error.value.detail["code"] == "USER_DISABLED"
        with pytest.raises(HTTPException) as token_error:
            get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=old_token), db=db)
        assert token_error.value.status_code == 403
        assert token_error.value.detail["code"] == "USER_DISABLED"

        update_user(member.id, UserUpdateRequest(tenant_id="tenant_demo", disabled=False), admin, db)
        restored = login(LoginRequest(tenant_id="tenant_demo", username="member", password="secret"), db=db)
        assert restored.user.disabled is False


def test_only_same_tenant_admin_can_change_disabled_state() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_a", name="A"))
        db.add(Tenant(id="tenant_b", name="B"))
        admin_a = User(id="admin_a", tenant_id="tenant_a", username="admin", role="admin", password_hash=hash_password("secret"))
        admin_b = User(id="admin_b", tenant_id="tenant_b", username="admin", role="admin", password_hash=hash_password("secret"))
        member = User(id="member_a", tenant_id="tenant_a", username="member", role="member", password_hash=hash_password("secret"))
        db.add(admin_a)
        db.add(admin_b)
        db.add(member)
        db.commit()
        with pytest.raises(HTTPException) as cross_tenant:
            update_user(member.id, UserUpdateRequest(tenant_id="tenant_a", disabled=True), admin_b, db)
        assert cross_tenant.value.status_code == 403
        with pytest.raises(HTTPException) as ordinary:
            update_user(member.id, UserUpdateRequest(tenant_id="tenant_a", disabled=True), member, db)
        assert ordinary.value.status_code == 403
        assert db.get(User, member.id).disabled is False


def _test_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)
