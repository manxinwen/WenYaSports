"""End-to-end test: full multi-agent pipeline through the HTTP API (no mocks)."""

import pytest
from fastapi.testclient import TestClient

from app.agents.coordinator_agent import CoordinatorAgent
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
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    db = str(tmp_path / "e2e.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db)
    return db


def make_real_coordinator():
    return CoordinatorAgent(
        parser_agent=ParserAgent(),
        feature_agent=FeatureExtractorAgent(),
        memory_agent=MemoryAgent(),
        recommendation_agent=RecommendationAgent(llm_enabled=False),
    )


def test_full_workflow_end_to_end(client, db_path, tmp_path):
    """上传 -> 列表 -> 详情(含轨迹点) -> 画像, 全链路真实执行, 不依赖 mock。"""
    fit_path = tmp_path / "run.fit"
    generate_fit(str(fit_path), n_records=120, sport="running")
    app.dependency_overrides[get_coordinator] = lambda: make_real_coordinator()

    # 1. 上传并分析
    with open(fit_path, "rb") as fh:
        resp = client.post(
            "/api/upload",
            files={"file": ("run.fit", fh, "application/octet-stream")},
            data={"user_id": "e2e_user", "session_id": "e2e_sess"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    activity_id = body["activity_id"]
    assert activity_id is not None
    assert body["metadata"]["sport"] == "running"
    assert body["metadata"]["total_distance_m"] > 0
    assert body["features"]["training_load"] > 0
    assert body["features"]["hr_zones"]
    assert body["recommendation"]["recovery_days"] >= 0
    assert "suggestion_text" in body["recommendation"]
    assert body["user_profile_summary"]

    # 2. 历史活动列表
    resp = client.get("/api/activities", params={"user_id": "e2e_user"})
    assert resp.status_code == 200
    activities = resp.json()["activities"]
    assert len(activities) == 1
    assert activities[0]["activity_id"] == activity_id

    # 3. 活动详情(重新解析轨迹点)
    resp = client.get(f"/api/activities/{activity_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["metadata"]["sport"] == "running"
    assert len(detail["records"]) == 120
    first = detail["records"][0]
    assert "lat" in first and "lon" in first and "hr" in first
    assert detail["features"]["total_distance_m"] > 0
    assert detail["recommendation"]["recovery_days"] >= 0

    # 4. 用户画像(含近 7 天训练负荷)
    resp = client.get("/api/user/profile", params={"user_id": "e2e_user"})
    assert resp.status_code == 200
    profile = resp.json()["profile"]
    assert profile.get("avg_load_7d", 0) > 0
