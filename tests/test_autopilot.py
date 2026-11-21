from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from studypilot import web
from studypilot.core import Config, StudyPilot
from studypilot.fake_notion import FakeNotion

SAMPLE = (Path(__file__).parent.parent / "examples" / "cs101_syllabus.txt").read_text()
TODAY = date(2026, 10, 1)


def test_autopilot_is_idempotent_for_items_and_goals(tmp_path):
    notion = FakeNotion()
    pilot = StudyPilot(notion, Config(), config_path=tmp_path / "config.json")
    pilot.bootstrap("parent")

    first = pilot.autopilot(SAMPLE, "hiking, reading, running", TODAY, year=2026)
    item_count = len(pilot.list_items())
    goal_count = len(pilot.list_goals())
    old_dashboard_ids = set(pilot.config.dashboard_blocks)
    assert first["found"] > 0
    assert first["created"] > 0 and first["skipped"] == 0
    assert first["goals_added"] and goal_count <= 3
    assert first["plan"]["sessions"]
    assert first["dashboard"] is True

    second = pilot.autopilot(SAMPLE, "hiking, reading, running", TODAY, year=2026)
    assert second["created"] == 0
    assert second["skipped"] == second["found"] == first["found"]
    assert second["goals_added"] == []
    assert len(pilot.list_items()) == item_count
    assert len(pilot.list_goals()) == goal_count
    current_dashboard_ids = set(pilot.config.dashboard_blocks)
    assert len(current_dashboard_ids) == len(old_dashboard_ids)
    assert not old_dashboard_ids & current_dashboard_ids


def test_autopilot_web_endpoint_bootstraps_demo_without_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYPILOT_DEMO", "1")
    monkeypatch.setenv("STUDYPILOT_CONFIG", str(tmp_path / "demo.json"))
    monkeypatch.setattr(web, "_pilot", None)
    client = TestClient(web.app)
    response = client.post(
        "/api/autopilot",
        json={
            "text": SAMPLE,
            "interests": "hiking",
            "today": TODAY.isoformat(),
            "year": 2026,
            "goals": 1,
        },
    )
    assert response.status_code == 200
    assert response.json()["found"] > 0
    assert response.json()["dashboard"] is True
