"""Orchestrates syllabus import, planning and digests against Notion."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from . import schema
from .digest import Digest, build_digest, digest_blocks
from .life import DAY_NAMES, TEMPLATES, LifeConfig, plan_life, suggest
from .models import Goal, Item, Plan
from .planner import PlannerConfig, plan_sessions

DEFAULT_CONFIG = Path(os.environ.get("STUDYPILOT_CONFIG", ".studypilot.json"))


@dataclass
class Config:
    parent_page_id: str = ""
    courses_db: str = ""
    assignments_db: str = ""
    sessions_db: str = ""
    goals_db: str = ""
    timezone: str = "UTC"
    daily_cap: float = 3.0
    block_hours: float = 1.5
    start_hour: int = 18

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG) -> "Config":
        if Path(path).exists():
            data = json.loads(Path(path).read_text())
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return cls()

    def save(self, path: Path = DEFAULT_CONFIG) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2) + "\n")

    @property
    def ready(self) -> bool:
        return bool(self.courses_db and self.assignments_db and self.sessions_db)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def planner(self) -> PlannerConfig:
        return PlannerConfig(daily_cap=self.daily_cap, block_hours=self.block_hours, start_time=time(self.start_hour, 0))

    def life(self) -> LifeConfig:
        return LifeConfig(study_start=time(self.start_hour, 0), daily_cap=self.daily_cap)


def _text(content: str) -> list:
    return [{"type": "text", "text": {"content": content}}]


def _plain(prop: dict) -> str:
    parts = prop.get("title") or prop.get("rich_text") or []
    return "".join(p.get("plain_text") or p.get("text", {}).get("content", "") for p in parts)


def _select(prop: dict, default: str = "") -> str:
    sel = prop.get("select") if prop else None
    return sel["name"] if sel else default


def _number(prop: dict, default: float = 0.0) -> float:
    n = (prop or {}).get("number")
    return default if n is None else n


class StudyPilot:
    def __init__(self, client, config: Config | None = None, config_path: Path = DEFAULT_CONFIG):
        self.notion = client
        self.config = config or Config.load(config_path)
        self.config_path = config_path
        self._courses: dict[str, str] | None = None

    def today(self) -> date:
        return datetime.now(self.config.tz).date()

    # ---- setup -------------------------------------------------------------
    def bootstrap(self, parent_page_id: str) -> Config:
        """Create the Courses / Assignments / Study Sessions databases under a page."""
        c = self.config
        if c.ready and c.parent_page_id == parent_page_id:
            self.ensure_life()
            return c
        c.parent_page_id = parent_page_id
        c.courses_db = self.notion.create_database(parent_page_id, "Courses", schema.COURSES, icon="\U0001F4DA")["id"]
        c.assignments_db = self.notion.create_database(
            parent_page_id, "Assignments & Exams", schema.assignments(c.courses_db), icon="\U0001F4DD"
        )["id"]
        c.sessions_db = self.notion.create_database(
            parent_page_id, "Schedule", schema.sessions(c.assignments_db), icon="\U0001F5D3\uFE0F"
        )["id"]
        c.goals_db = ""
        self.ensure_life()
        return c

    def ensure_life(self) -> None:
        """Add the Life Goals database and link it to the schedule (also upgrades older setups)."""
        c = self.config
        if c.goals_db or not c.ready:
            return
        c.goals_db = self.notion.create_database(c.parent_page_id, "Life Goals", schema.goals(), icon="\U0001F331")["id"]
        self.notion.update_database(c.sessions_db, schema.schedule_life_props(c.goals_db), title="Schedule")
        c.save(self.config_path)

    def _require(self) -> None:
        if not self.config.ready:
            raise RuntimeError("Not set up yet: run `studypilot setup <notion-page-url>` first")

    # ---- courses -----------------------------------------------------------
    def courses(self) -> dict[str, str]:
        if self._courses is None:
            self._courses = {
                _plain(p["properties"]["Name"]): p["id"] for p in self.notion.query_database(self.config.courses_db)
            }
        return self._courses

    def ensure_course(self, name: str) -> str | None:
        if not name:
            return None
        courses = self.courses()
        if name not in courses:
            page = self.notion.create_page(
                {"database_id": self.config.courses_db},
                {"Name": {"title": _text(name)}, "Code": {"rich_text": _text(name)}},
                icon="\U0001F4D8",
            )
            courses[name] = page["id"]
        return courses[name]

    # ---- assignments -------------------------------------------------------
    def list_items(self) -> list[Item]:
        self._require()
        by_id = {v: k for k, v in self.courses().items()}
        items = []
        for p in self.notion.query_database(self.config.assignments_db):
            props = p["properties"]
            due = (props.get("Due") or {}).get("date")
            if not due or not due.get("start"):
                continue
            rel = (props.get("Course") or {}).get("relation") or []
            items.append(
                Item(
                    title=_plain(props["Name"]),
                    due=date.fromisoformat(due["start"][:10]),
                    type=_select(props.get("Type"), "Assignment"),
                    hours=(props.get("Est. Hours") or {}).get("number") or 0.0,
                    course=by_id.get(rel[0]["id"], "") if rel else "",
                    status=_select(props.get("Status"), "Not started"),
                    notion_id=p["id"],
                )
            )
        return sorted(items, key=lambda i: i.due)

    def import_items(self, items: list[Item]) -> dict:
        """Add items to Notion, skipping ones that already exist (same title + due date)."""
        self._require()
        existing = {(i.title.lower(), i.due) for i in self.list_items()}
        created, skipped = [], []
        for item in items:
            if (item.title.lower(), item.due) in existing:
                skipped.append(item.title)
                continue
            props = {
                "Name": {"title": _text(item.title)},
                "Type": {"select": {"name": item.type}},
                "Due": {"date": {"start": item.due.isoformat()}},
                "Status": {"select": {"name": item.status}},
                "Est. Hours": {"number": item.hours},
                "Source": {"select": {"name": "Syllabus"}},
            }
            course_id = self.ensure_course(item.course)
            if course_id:
                props["Course"] = {"relation": [{"id": course_id}]}
            page = self.notion.create_page({"database_id": self.config.assignments_db}, props)
            item.notion_id = page["id"]
            existing.add((item.title.lower(), item.due))
            created.append(item.title)
        return {"created": created, "skipped": skipped}

    # ---- life goals --------------------------------------------------------
    def list_goals(self) -> list[Goal]:
        self._require()
        self.ensure_life()
        goals = []
        for p in self.notion.query_database(self.config.goals_db):
            props = p["properties"]
            started = ((props.get("Started") or {}).get("date") or {}).get("start")
            goals.append(
                Goal(
                    title=_plain(props["Name"]),
                    template=_plain(props.get("Template") or {}) or "custom",
                    category=_select(props.get("Category"), "Wellbeing"),
                    sessions_per_week=int(_number(props.get("Sessions/Week"), 1)),
                    hours=_number(props.get("Hours/Session"), 1.0),
                    days=[DAY_NAMES.index(o["name"]) for o in (props.get("Days") or {}).get("multi_select", [])
                          if o["name"] in DAY_NAMES],
                    time=_select(props.get("Time"), "Evening"),
                    target=_plain(props.get("Target") or {}),
                    status=_select(props.get("Status"), "Active"),
                    start=date.fromisoformat(started[:10]) if started else None,
                    notion_id=p["id"],
                )
            )
        return goals

    def add_goal(self, template: str, target: str = "", today: date | None = None, **overrides) -> Goal:
        """Create a life goal from a template key (see life.TEMPLATES) or a custom title."""
        self._require()
        self.ensure_life()
        if template in TEMPLATES:
            goal = TEMPLATES[template].goal(target, **overrides)
        else:
            goal = Goal(title=overrides.pop("title", None) or template, target=target)
            for k, v in overrides.items():
                if v not in (None, "", []):
                    setattr(goal, k, v)
        goal.start = today or self.today()
        icon = TEMPLATES[template].emoji if template in TEMPLATES else "\u2728"
        page = self.notion.create_page({"database_id": self.config.goals_db}, self._goal_props(goal), icon=icon)
        goal.notion_id = page["id"]
        return goal

    def _goal_props(self, g: Goal) -> dict:
        props = {
            "Name": {"title": _text(g.title)},
            "Category": {"select": {"name": g.category}},
            "Template": {"rich_text": _text(g.template)},
            "Sessions/Week": {"number": g.sessions_per_week},
            "Hours/Session": {"number": g.hours},
            "Days": {"multi_select": [{"name": DAY_NAMES[d]} for d in g.days]},
            "Time": {"select": {"name": g.time}},
            "Status": {"select": {"name": g.status}},
            "Target": {"rich_text": _text(g.target)},
        }
        if g.start:
            props["Started"] = {"date": {"start": g.start.isoformat()}}
        return props

    def set_goal_status(self, name_or_id: str, status: str) -> Goal:
        for g in self.list_goals():
            if name_or_id in (g.notion_id, g.title) or g.title.lower() == name_or_id.lower():
                self.notion.update_page(g.notion_id, {"Status": {"select": {"name": status}}})
                g.status = status
                return g
        raise ValueError(f"No life goal named {name_or_id!r}")

    def suggest(self, interests: str, today: date | None = None) -> list[dict]:
        today = today or self.today()
        study = plan_sessions(self.list_items(), today, self.config.planner(), tz=self.config.tz)
        next_week = sum(h for d, h in study.hours_by_day().items() if (d - today).days < 7)
        return suggest(interests, round(next_week, 1), self.list_goals(), self.config.daily_cap)

    # ---- planning ----------------------------------------------------------
    def _sessions(self) -> list[dict]:
        return list(self.notion.query_database(self.config.sessions_db))

    def _full_plan(self, today: date, done_hours: dict[str, float] | None = None) -> Plan:
        items = self.list_items()
        plan = plan_sessions(items, today, self.config.planner(), done_hours, tz=self.config.tz)
        life, light = plan_life(self.list_goals(), today, plan, items, self.config.life(), tz=self.config.tz)
        plan.sessions = sorted(plan.sessions + life, key=lambda s: s.start)
        plan.light_weeks = sorted(light)
        return plan

    def replan(self, today: date | None = None) -> Plan:
        """Clear future StudyPilot sessions that aren't done, then write a fresh study + life plan."""
        self._require()
        self.ensure_life()
        today = today or self.today()
        title_by_id = {i.notion_id: i.title for i in self.list_items()}
        done_hours: dict[str, float] = {}
        for s in self._sessions():
            props = s["properties"]
            rel = (props.get("Assignment") or {}).get("relation") or []
            title = title_by_id.get(rel[0]["id"]) if rel else None
            hours = _number(props.get("Hours"))
            when = ((props.get("When") or {}).get("date") or {}).get("start", "")
            ours = _select(props.get("Planned by")) == "StudyPilot"
            if (props.get("Done") or {}).get("checkbox"):
                if title:
                    done_hours[title] = done_hours.get(title, 0.0) + hours
            elif ours and when and date.fromisoformat(when[:10]) >= today:
                self.notion.update_page(s["id"], archived=True)
        plan = self._full_plan(today, done_hours)
        for sess in plan.sessions:
            props = {
                "Name": {"title": _text(sess.title)},
                "When": {"date": {"start": sess.start.isoformat(), "end": sess.end.isoformat()}},
                "Hours": {"number": sess.hours},
                "Done": {"checkbox": False},
                "Planned by": {"select": {"name": "StudyPilot"}},
                "Kind": {"select": {"name": sess.kind}},
            }
            if sess.item_notion_id:
                props["Assignment"] = {"relation": [{"id": sess.item_notion_id}]}
            if sess.goal_notion_id:
                props["Goal"] = {"relation": [{"id": sess.goal_notion_id}]}
            self.notion.create_page({"database_id": self.config.sessions_db}, props)
        return plan

    def preview_plan(self, today: date | None = None) -> Plan:
        self._require()
        self.ensure_life()
        return self._full_plan(today or self.today())

    def life_stats(self, today: date) -> dict:
        """Completion of life sessions over the last 7 days."""
        total = done = 0
        for s in self._sessions():
            props = s["properties"]
            if _select(props.get("Kind")) != "Life":
                continue
            when = ((props.get("When") or {}).get("date") or {}).get("start", "")
            if when and 0 < (today - date.fromisoformat(when[:10])).days <= 7:
                total += 1
                done += bool((props.get("Done") or {}).get("checkbox"))
        return {"last_week_total": total, "last_week_done": done}

    # ---- digest ------------------------------------------------------------
    def digest(self, today: date | None = None, publish: bool = True) -> tuple[Digest, str | None]:
        self._require()
        today = today or self.today()
        d = build_digest(self.list_items(), self.preview_plan(today), today, self.life_stats(today))
        url = None
        if publish:
            page = self.notion.create_page(
                {"page_id": self.config.parent_page_id},
                {"title": {"title": _text(f"\U0001F9ED {d.title}")}},
                children=digest_blocks(d),
            )
            url = page.get("url")
        return d, url
