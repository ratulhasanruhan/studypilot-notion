"""Rule-based syllabus parser: finds dated deadlines and classifies them."""

from __future__ import annotations

import re
from datetime import date, datetime

from dateutil import parser as dateparser

from .models import Item

MONTHS = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
)
WEEKDAY = r"(?:(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day|nesday|sday|urday)?\.?,?\s+)?"

DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"),
    re.compile(WEEKDAY + MONTHS + r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b", re.I),
    re.compile(WEEKDAY + r"\b\d{1,2}(?:st|nd|rd|th)?\s+" + MONTHS + r"(?:,?\s+\d{4})?\b", re.I),
    re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"),
]

TYPE_RULES = [
    ("Project", r"\b(project|capstone|presentation|portfolio)\b"),
    ("Exam", r"\b(exam|midterm|final|test)\b"),
    ("Quiz", r"\bquiz(zes)?\b"),
    ("Lab", r"\blab\b"),
    ("Reading", r"\b(read|reading|chapter|ch\.)\b"),
    ("Assignment", r"\b(hw|homework|assignment|problem set|pset|essay|paper|report|due|submit)\b"),
]

COURSE_RE = re.compile(r"\b([A-Z]{2,5})\s?-?(\d{2,4}[A-Z]?)\b")
DEADLINE_HINT = re.compile(
    r"\b(due|exam|midterm|final|quiz|project|hw|homework|assignment|essay|paper|report|lab|"
    r"presentation|pset|problem set|test|submit|read|reading|chapter)\b",
    re.I,
)


def _find_date(line: str):
    for pat in DATE_PATTERNS:
        m = pat.search(line)
        if m:
            return m
    return None


def _parse_date(text: str, year: int, term_start: date | None) -> date | None:
    has_year = bool(re.search(r"\d{4}", text)) or bool(re.search(r"/\d{2,4}$", text.strip()))
    try:
        d = dateparser.parse(text, default=datetime(year, 1, 1), fuzzy=True).date()
    except (ValueError, OverflowError):
        return None
    if not has_year and term_start and d < term_start:
        d = d.replace(year=d.year + 1)
    return d


def classify(text: str) -> str:
    low = text.lower()
    for kind, pattern in TYPE_RULES:
        if re.search(pattern, low):
            return kind
    return "Assignment"


def _clean_title(line: str, date_text: str) -> str:
    t = line.replace(date_text, " ")
    t = re.sub(r"^\s*(?:[-*\u2022]|\d+[.)])\s+", "", t)
    t = re.sub(r"\bweek\s*\d+\b", " ", t, flags=re.I)
    t = re.sub(r"\(\s*\)|\[\s*\]", " ", t)
    t = re.sub(r"\b(due|on|by)\b\s*[:\-]?\s*$", " ", t.strip(), flags=re.I)
    t = re.sub(r"^\s*[:\-\u2013\u2014|,]+|[:\-\u2013\u2014|,(]+\s*$", "", t.strip())
    t = re.sub(r"\s{2,}", " ", t).strip(" -:\u2013\u2014|,")
    return t[:120] or "Untitled deadline"


def detect_course(text: str) -> str:
    for line in text.splitlines()[:10]:
        m = COURSE_RE.search(line)
        if m:
            return f"{m.group(1)} {m.group(2)}"
    return ""


def parse_syllabus(
    text: str,
    year: int | None = None,
    term_start: date | None = None,
    course: str | None = None,
) -> list[Item]:
    """Extract dated deadlines from free-form syllabus text."""
    year = year or (term_start.year if term_start else date.today().year)
    course = course if course is not None else detect_course(text)
    items: list[Item] = []
    seen: set[tuple[str, date]] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _find_date(line)
        if not m or not DEADLINE_HINT.search(line):
            continue
        due = _parse_date(m.group(0), year, term_start)
        if not due:
            continue
        title = _clean_title(line, m.group(0))
        key = (title.lower(), due)
        if key in seen:
            continue
        seen.add(key)
        items.append(Item(title=title, due=due, type=classify(line), course=course))
    items.sort(key=lambda i: i.due)
    return items
