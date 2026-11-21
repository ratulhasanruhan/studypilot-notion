"""Balance Score: one number per week that says whether study and the rest of life fit together."""

from __future__ import annotations

from datetime import date, timedelta

from .models import Item, Plan


def label(score: int) -> str:
    return "Balanced" if score >= 75 else "Stretched" if score >= 50 else "Burnout risk"


def week_balance(plan: Plan, items: list[Item], start: date, daily_cap: float, today: date | None = None) -> dict:
    """Score the 7 days from `start` (0-100) and give one plain-language tip."""
    end = start + timedelta(days=7)
    first = max(start, today or start)
    days = [first + timedelta(days=i) for i in range((end - first).days)]
    study = {d: h for d, h in plan.hours_by_day("Study").items() if start <= d < end}
    life = {d: h for d, h in plan.hours_by_day("Life").items() if start <= d < end}
    study_h, life_h = round(sum(study.values()), 2), round(sum(life.values()), 2)
    exams = [i.title for i in items if i.type == "Exam" and i.status != "Done" and start <= i.due < end]
    due = {i.title: i.due for i in items}
    risky = [t for t in plan.at_risk if t in due and due[t] < end]
    rest_days = sum(1 for d in days if study.get(d, 0) == 0)

    load = study_h / max(daily_cap * len(days), 1e-6)
    share = life_h / (study_h + life_h) if study_h + life_h else 1.0
    score = 100.0
    if load > 0.5:
        score -= (load - 0.5) * 80
    if study_h and share < 0.2:
        score -= (0.2 - share) * 150
    score -= 10 * min(3, len(risky))
    if days and rest_days == 0:
        score -= 10
    if exams and not life_h:
        score -= 10
    score = int(round(max(0.0, min(100.0, score))))

    if risky:
        tip = f"{risky[0]} doesn't fit before its deadline. Raise hours/day or start it sooner."
    elif exams:
        tip = f"Exam week ({', '.join(exams)}): activities are lighter. Keep the short ones to stay fresh."
    elif study_h and share < 0.2:
        tip = "Almost no time for yourself. Add a life goal, even a 30-minute walk or a book."
    elif load > 0.85:
        tip = "Heavy study week. Protect your sleep and keep one evening free."
    elif days and rest_days == 0:
        tip = "No study-free day this week. Try to keep one."
    elif not life_h:
        tip = "Light week: a good time to start a new hobby or plan a hike."
    else:
        tip = "Good balance. Keep it up."
    return {
        "start": start.isoformat(),
        "score": score,
        "label": label(score),
        "study_hours": study_h,
        "life_hours": life_h,
        "rest_days": rest_days,
        "exams": exams,
        "at_risk": risky,
        "tip": tip,
    }


def weekly(plan: Plan, items: list[Item], today: date, daily_cap: float, weeks: int = 4) -> list[dict]:
    return [week_balance(plan, items, today + timedelta(weeks=w), daily_cap, today) for w in range(weeks)]
