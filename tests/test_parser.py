import pytest

from app.agents.parser_agent import ParserAgent
from app.models.activity import ParsedActivity
from app.services.fit_parser import FitParseError, parse_fit_file
from tests.fit_gen import generate_fit


@pytest.fixture()
def sample_fit(tmp_path):
    path = tmp_path / "sample.fit"
    generate_fit(str(path), n_records=200)
    return str(path)


def test_parse_fit_file_returns_metadata_and_records(sample_fit):
    data = parse_fit_file(sample_fit)
    assert "metadata" in data
    assert "records" in data
    assert len(data["records"]) > 0


def test_parse_fit_file_maps_field_names(sample_fit):
    data = parse_fit_file(sample_fit)
    for key in ("timestamp", "lat", "lon", "hr", "speed", "alt", "distance", "power"):
        assert key in data["records"][0]
    assert data["records"][0]["lat"] is not None
    assert -90 <= data["records"][0]["lat"] <= 90
    assert -180 <= data["records"][0]["lon"] <= 180


def test_parse_fit_file_metadata_from_session(sample_fit):
    data = parse_fit_file(sample_fit)
    meta = data["metadata"]
    assert meta["sport"] == "running"
    assert meta["total_timer_time"] > 0
    assert meta["total_distance"] > 0
    assert meta["avg_heart_rate"] is not None
    assert meta["max_heart_rate"] is not None
    assert meta["total_ascent"] >= 0
    assert meta["total_descent"] >= 0


def test_parse_fit_file_without_session(tmp_path):
    path = tmp_path / "no_session.fit"
    generate_fit(str(path), n_records=50, with_session=False)
    data = parse_fit_file(str(path))
    assert data["metadata"]["sport"] == "unknown"
    assert data["metadata"]["total_timer_time"] > 0
    assert data["metadata"]["total_distance"] > 0
    assert len(data["records"]) == 50


def test_parser_agent_returns_parsed_activity(sample_fit):
    agent = ParserAgent()
    activity = agent.run(sample_fit)
    assert isinstance(activity, ParsedActivity)
    assert activity.metadata.sport == "running"
    assert len(activity.records) == 200
    assert activity.records[0].hr is not None
    assert activity.records[0].lat is not None


def test_parse_fit_file_missing_file(tmp_path):
    with pytest.raises(FitParseError):
        parse_fit_file(str(tmp_path / "nope.fit"))
