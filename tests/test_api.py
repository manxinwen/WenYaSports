"""Tests for the FastAPI routes (prompt 7)."""

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from app.agents.coordinator_agent import CoordinatorAgent, CoordinatorError
from app.agents.feature_extractor_agent import FeatureExtractorAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.parser_agent import ParserAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.api.routes import get_coordinator
from app.db import database
from app.main import app
from tests.fit_gen import generate_fit


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_dependency_overrides():
    """Make sure a failing test does not leak dependency overrides."""
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_fit(tmp_path):
    path = tmp_path / "sample.fit"
    generate_fit(str(path), n_records=50)
    return str(path)


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Point every DB access (memory agent + routes) at a temp database."""
    db = str(tmp_path / "api.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db)
    return db


def make_real_coordinator():
    return CoordinatorAgent(
        parser_agent=ParserAgent(),
        feature_agent=FeatureExtractorAgent(),
        memory_agent=MemoryAgent(),
        recommendation_agent=RecommendationAgent(llm_enabled=False),
    )


def upload(client, path, user_id="u1", session_id="s1", filename=None):
    with open(path, "rb") as fh:
        return client.post(
            "/api/upload",
            files={
                "file": (
                    filename or "activity.fit",
                    fh,
                    "application/octet-stream",
                )
            },
            data={"user_id": user_id, "session_id": session_id},
        )


def test_upload_with_real_pipeline(client, sample_fit, db_path):
    app.dependency_overrides[get_coordinator] = lambda: make_real_coordinator()
    resp = upload(client, sample_fit, "u1", "s1")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["activity_id"] is not None
    assert body["metadata"]["sport"] == "running"
    assert body["features"]["training_load"] > 0
    assert body["recommendation"]["recovery_days"] >= 0
    assert "user_profile_summary" in body


def test_upload_rejects_non_fit_file(client):
    app.dependency_overrides[get_coordinator] = lambda: mock.MagicMock()
    resp = client.post(
        "/api/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"user_id": "u", "session_id": "s"},
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_upload_coordinator_parse_error(client, sample_fit):
    coord = mock.MagicMock()
    coord.run.side_effect = CoordinatorError("invalid fit", status_code=400)
    app.dependency_overrides[get_coordinator] = lambda: coord
    resp = upload(client, sample_fit)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid fit"


def test_upload_coordinator_internal_error(client, sample_fit):
    coord = mock.MagicMock()
    coord.run.side_effect = ValueError("boom")
    app.dependency_overrides[get_coordinator] = lambda: coord
    resp = upload(client, sample_fit)
    assert resp.status_code == 500
    assert "detail" in resp.json()


def test_list_activities_and_profile(client, sample_fit, db_path):
    app.dependency_overrides[get_coordinator] = lambda: make_real_coordinator()
    upload(client, sample_fit, "u2", "s2")

    resp = client.get("/api/activities", params={"user_id": "u2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    act = body["activities"][0]
    assert act["activity_id"] is not None
    assert act["sport"] == "running"
    assert act["training_load"] > 0

    profile_resp = client.get("/api/user/profile", params={"user_id": "u2"})
    assert profile_resp.status_code == 200
    profile = profile_resp.json()["profile"]
    assert profile.get("avg_load_7d", 0) > 0


def test_activity_detail_returns_records(client, sample_fit, db_path):
    app.dependency_overrides[get_coordinator] = lambda: make_real_coordinator()
    upload(client, sample_fit, "u3", "s3")

    aid = client.get("/api/activities", params={"user_id": "u3"}).json()["activities"][0][
        "activity_id"
    ]
    resp = client.get(f"/api/activities/{aid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["sport"] == "running"
    assert body["features"]["training_load"] > 0
    assert body["recommendation"]["recovery_days"] >= 0
    assert len(body["records"]) == 50
    assert "lat" in body["records"][0]
    assert "hr" in body["records"][0]


def test_activity_not_found(client):
    resp = client.get("/api/activities/999999")
    assert resp.status_code == 404
    assert "detail" in resp.json()
