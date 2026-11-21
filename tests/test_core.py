from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studypilot import web
from studypilot.core import Config, StudyPilot
from studypilot.fake_notion import FakeNotion
from studypilot.notion import extract_id
from studypilot.syllabus import parse_syllabus

SAMPLE = (Path(__file__).parent.parent / "examples" / "cs101_syllabus.txt").read_text()


@pytest.fixture
def pilot(tmp_path):
    p = StudyPilot(FakeNotion(), Config(timezone="Asia/Dhaka"), config_path=tmp_path / "cfg.json")
    p.bootstrap("parent")
    return p


def test_bootstrap_creates_linked_databases(pilot, tmp_path):
    dbs = pilot.notion.databases
    assert {d["title"] for d in dbs.values()} == {"Courses", "Assignments & Exams", "Study Sessions"}
    a = dbs[pilot.config.assignments_db]["properties"]
    assert a["Course"]["relation"]["database_id"] == pilot.config.courses_db
    assert Config.load(tmp_path / "cfg.json").ready


def test_import_is_idempotent_and_links_course(pilot):
    items = parse_syllabus(SAMPLE, year=2026)
    first = pilot.import_items(items)
    second = pilot.import_items(parse_syllabus(SAMPLE, year=2026))
    assert len(first["created"]) == len(items) and not first["skipped"]
    assert not second["created"] and len(second["skipped"]) == len(items)
    assert list(pilot.courses()) == ["CS 101"]
    assert all(i.course == "CS 101" for i in pilot.list_items())


def test_replan_replaces_future_sessions_and_keeps_done(pilot):
    pilot.import_items(parse_syllabus(SAMPLE, year=2026))
    today = date(2026, 10, 1)
    plan1 = pilot.replan(today)
    rows = pilot.notion.rows(pilot.config.sessions_db)
    assert len(rows) == len(plan1.sessions)
    assert rows[0]["properties"]["When"]["date"]["start"].endswith("+06:00")
    rows[0]["properties"]["Done"] = {"checkbox": True}
    plan2 = pilot.replan(today)
    live = pilot.notion.rows(pilot.config.sessions_db)
    assert len(live) == len(plan2.sessions) + 1
    assert sum(s.hours for s in plan2.sessions) < sum(s.hours for s in plan1.sessions)


def test_digest_publishes_page(pilot):
    pilot.import_items(parse_syllabus(SAMPLE, year=2026))
    d, url = pilot.digest(date(2026, 10, 10))
    assert [i.title for i in d.due_this_week] == ["Midterm Exam"]
    assert any(i.title == "Quiz 1" for i in d.overdue)
    assert url and url.startswith("https://www.notion.so/")


def test_extract_id():
    url = "https://www.notion.so/me/Student-OS-1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d?pvs=4"
    assert extract_id(url) == "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d"


def test_web_demo_flow(monkeypatch):
    monkeypatch.setenv("STUDYPILOT_DEMO", "1")
    monkeypatch.setattr(web, "_pilot", None)
    c = TestClient(web.app)
    assert c.get("/api/status").json()["demo"] is True
    assert c.post("/api/setup", json={"page": ""}).status_code == 200
    items = c.post("/api/parse", json={"text": SAMPLE, "year": 2026}).json()["items"]
    assert c.post("/api/import", json={"items": items}).json()["created"]
    plan = c.post("/api/plan", json={"today": "2026-10-01"}).json()
    assert plan["sessions"]
    dig = c.post("/api/digest", json={"today": "2026-10-10"}).json()
    assert "Midterm Exam" in dig["markdown"]
