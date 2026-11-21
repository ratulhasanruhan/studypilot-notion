from datetime import date, datetime

from studypilot.balance import label, week_balance
from studypilot.models import Item, Plan, Session

MON = date(2026, 11, 2)


def sess(day, hours, kind="Study"):
    return Session("x", datetime(2026, 11, day, 18), hours, kind=kind)


def test_balanced_week_scores_high():
    plan = Plan([sess(d, 1.5) for d in (2, 3, 4, 5, 6)] + [sess(7, 3, "Life"), sess(3, 0.75, "Life")])
    b = week_balance(plan, [], MON, 3)
    assert b["label"] == "Balanced" and b["score"] >= 90
    assert b["study_hours"] == 7.5 and b["life_hours"] == 3.75 and b["rest_days"] == 2


def test_overloaded_week_without_life_is_burnout_risk():
    plan = Plan([sess(d, 3) for d in range(2, 9)], at_risk={"Project": 4})
    items = [Item("Project", date(2026, 11, 7), "Project"), Item("Midterm", date(2026, 11, 6), "Exam")]
    b = week_balance(plan, items, MON, 3)
    assert b["label"] == "Burnout risk"
    assert b["at_risk"] == ["Project"] and b["exams"] == ["Midterm"]
    assert b["tip"].startswith("Project doesn't fit")


def test_labels():
    assert [label(s) for s in (80, 60, 20)] == ["Balanced", "Stretched", "Burnout risk"]
