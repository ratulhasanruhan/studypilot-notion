from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Optional

TYPE_HOURS = {
    "Exam": 8.0,
    "Project": 10.0,
    "Assignment": 4.0,
    "Lab": 3.0,
    "Quiz": 2.0,
    "Reading": 1.5,
}

TYPE_LEAD_DAYS = {
    "Exam": 10,
    "Project": 14,
    "Assignment": 6,
    "Lab": 4,
    "Quiz": 4,
    "Reading": 3,
}


@dataclass
class Item:
    """A deadline extracted from a syllabus or stored in Notion."""

    title: str
    due: date
    type: str = "Assignment"
    hours: float = 0.0
    course: str = ""
    status: str = "Not started"
    notion_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.hours:
            self.hours = TYPE_HOURS.get(self.type, 3.0)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["due"] = self.due.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        d = dict(d)
        d["due"] = date.fromisoformat(d["due"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Session:
    """A planned study block for one item."""

    item_title: str
    start: datetime
    hours: float
    item_type: str = "Assignment"
    course: str = ""
    item_notion_id: Optional[str] = None
    kind: str = "Study"
    label: str = ""
    goal_notion_id: Optional[str] = None

    @property
    def end(self) -> datetime:
        from datetime import timedelta

        return self.start + timedelta(hours=self.hours)

    @property
    def title(self) -> str:
        if self.label:
            return self.label
        verb = {"Exam": "Review", "Quiz": "Review", "Reading": "Read"}.get(self.item_type, "Work on")
        if self.item_title.lower().startswith(("read", "review", "study", "work on", "finish")):
            return self.item_title
        return f"{verb}: {self.item_title}"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "item_title": self.item_title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "hours": self.hours,
            "course": self.course,
            "kind": self.kind,
        }


@dataclass
class Goal:
    """A life-beyond-study goal (fitness, outdoors, reading, hobbies...)."""

    title: str
    template: str = "custom"
    category: str = "Wellbeing"
    sessions_per_week: int = 2
    hours: float = 1.0
    days: list[int] = field(default_factory=list)
    time: str = "Evening"
    target: str = ""
    status: str = "Active"
    start: Optional[date] = None
    notion_id: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat() if self.start else None
        return d


@dataclass
class Plan:
    sessions: list[Session] = field(default_factory=list)
    at_risk: dict[str, float] = field(default_factory=dict)
    light_weeks: list[date] = field(default_factory=list)

    def hours_by_day(self, kind: str | None = None) -> dict[date, float]:
        out: dict[date, float] = {}
        for s in self.sessions:
            if kind and s.kind != kind:
                continue
            out[s.start.date()] = round(out.get(s.start.date(), 0.0) + s.hours, 2)
        return dict(sorted(out.items()))

    def to_dict(self) -> dict:
        return {
            "sessions": [s.to_dict() for s in self.sessions],
            "at_risk": self.at_risk,
            "hours_by_day": {d.isoformat(): h for d, h in self.hours_by_day().items()},
            "study_by_day": {d.isoformat(): h for d, h in self.hours_by_day("Study").items()},
            "life_by_day": {d.isoformat(): h for d, h in self.hours_by_day("Life").items()},
            "light_weeks": [d.isoformat() for d in self.light_weeks],
        }
