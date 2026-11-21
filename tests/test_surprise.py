import random
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from studypilot import web
from studypilot.core import Config, StudyPilot
from studypilot.fake_notion import FakeNotion
from studypilot.life import LifeConfig, surprise
from studypilot.models import Plan, Session


def test_surprise_is_seeded_and_avoids_scheduled_sessions():
    today = date.today() + timedelta(days=10)
    weeks = [{"label": "Balanced"}]
    empty = Plan(weeks=weeks)
    idea = surprise(empty, today, LifeConfig(), rng=random.Random(42), interests="hiking")
    repeated = surprise(empty, today, LifeConfig(), rng=random.Random(42), interests="hiking")
    assert idea == repeated
    assert idea and idea["why"].endswith("next week is Balanced.")

    start = datetime.fromisoformat(idea["start"])
    blocked = Plan(
        sessions=[Session("Study block", start, idea["hours"], kind="Study")],
        weeks=weeks,
    )
    alternative = surprise(blocked, today, LifeConfig(), rng=random.Random(42), interests="hiking")
    assert alternative
    alternative_start = datetime.fromisoformat(alternative["start"])
    alternative_end = datetime.fromisoformat(alternative["end"])
    assert not (alternative_start < start + timedelta(hours=idea["hours"]) and alternative_end > start)
    if alternative["hours"] > 0.5:
        assert blocked.hours_by_day("Study").get(alternative_start.date(), 0) < LifeConfig().daily_cap


def test_surprise_schedule_row_survives_replan(tmp_path):
    notion = FakeNotion()
    pilot = StudyPilot(notion, Config(), config_path=tmp_path / "config.json")
    pilot.bootstrap("parent")
    start = datetime.combine(date.today() + timedelta(days=10), datetime.min.time().replace(hour=7), tzinfo=pilot.config.tz)
    idea = {
        "emoji": "🌄",
        "title": "Sunrise hilltop hike",
        "hours": 3,
        "start": start.isoformat(),
        "end": (start + timedelta(hours=3)).isoformat(),
    }

    page_id = pilot.add_surprise(idea)
    pilot.replan(start.date() - timedelta(days=1))
    row = notion.pages[page_id]
    assert not row["archived"]
    assert row["properties"]["Planned by"]["select"]["name"] == "Surprise"
    options = notion.databases[pilot.config.sessions_db]["properties"]["Planned by"]["select"]["options"]
    assert "Surprise" in [option["name"] for option in options]


def test_surprise_web_endpoints_work_without_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYPILOT_DEMO", "1")
    monkeypatch.setenv("STUDYPILOT_CONFIG", str(tmp_path / "demo.json"))
    monkeypatch.setattr(web, "_pilot", None)
    client = TestClient(web.app)
    today = (date.today() + timedelta(days=10)).isoformat()

    response = client.post("/api/surprise", json={"today": today, "seed": 8, "interests": "hiking"})
    assert response.status_code == 200
    idea = response.json()["idea"]
    assert idea and idea["title"]
    added = client.post("/api/surprise/add", json={"idea": idea})
    assert added.status_code == 200 and added.json() == {"ok": True}
