from datetime import date, datetime, timedelta
import json

from fastapi.testclient import TestClient

from studypilot import web
from studypilot.core import Config, StudyPilot
from studypilot.dashboard import dashboard_blocks
from studypilot.fake_notion import FakeNotion
from studypilot.models import Goal, Item, Plan, Session

TODAY = date(2026, 11, 23)


def _plan():
    weeks = [
        {
            "start": (TODAY + timedelta(weeks=index)).isoformat(),
            "score": 90 - index,
            "label": "Balanced" if index == 0 else "Stretched",
            "study_hours": 10.5,
            "life_hours": 4,
            "tip": "Good balance. Keep it up.",
        }
        for index in range(4)
    ]
    return Plan(
        sessions=[
            Session("Homework 3", datetime(2026, 11, 23, 18, 0), 1.5),
            Session("Run", datetime(2026, 11, 23, 7, 30), 0.75, kind="Life", label="Run"),
        ],
        weeks=weeks,
    )


def _plain(block):
    return "".join(part["text"]["content"] for part in block.get("rich_text", []))


def _plain_cell(cell):
    return "".join(part["text"]["content"] for part in cell)


def test_dashboard_blocks_cover_balance_schedule_due_dates_and_goals():
    items = [
        Item("Problem Set 7", TODAY, type="Assignment", course="MAT 216"),
        Item("Done item", TODAY + timedelta(days=1), status="Done"),
        Item("Last included", TODAY + timedelta(days=13)),
        Item("Outside range", TODAY + timedelta(days=14)),
        Item("Overdue", TODAY - timedelta(days=1)),
    ]
    goals = [
        Goal(
            "Half-marathon training",
            template="half-marathon",
            sessions_per_week=3,
            hours=0.75,
            time="Morning",
            target="City Half",
        ),
        Goal("Read for fun", template="reading", sessions_per_week=5, hours=0.5, time="Evening", status="Paused"),
    ]
    blocks = dashboard_blocks(
        _plan(),
        items,
        goals,
        TODAY,
        {"courses": "courses-id", "assignments": "assignments-id", "goals": "goals-id", "sessions": "sessions-id"},
    )

    balance = blocks[4]["column_list"]["children"]
    assert len(balance) == 4
    assert all(column["column"]["children"][0]["type"] == "callout" for column in balance)
    schedule = blocks[6]["table"]
    assert schedule["table_width"] == 3 and schedule["has_column_header"] is True
    assert len(schedule["children"]) == 8
    assert _plain_cell(schedule["children"][0]["table_row"]["cells"][0]) == "Day"
    assert _plain_cell(schedule["children"][1]["table_row"]["cells"][1]) == "18:00 Work on: Homework 3 (90 min)"
    assert _plain_cell(schedule["children"][1]["table_row"]["cells"][2]) == "07:30 Run (45 min)"

    columns = blocks[7]["column_list"]["children"]
    due_blocks = columns[0]["column"]["children"][1:]
    due_text = [_plain(block["to_do"]) for block in due_blocks]
    assert due_text == [
        "Mon Nov 23 · Problem Set 7 (Assignment, MAT 216)",
        "Sun Dec 06 · Last included (Assignment)",
    ]
    goal_blocks = columns[1]["column"]["children"][1:]
    goal_text = [_plain(block["bulleted_list_item"]) for block in goal_blocks]
    assert "🏃 Half-marathon training · 3x a week, 45 min, mornings · City Half" in goal_text
    assert "📖 Read for fun · 5x a week, 30 min, evenings (paused)" in goal_text


def test_dashboard_refresh_replaces_blocks_and_respects_anchor_or_end(tmp_path):
    notion = FakeNotion()
    pilot = StudyPilot(notion, Config(), config_path=tmp_path / "config.json")
    pilot.bootstrap("parent")
    anchor, tail = notion.append_children(
        "parent",
        [
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}},
        ],
    )

    first_ids = pilot.dashboard(TODAY, after=anchor)
    children = notion.children["parent"]
    assert children[1]["id"] == first_ids[0]
    assert children[1 + len(first_ids)]["id"] == tail

    second_ids = pilot.dashboard(TODAY)
    children = notion.children["parent"]
    child_ids = {block["id"] for block in children}
    assert len(second_ids) == len(first_ids)
    assert not set(first_ids) & child_ids
    assert children[1]["id"] == second_ids[0]
    assert Config.load(tmp_path / "config.json").dashboard_blocks == second_ids

    end_ids = pilot.dashboard(TODAY, after="top")
    children = notion.children["parent"]
    child_ids = {block["id"] for block in children}
    assert not set(second_ids) & child_ids
    assert [block["id"] for block in children[-len(end_ids):]] == end_ids


def test_old_config_defaults_and_demo_dashboard_endpoint(tmp_path, monkeypatch):
    config_path = tmp_path / "old.json"
    config_path.write_text(json.dumps({"parent_page_id": "parent", "courses_db": "courses"}))
    old_config = Config.load(config_path)
    assert old_config.dashboard_after == ""
    assert old_config.dashboard_blocks == []

    monkeypatch.setenv("STUDYPILOT_DEMO", "1")
    monkeypatch.setenv("STUDYPILOT_CONFIG", str(tmp_path / "demo.json"))
    monkeypatch.setattr(web, "_pilot", None)
    client = TestClient(web.app)
    response = client.post("/api/dashboard", json={"today": TODAY.isoformat()})
    assert response.status_code == 200
    assert response.json()["blocks"] > 0
