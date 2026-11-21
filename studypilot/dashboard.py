"""Notion dashboard blocks for a StudyPilot workspace."""

from __future__ import annotations

import os
from datetime import date, timedelta

from .life import TEMPLATES
from .models import Goal, Item, Plan

REPO_URL = "https://github.com/ratulhasanruhan/studypilot-notion"


def _text(content: str, annotations: dict | None = None, **kwargs) -> dict:
    out = {"type": "text", "text": {"content": content, **kwargs}}
    if annotations:
        out["annotations"] = annotations
    return out


def _block(block_type: str, content: dict) -> dict:
    return {"object": "block", "type": block_type, block_type: content}


def _rich_text(content: str) -> list[dict]:
    return [_text(content)]


def _heading(level: int, content: str) -> dict:
    return _block(f"heading_{level}", {"rich_text": _rich_text(content)})


def _paragraph(content: str) -> dict:
    return _block("paragraph", {"rich_text": _rich_text(content)})


def _balance_callout(week: dict, index: int) -> dict:
    label = week["label"]
    icon = {"Balanced": "🟢", "Stretched": "🟡", "Burnout risk": "🔴"}.get(label, "🔴")
    start = date.fromisoformat(week["start"])
    window = "Next 7 days" if index == 0 else f"Week of {start:%b %d}"
    rich_text = [
        _text(f"{window}\n"),
        _text(
            f"{week['score']}/100 · {label}\n",
            annotations={"bold": True},
        ),
        _text(f"📚 {week['study_hours']}h study · 🌱 {week['life_hours']}h life\n"),
        _text(week["tip"]),
    ]
    return _block(
        "callout",
        {"rich_text": rich_text, "icon": {"type": "emoji", "emoji": icon}},
    )


def _balance_columns(plan: Plan) -> dict:
    columns = [
        _block("column", {"children": [_balance_callout(week, index)]})
        for index, week in enumerate(plan.weeks)
    ]
    return _block("column_list", {"children": columns})


def _table(plan: Plan, today: date) -> dict:
    def row(cells: list[str]) -> dict:
        return _block(
            "table_row",
            {"cells": [_rich_text(value) for value in cells]},
        )

    rows = [row(["Day", "📚 Study", "🌱 Life"])]
    for offset in range(7):
        day = today + timedelta(days=offset)
        cells = [day.strftime("%a %b %d")]
        for kind in ("Study", "Life"):
            sessions = [
                session
                for session in plan.sessions
                if session.kind == kind and session.start.date() == day
            ]
            cells.append(
                "\n".join(
                    f"{session.start:%H:%M} {session.title} ({round(session.hours * 60)} min)"
                    for session in sessions
                )
                or "—"
            )
        rows.append(row(cells))
    return _block(
        "table",
        {"table_width": 3, "has_column_header": True, "children": rows},
    )


def _due_items(items: list[Item], today: date) -> list[dict]:
    end = today + timedelta(days=14)
    due = sorted(
        (item for item in items if item.status != "Done" and today <= item.due < end),
        key=lambda item: item.due,
    )
    if not due:
        return [_paragraph("Nothing due 🎉")]
    return [
        _block(
            "to_do",
            {
                "rich_text": _rich_text(
                    f"{item.due:%a %b %d} · {item.title} "
                    f"({item.type}{', ' + item.course if item.course else ''})"
                ),
                "checked": False,
            },
        )
        for item in due
    ]


def _life_goals(goals: list[Goal]) -> list[dict]:
    if not goals:
        return [_paragraph("No life goals yet")]
    blocks = []
    for goal in goals:
        emoji = TEMPLATES.get(goal.template).emoji if goal.template in TEMPLATES else "✨"
        target = f" · {goal.target}" if goal.target else ""
        paused = " (paused)" if goal.status == "Paused" else ""
        text = (
            f"{emoji} {goal.title} · {goal.sessions_per_week}x a week, "
            f"{round(goal.hours * 60)} min, {goal.time.lower()}s{target}{paused}"
        )
        blocks.append(_block("bulleted_list_item", {"rich_text": _rich_text(text)}))
    return blocks


def _database_links(links: dict) -> list[dict]:
    blocks = []
    for key in ("courses", "assignments", "goals", "sessions"):
        database_id = links.get(key) or links.get(f"{key}_db")
        if database_id:
            blocks.append(
                _block(
                    "link_to_page",
                    {
                        "type": "database_id",
                        "database_id": database_id,
                    },
                )
            )
    return blocks


def _external_links(links: dict) -> dict:
    result = {"repo": links.get("repo") or REPO_URL}
    app_url = links.get("app") or os.environ.get("STUDYPILOT_APP_URL")
    if app_url:
        result["app"] = app_url
    for key, value in links.items():
        if key not in ("app", "repo"):
            result[key] = value
    return result


def _links_paragraph(links: dict) -> dict | None:
    values = _external_links(links)
    entries = [
        (label, values.get(key))
        for label, key in (("Web app", "app"), ("GitHub", "repo"))
        if values.get(key)
    ]
    if not entries:
        return None
    rich_text = []
    for index, (label, url) in enumerate(entries):
        if index:
            rich_text.append(_text(" · "))
        rich_text.append(_text(label, link={"url": url}))
    return _block("paragraph", {"rich_text": rich_text})


def dashboard_blocks(
    plan: Plan,
    items: list[Item],
    goals: list[Goal],
    today: date,
    links: dict,
) -> list[dict]:
    """Render a refreshable dashboard as Notion API 2022-06-28 block JSON."""
    blocks = [
        _block("divider", {}),
        _heading(1, "🧭 StudyPilot dashboard"),
        _paragraph(f"Study hard, live fully. Updated {today:%a %b %d, %Y}."),
        _heading(2, "⚖️ Balance Score"),
        _balance_columns(plan),
        _heading(2, "📅 Next 7 days"),
        _table(plan, today),
        _block(
            "column_list",
            {
                "children": [
                    _block(
                        "column",
                        {
                            "children": [
                                _heading(3, "⏰ Due in the next 14 days"),
                                *_due_items(items, today),
                            ]
                        },
                    ),
                    _block(
                        "column",
                        {
                            "children": [
                                _heading(3, "🌱 Life goals"),
                                *_life_goals(goals),
                            ]
                        },
                    ),
                ]
            },
        ),
        _heading(3, "🗂️ Databases"),
        *_database_links(links),
    ]
    external_links = _links_paragraph(links)
    if external_links:
        blocks.append(external_links)
    blocks.append(_block("divider", {}))
    return blocks
