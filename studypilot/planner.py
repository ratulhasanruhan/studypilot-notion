"""Deadline-aware study planner (earliest deadline first, load-balanced)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from .models import TYPE_LEAD_DAYS, Item, Plan, Session


@dataclass
class PlannerConfig:
    daily_cap: float = 3.0
    block_hours: float = 1.5
    min_block: float = 0.5
    start_time: time = time(18, 0)
    study_weekdays: set[int] = field(default_factory=lambda: {0, 1, 2, 3, 4, 5, 6})
    lead_days: dict[str, int] = field(default_factory=lambda: dict(TYPE_LEAD_DAYS))


def plan_sessions(
    items: list[Item],
    today: date,
    config: PlannerConfig | None = None,
    done_hours: dict[str, float] | None = None,
    tz=None,
) -> Plan:
    """Schedule study blocks before each deadline.

    Items are handled earliest-deadline-first. Each item's remaining hours are
    split into blocks that land on the least-loaded allowed day in its lead
    window, never exceeding ``daily_cap`` per day. Hours that do not fit are
    reported in ``Plan.at_risk``.
    """
    cfg = config or PlannerConfig()
    done_hours = done_hours or {}
    load: dict[date, float] = {}
    plan = Plan()

    pending = [i for i in items if i.status != "Done" and i.due > today]
    pending.sort(key=lambda i: (i.due, -i.hours))

    for item in pending:
        remaining = round(max(item.hours - done_hours.get(item.title, 0.0), 0.0), 2)
        if remaining <= 0:
            continue
        lead = cfg.lead_days.get(item.type, 5)
        first = max(today, item.due - timedelta(days=lead))
        days = [
            first + timedelta(days=n)
            for n in range((item.due - first).days)
            if (first + timedelta(days=n)).weekday() in cfg.study_weekdays
        ]
        while remaining > 1e-6 and days:
            open_days = [d for d in days if cfg.daily_cap - load.get(d, 0.0) >= cfg.min_block - 1e-6]
            if not open_days:
                break
            # least-loaded day; ties go to the later day so work stays close to the deadline
            day = min(open_days, key=lambda d: (load.get(d, 0.0), -d.toordinal()))
            free = cfg.daily_cap - load.get(day, 0.0)
            block = round(min(cfg.block_hours, remaining, free), 2)
            if remaining - block < cfg.min_block - 1e-6 and remaining <= free:
                block = remaining
            start = datetime.combine(day, cfg.start_time, tzinfo=tz) + timedelta(hours=load.get(day, 0.0))
            plan.sessions.append(
                Session(
                    item_title=item.title,
                    start=start,
                    hours=block,
                    item_type=item.type,
                    course=item.course,
                    item_notion_id=item.notion_id,
                )
            )
            load[day] = round(load.get(day, 0.0) + block, 2)
            remaining = round(remaining - block, 2)
        if remaining > 1e-6:
            plan.at_risk[item.title] = remaining

    plan.sessions.sort(key=lambda s: s.start)
    return plan
