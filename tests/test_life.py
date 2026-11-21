from datetime import date

import pytest

from studypilot.core import Config, StudyPilot
from studypilot.fake_notion import FakeNotion
from studypilot.life import TEMPLATES, LifeConfig, match_templates, plan_life, suggest
from studypilot.models import Item
from studypilot.planner import plan_sessions

TODAY = date(2026, 11, 2)  # Monday


def test_match_and_suggest():
    assert match_templates("I want to run a half marathon") == ["half-marathon"]
    assert "hiking" in match_templates("hiking and trekking")
    s = suggest("hiking, marathon, sci-fi books", study_hours_next_week=8)
    keys = [x["template"] for x in s]
    assert keys[:3] == ["half-marathon", "hiking", "reading"]
    reading = next(x for x in s if x["template"] == "reading")
    assert "Dune - Frank Herbert" in reading["books"]


def test_suggest_pads_with_balanced_defaults_and_flags_busy_weeks():
    s = suggest("", study_hours_next_week=20, daily_cap=3)
    assert s[0]["template"] == "meditation"
    assert "Busy week" in s[0]["why"]


def test_life_sessions_avoid_study_and_progress():
    goals = [TEMPLATES["half-marathon"].goal(), TEMPLATES["reading"].goal("Dune")]
    goals[0].start = TODAY
    study = plan_sessions([Item("HW", date(2026, 11, 20), hours=4)], TODAY)
    life, light = plan_life(goals, TODAY, study, cfg=LifeConfig(weeks=3))
    assert not light
    long_runs = [s.title for s in life if "Long run" in s.title]
    assert long_runs == ["\U0001F3C3 Long run: 6 km", "\U0001F3C3 Long run: 7.5 km", "\U0001F3C3 Long run: 9 km"]
    for s in life:
        for st in study.sessions:
            assert s.end <= st.start or s.start >= st.end
    assert all(s.kind == "Life" for s in life)
    assert any(s.title == "\U0001F4D6 Read: Dune (30 min)" for s in life)


def test_exam_week_is_light():
    goals = [TEMPLATES["hiking"].goal(), TEMPLATES["gym"].goal()]
    items = [Item("Midterm", date(2026, 11, 6), "Exam")]
    study = plan_sessions(items, TODAY)
    life, light = plan_life(goals, TODAY, study, items, LifeConfig(weeks=2))
    assert date(2026, 11, 2) in light
    week1 = [s for s in life if s.start.date() < date(2026, 11, 9)]
    week2 = [s for s in life if s.start.date() >= date(2026, 11, 9)]
    assert any("Easy nature walk" in s.title for s in week1)
    assert sum(1 for s in week1 if "Gym" in s.title) == 2
    assert sum(1 for s in week2 if "Gym" in s.title) == 3


def test_paused_goals_are_not_scheduled():
    g = TEMPLATES["gym"].goal()
    g.status = "Paused"
    assert plan_life([g], TODAY, plan_sessions([], TODAY))[0] == []


@pytest.fixture
def pilot(tmp_path):
    p = StudyPilot(FakeNotion(), Config(timezone="Asia/Dhaka"), config_path=tmp_path / "cfg.json")
    p.bootstrap("parent")
    return p


def test_goal_roundtrip_and_replan_writes_life_sessions(pilot):
    pilot.add_goal("hiking", today=TODAY)
    pilot.add_goal("reading", "Dune", today=TODAY, sessions_per_week=3)
    goals = {g.title: g for g in pilot.list_goals()}
    assert goals["Read for fun"].sessions_per_week == 3 and goals["Read for fun"].target == "Dune"
    assert goals["Weekend hikes"].days == [5, 6]
    plan = pilot.replan(TODAY)
    rows = pilot.notion.rows(pilot.config.sessions_db)
    life_rows = [r for r in rows if r["properties"]["Kind"]["select"]["name"] == "Life"]
    assert life_rows and len(rows) == len(plan.sessions)
    assert all(r["properties"]["Goal"]["relation"] for r in life_rows)
    pilot.set_goal_status("weekend hikes", "Paused")
    plan2 = pilot.replan(TODAY)
    assert not any("Hike" in s.title for s in plan2.sessions)


def test_upgrade_adds_life_goals_to_existing_setup(tmp_path):
    p = StudyPilot(FakeNotion(), Config(), config_path=tmp_path / "c.json")
    p.bootstrap("parent")
    p.config.goals_db = ""
    p.ensure_life()
    assert p.config.goals_db and Config.load(tmp_path / "c.json").goals_db == p.config.goals_db


def test_flexible_goals_avoid_crowded_days():
    goals = [TEMPLATES["hiking"].goal(), TEMPLATES["half-marathon"].goal()]
    life, _ = plan_life(goals, TODAY, plan_sessions([], TODAY), cfg=LifeConfig(weeks=1))
    hike = next(s for s in life if "hike" in s.title.lower())
    assert hike.start.weekday() == 6  # Saturday has the long run
