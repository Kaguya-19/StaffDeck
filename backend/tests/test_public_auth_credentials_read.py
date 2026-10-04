from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlmodel import Session, SQLModel, create_engine

from app.api.auth import list_account_api_credentials
from app.db.models import Tenant, User


class AccountCredentialReadTests(unittest.TestCase):
    def test_discovery_does_not_create_or_flush_missing_account_client(self) -> None:
        engine = create_engine("sqlite://")
        SQLModel.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(Tenant(id="tenant", name="Tenant"))
            user = User(
                id="user",
                tenant_id="tenant",
                username="owner",
                role="admin",
                password_hash="unused",
            )
            db.add(user)
            db.commit()

            with patch("app.api.auth._ensure_account_api_client", side_effect=AssertionError("read path wrote")):
                rows = list_account_api_credentials(user, db)

            self.assertEqual(rows, [])
            self.assertEqual(list(db.new), [])
            self.assertEqual(list(db.dirty), [])


if __name__ == "__main__":
    unittest.main()
