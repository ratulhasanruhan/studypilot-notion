"""Notion database schemas for the StudyPilot Student OS."""

TYPES = ["Assignment", "Exam", "Quiz", "Project", "Lab", "Reading"]
STATUSES = ["Not started", "In progress", "Done"]

COURSES = {
    "Name": {"title": {}},
    "Code": {"rich_text": {}},
}


def assignments(courses_db: str) -> dict:
    return {
        "Name": {"title": {}},
        "Course": {"relation": {"database_id": courses_db, "single_property": {}}},
        "Type": {"select": {"options": [{"name": t} for t in TYPES]}},
        "Due": {"date": {}},
        "Status": {"select": {"options": [{"name": s} for s in STATUSES]}},
        "Est. Hours": {"number": {"format": "number"}},
        "Source": {"select": {"options": [{"name": "Syllabus"}, {"name": "Manual"}]}},
    }


def sessions(assignments_db: str) -> dict:
    return {
        "Name": {"title": {}},
        "Assignment": {"relation": {"database_id": assignments_db, "single_property": {}}},
        "When": {"date": {}},
        "Hours": {"number": {"format": "number"}},
        "Done": {"checkbox": {}},
        "Planned by": {"select": {"options": [{"name": "StudyPilot"}, {"name": "Surprise"}, {"name": "Me"}]}},
    }


def goals() -> dict:
    from .life import CATEGORIES, DAY_NAMES, TIMES

    return {
        "Name": {"title": {}},
        "Category": {"select": {"options": [{"name": c} for c in CATEGORIES]}},
        "Template": {"rich_text": {}},
        "Sessions/Week": {"number": {"format": "number"}},
        "Hours/Session": {"number": {"format": "number"}},
        "Days": {"multi_select": {"options": [{"name": d} for d in DAY_NAMES]}},
        "Time": {"select": {"options": [{"name": t} for t in TIMES]}},
        "Status": {"select": {"options": [{"name": s} for s in ["Active", "Paused", "Done"]]}},
        "Target": {"rich_text": {}},
        "Started": {"date": {}},
    }


def schedule_life_props(goals_db: str) -> dict:
    return {
        "Kind": {"select": {"options": [{"name": "Study"}, {"name": "Life"}]}},
        "Goal": {"relation": {"database_id": goals_db, "single_property": {}}},
    }
