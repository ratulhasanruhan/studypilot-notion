"""Compact QuickChart URLs for dashboard visualizations."""

from __future__ import annotations

import json
from datetime import date, timedelta
from urllib.parse import quote

from .models import Item, Plan

BALANCE_COLORS = {
    "Balanced": "#0f7b6c",
    "Stretched": "#d9730d",
    "Burnout risk": "#e03e3e",
}
COURSE_COLORS = ["#2383e2", "#0f7b6c", "#d9730d", "#e03e3e", "#8b5cf6"]


def chart_url(config: dict, width: int = 600, height: int = 300) -> str:
    encoded = quote(json.dumps(config, separators=(",", ":")))
    return f"https://quickchart.io/chart?w={width}&h={height}&bkg=white&c={encoded}"


def balance_chart(weeks: list[dict]) -> str:
    labels = []
    for week in weeks:
        start = date.fromisoformat(week["start"])
        labels.append(f"{start:%b} {start.day}")
    config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "data": [round(week["score"]) for week in weeks],
                    "backgroundColor": [BALANCE_COLORS.get(week["label"], BALANCE_COLORS["Burnout risk"]) for week in weeks],
                }
            ],
        },
        "options": {
            "title": {"display": True, "text": "Balance Score by week"},
            "legend": {"display": False},
            "scales": {"yAxes": [{"ticks": {"min": 0, "max": 100}}]},
        },
    }
    return chart_url(config)


def week_hours_chart(plan: Plan, today: date) -> str:
    labels = [(today + timedelta(days=offset)).strftime("%a %d") for offset in range(7)]
    hours = {
        kind: plan.hours_by_day(kind)
        for kind in ("Study", "Life")
    }
    study_values = []
    life_values = []
    for offset in range(7):
        day = today + timedelta(days=offset)
        study = hours["Study"].get(day, 0)
        life = hours["Life"].get(day, 0)
        study_value = round(study, 1)
        life_value = round(life, 1)
        correction = round(round(study + life, 1) - study_value - life_value, 1)
        if correction:
            if study >= life:
                study_value = round(study_value + correction, 1)
            else:
                life_value = round(life_value + correction, 1)
        study_values.append(study_value)
        life_values.append(life_value)
    config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Study",
                    "data": study_values,
                    "backgroundColor": "#2383e2",
                },
                {
                    "label": "Life",
                    "data": life_values,
                    "backgroundColor": "#0f7b6c",
                },
            ],
        },
        "options": {
            "title": {"display": True, "text": "Next 7 days: study vs life (hours)"},
            "scales": {"xAxes": [{"stacked": True}], "yAxes": [{"stacked": True, "ticks": {"beginAtZero": True}}]},
        },
    }
    return chart_url(config)


def course_hours_chart(plan: Plan, items: list[Item]) -> str:
    course_by_id = {item.notion_id: item.course for item in items if item.notion_id and item.course}
    course_by_title = {item.title: item.course for item in items if item.course}
    totals: dict[str, float] = {}
    for session in plan.sessions:
        if session.kind != "Study":
            continue
        course = course_by_id.get(session.item_notion_id or "")
        if not course:
            course = course_by_title.get(session.item_title, "Other")
        totals[course] = totals.get(course, 0.0) + session.hours
    if not totals:
        totals["Other"] = 0.0
    labels = sorted(totals)
    config = {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "data": [round(totals[label], 1) for label in labels],
                    "backgroundColor": [COURSE_COLORS[index % len(COURSE_COLORS)] for index in range(len(labels))],
                }
            ],
        },
        "options": {"title": {"display": True, "text": "Planned study hours by course"}},
    }
    return chart_url(config)
