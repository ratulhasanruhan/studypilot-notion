from datetime import date

from studypilot.models import Item
from studypilot.planner import PlannerConfig, plan_sessions

TODAY = date(2026, 11, 2)


def test_hours_scheduled_before_deadline_and_capped():
    items = [
        Item("Midterm", date(2026, 11, 12), "Exam", hours=8),
        Item("HW 4", date(2026, 11, 6), "Assignment", hours=4),
    ]
    plan = plan_sessions(items, TODAY, PlannerConfig(daily_cap=3))
    assert not plan.at_risk
    for item in items:
        sess = [s for s in plan.sessions if s.item_title == item.title]
        assert abs(sum(s.hours for s in sess) - item.hours) < 1e-6
        assert all(TODAY <= s.start.date() < item.due for s in sess)
    assert max(plan.hours_by_day().values()) <= 3 + 1e-6


def test_sessions_on_same_day_do_not_overlap():
    items = [Item("A", date(2026, 11, 4), hours=3), Item("B", date(2026, 11, 4), hours=3)]
    plan = plan_sessions(items, TODAY, PlannerConfig(daily_cap=3, block_hours=1.5))
    by_day = {}
    for s in plan.sessions:
        by_day.setdefault(s.start.date(), []).append(s)
    for sessions in by_day.values():
        sessions.sort(key=lambda s: s.start)
        for a, b in zip(sessions, sessions[1:]):
            assert a.end <= b.start


def test_reports_at_risk_when_not_enough_time():
    plan = plan_sessions([Item("Cram", date(2026, 11, 3), "Exam", hours=8)], TODAY, PlannerConfig(daily_cap=3))
    assert plan.at_risk == {"Cram": 5.0}


def test_skips_done_past_and_completed_hours():
    items = [
        Item("Done one", date(2026, 11, 10), status="Done"),
        Item("Past", date(2026, 10, 1)),
        Item("Half done", date(2026, 11, 10), hours=4),
    ]
    plan = plan_sessions(items, TODAY, done_hours={"Half done": 2.5})
    assert {s.item_title for s in plan.sessions} == {"Half done"}
    assert sum(s.hours for s in plan.sessions) == 1.5


def test_respects_study_weekdays():
    cfg = PlannerConfig(study_weekdays={0, 2, 4})
    plan = plan_sessions([Item("HW", date(2026, 11, 9), hours=4)], TODAY, cfg)
    assert all(s.start.weekday() in {0, 2, 4} for s in plan.sessions)
