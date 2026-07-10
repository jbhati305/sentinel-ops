from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.container import _build_database, build_container
from backend.app.main import create_app
from backend.app.repositories import PostgresDatabase, SqliteDatabase


def test_build_database_uses_sqlite_by_default(tmp_path):
    settings = Settings(database_url=None)
    db = _build_database(settings, str(tmp_path / "sentinel_ops.sqlite3"))
    assert isinstance(db, SqliteDatabase)


def test_build_database_uses_postgres_when_database_url_set(tmp_path):
    settings = Settings(database_url="postgresql://user:pass@localhost:5432/sentinelops")
    db = _build_database(settings, str(tmp_path / "sentinel_ops.sqlite3"))
    assert isinstance(db, PostgresDatabase)
    assert db.database_url == "postgresql://user:pass@localhost:5432/sentinelops"


@pytest.fixture
def client(tmp_path):
    app = create_app(database_path=str(tmp_path / "sentinel_ops_control.sqlite3"), start_simulator=False)
    with TestClient(app) as test_client:
        yield test_client


def test_control_page_smoke(client):
    response = client.get("/control")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SentinelOps Control" in response.text
    assert "http://localhost:3001" in response.text
    assert "/docs" in response.text
    assert "/api/v1/simulation/inject" in response.text
