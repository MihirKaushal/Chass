from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["PERSISTENCE_BACKEND"] = "sql"

from backend.db import reset_database_engine
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_path = tmp_path / "chass-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("TOKEN_SECRET", "test-only-secret")
    reset_database_engine()

    with TestClient(app) as test_client:
        yield test_client

    reset_database_engine()
