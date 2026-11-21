"""Weekly digest: what's due, what's overdue, and the planned workload."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .models import Item, Plan


@dataclass
class Digest:
    week_start: date
    due_this_week: list[Item] = field(default_factory=list)
    overdue: list[Item] = field(default_factory=list)
    hours_by_day: dict[date, float] = field(default_factory=dict)
    at_risk: dict[str, float] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return f"Week of {self.week_start:%b %d, %Y}"

    @property
    def total_hours(self) -> float:
        return round(sum(self.hours_by_day.values()), 2)

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", ""]
        lines.append("## Due this week")
        lines += [f"- {i.due:%a %b %d} - {i.title} ({i.type}{', ' + i.course if i.course else ''})" for i in self.due_this_week] or ["- Nothing due"]
        lines += ["", "## Overdue"]
        lines += [f"- {i.title} (was due {i.due:%b %d})" for i in self.overdue] or ["- All caught up"]
        lines += ["", f"## Study plan ({self.total_hours}h)"]
        lines += [f"- {d:%a %b %d}: {h}h" for d, h in self.hours_by_day.items()] or ["- No sessions planned"]
        if self.at_risk:
            lines += ["", "## At risk (not enough time)"]
            lines += [f"- {t}: {h}h unscheduled" for t, h in self.at_risk.items()]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "due_this_week": [i.to_dict() for i in self.due_this_week],
            "overdue": [i.to_dict() for i in self.overdue],
            "hours_by_day": {d.isoformat(): h for d, h in self.hours_by_day.items()},
            "total_hours": self.total_hours,
            "at_risk": self.at_risk,
            "markdown": self.to_markdown(),
        }


def build_digest(items: list[Item], plan: Plan, today: date) -> Digest:
    end = today + timedelta(days=7)
    return Digest(
        week_start=today,
        due_this_week=sorted([i for i in items if today <= i.due < end and i.status != "Done"], key=lambda i: i.due),
        overdue=sorted([i for i in items if i.due < today and i.status != "Done"], key=lambda i: i.due),
        hours_by_day={d: h for d, h in plan.hours_by_day().items() if today <= d < end},
        at_risk=dict(plan.at_risk),
    )


def _text(content: str) -> list:
    return [{"type": "text", "text": {"content": content}}]


def digest_blocks(d: Digest) -> list[dict]:
    """Render a digest as Notion blocks."""

    def h2(t):
        return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": _text(t)}}

    def todo(t, checked=False):
        return {"object": "block", "type": "to_do", "to_do": {"rich_text": _text(t), "checked": checked}}

    def bullet(t):
        return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _text(t)}}

    def callout(t, emoji):
        return {"object": "block", "type": "callout", "callout": {"rich_text": _text(t), "icon": {"type": "emoji", "emoji": emoji}}}

    blocks = [
        callout(
            f"{len(d.due_this_week)} due this week - {len(d.overdue)} overdue - {d.total_hours}h of study planned",
            "\U0001F9ED",
        ),
        h2("Due this week"),
    ]
    blocks += [todo(f"{i.due:%a %b %d} - {i.title} ({i.type}{', ' + i.course if i.course else ''})") for i in d.due_this_week] or [bullet("Nothing due")]
    blocks.append(h2("Overdue"))
    blocks += [todo(f"{i.title} (was due {i.due:%b %d})") for i in d.overdue] or [bullet("All caught up")]
    blocks.append(h2("Study plan"))
    blocks += [bullet(f"{day:%a %b %d}: {'#' * int(h * 2)} {h}h") for day, h in d.hours_by_day.items()] or [bullet("No sessions planned")]
    if d.at_risk:
        blocks.append(h2("At risk"))
        blocks += [callout(f"{t}: {h}h could not be scheduled before the deadline", "\u26A0\uFE0F") for t, h in d.at_risk.items()]
    return blocks
