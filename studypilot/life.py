"""Life beyond study: activity suggestions and load-aware scheduling."""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Callable

from .models import Goal, Item, Plan, Session

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CATEGORIES = ["Fitness", "Outdoors", "Reading", "Creative", "Social", "Wellbeing", "Skill"]
TIMES = ["Morning", "Afternoon", "Evening"]

BOOKS = {
    "general": ["Atomic Habits - James Clear", "Project Hail Mary - Andy Weir", "Man's Search for Meaning - Viktor Frankl", "Sapiens - Yuval Noah Harari", "The Alchemist - Paulo Coelho"],
    "sci-fi": ["Project Hail Mary - Andy Weir", "Dune - Frank Herbert", "The Martian - Andy Weir", "Recursion - Blake Crouch", "Klara and the Sun - Kazuo Ishiguro"],
    "fantasy": ["The Name of the Wind - Patrick Rothfuss", "Mistborn - Brandon Sanderson", "The Hobbit - J.R.R. Tolkien", "Piranesi - Susanna Clarke"],
    "self-help": ["Atomic Habits - James Clear", "Deep Work - Cal Newport", "The Psychology of Money - Morgan Housel", "Mindset - Carol Dweck"],
    "history": ["Sapiens - Yuval Noah Harari", "Guns, Germs, and Steel - Jared Diamond", "The Silk Roads - Peter Frankopan"],
    "science": ["A Short History of Nearly Everything - Bill Bryson", "The Gene - Siddhartha Mukherjee", "Thinking, Fast and Slow - Daniel Kahneman"],
    "business": ["Zero to One - Peter Thiel", "The Lean Startup - Eric Ries", "Shoe Dog - Phil Knight"],
    "fiction": ["Educated - Tara Westover", "Norwegian Wood - Haruki Murakami", "The Kite Runner - Khaled Hosseini", "Tomorrow, and Tomorrow, and Tomorrow - Gabrielle Zevin"],
}
GENRE_WORDS = {
    "sci-fi": r"sci-?fi|science fiction|space",
    "fantasy": r"fantasy|magic",
    "self-help": r"self[- ]?help|productivity|habits|growth",
    "history": r"history|historical",
    "science": r"science|physics|biology|psychology",
    "business": r"business|startup|entrepreneur|finance",
    "fiction": r"novel|fiction|literature|story",
}

HIKES = ["Local trail loop", "Sunrise hilltop hike", "Waterfall or lake trail", "Explore a new park", "Forest trail with friends"]
SKETCH = ["people in a cafe", "your desk", "a plant", "a street corner", "your hands", "a building"]
LIFTS = ["Push day", "Pull day", "Leg day"]

LabelFn = Callable[[Goal, int, int, bool], tuple[str, float]]


def _half_marathon(g: Goal, week: int, k: int, light: bool) -> tuple[str, float]:
    if k == g.sessions_per_week - 1 and not light:
        km = min(6 + 1.5 * week, 21.1)
        return (f"Long run: {km:g} km" if km < 21.1 else "Race-pace long run: 21.1 km", round(0.75 + km / 10, 2))
    return (f"Easy run: {min(4 + 0.5 * week, 10):g} km", g.hours)


def _c25k(g: Goal, week: int, k: int, light: bool) -> tuple[str, float]:
    return (f"Couch to 5K: week {week + 1}, run {k + 1}" if week < 9 else "5K run", g.hours)


def _hike(g: Goal, week: int, k: int, light: bool) -> tuple[str, float]:
    if light:
        return ("Easy nature walk (busy week)", 1.0)
    return (f"Hike: {g.target or HIKES[week % len(HIKES)]}", g.hours)


def _simple(fmt: str) -> LabelFn:
    def fn(g: Goal, week: int, k: int, light: bool) -> tuple[str, float]:
        return (fmt.format(target=g.target, week=week + 1, n=k + 1, sketch=SKETCH[(week * 3 + k) % len(SKETCH)],
                           lift=LIFTS[k % len(LIFTS)]), g.hours)
    return fn


@dataclass
class Template:
    key: str
    title: str
    category: str
    emoji: str
    sessions_per_week: int
    hours: float
    days: list[int]
    time: str
    keywords: str
    pitch: str
    label: LabelFn = field(default=None)  # type: ignore[assignment]
    default_target: str = ""

    def goal(self, target: str = "", **overrides) -> Goal:
        g = Goal(title=self.title, template=self.key, category=self.category, sessions_per_week=self.sessions_per_week,
                 hours=self.hours, days=list(self.days), time=self.time, target=target or self.default_target)
        for k, v in overrides.items():
            if v not in (None, "", []):
                setattr(g, k, v)
        return g


TEMPLATES: dict[str, Template] = {t.key: t for t in [
    Template("half-marathon", "Half-marathon training", "Fitness", "\U0001F3C3", 3, 0.75, [1, 3, 5], "Morning",
             r"marathon|half[- ]?marathon|10k|race", "Progressive 3-runs-a-week plan; the Saturday long run grows 1.5 km each week.", _half_marathon),
    Template("5k", "Couch to 5K", "Fitness", "\U0001F45F", 3, 0.5, [0, 2, 5], "Morning",
             r"\brun|running|jog|cardio|5k", "Beginner-friendly: three 30-minute runs a week until you can run 5K.", _c25k),
    Template("hiking", "Weekend hikes", "Outdoors", "\U0001F97E", 1, 3.5, [5, 6], "Morning",
             r"hik|trek|mountain|trail|nature|outdoor|walk", "One weekend hike a week; it becomes a short walk in exam weeks.", _hike),
    Template("reading", "Read for fun", "Reading", "\U0001F4D6", 5, 0.5, [0, 1, 2, 3, 6], "Evening",
             r"read|book|novel|literature|fiction|sci-?fi|fantasy", "30 minutes of non-course reading before bed, five nights a week.",
             _simple("Read: {target} (30 min)"), BOOKS["general"][0]),
    Template("gym", "Strength training", "Fitness", "\U0001F3CB\uFE0F", 3, 1.0, [0, 2, 4], "Afternoon",
             r"gym|lift|strength|muscle|workout|fitness", "Push / pull / legs split, three times a week.", _simple("Gym: {lift}")),
    Template("meditation", "Mindfulness", "Wellbeing", "\U0001F9D8", 5, 0.25, [0, 1, 2, 3, 4], "Morning",
             r"meditat|mindful|stress|calm|anxiety|mental|sleep", "15 minutes each weekday morning to lower stress.", _simple("Meditate 15 min")),
    Template("music", "Music practice", "Creative", "\U0001F3B8", 4, 0.5, [0, 2, 4, 6], "Evening",
             r"guitar|piano|music|sing|instrument|violin|drum|ukulele", "Short regular practice beats rare long sessions.",
             _simple("Practice {target}"), "guitar"),
    Template("drawing", "Sketching", "Creative", "\U0001F3A8", 3, 0.5, [1, 3, 6], "Afternoon",
             r"draw|sketch|art|paint|design", "A 30-minute sketch prompt three times a week.", _simple("Sketch: {sketch}")),
    Template("language", "Learn a language", "Skill", "\U0001F5E3\uFE0F", 5, 0.25, [0, 1, 2, 3, 4], "Morning",
             r"language|spanish|french|japanese|korean|german|arabic|chinese|duolingo", "15 minutes a day keeps the streak alive.",
             _simple("{target} practice (15 min)"), "Spanish"),
    Template("friends", "Friends & clubs", "Social", "\U0001F91D", 1, 2.0, [4], "Evening",
             r"friend|social|club|hang|party|people", "A protected Friday evening for people, not screens.", _simple("Hang out: friends or club")),
    Template("volunteer", "Volunteering", "Social", "\U0001F49B", 1, 2.0, [6], "Afternoon",
             r"volunteer|community|charity|help|ngo", "Two hours a week giving back.", _simple("Volunteer: {target}"), "local community"),
    Template("cooking", "Cook something new", "Wellbeing", "\U0001F373", 1, 1.5, [6], "Evening",
             r"cook|bake|food|recipe", "One new recipe every Sunday.", _simple("Cook a new recipe (week {week})")),
    Template("photography", "Photo walks", "Creative", "\U0001F4F7", 1, 1.5, [5], "Afternoon",
             r"photo|camera|film", "A weekly photo walk with a theme.", _simple("Photo walk")),
    Template("sport", "Team sport", "Fitness", "\u26BD", 2, 1.5, [2, 5], "Afternoon",
             r"football|soccer|cricket|basketball|badminton|tennis|volleyball|sport", "Pickup games twice a week.",
             _simple("Play {target}"), "football"),
    Template("cycling", "Cycling", "Outdoors", "\U0001F6B4", 2, 1.5, [3, 6], "Morning",
             r"cycl|bike|biking", "Two rides a week, one longer weekend route.", _simple("Ride #{n} this week")),
    Template("swimming", "Swimming", "Fitness", "\U0001F3CA", 2, 1.0, [1, 4], "Morning",
             r"swim|pool", "Two swims a week for low-impact fitness.", _simple("Swim laps")),
    Template("side-project", "Side project", "Skill", "\U0001F4BB", 2, 1.5, [5, 6], "Afternoon",
             r"code|coding|build|app|startup|project|hackathon", "Weekend build time for something that's yours.",
             _simple("Build: {target}"), "your side project"),
    Template("journaling", "Journaling", "Wellbeing", "\u270D\uFE0F", 3, 0.25, [1, 3, 6], "Evening",
             r"journal|write|writing|reflect|diary", "Short reflection three evenings a week.", _simple("Journal 15 min")),
]}

BALANCED_DEFAULTS = ["reading", "hiking", "meditation", "friends"]
IDEAS = [
    ("🌄", "Sunrise hilltop hike", "Outdoors", 3, "Morning"),
    ("☕", "New café + 30 pages of a book", "Reading", 1.5, "Afternoon"),
    ("🏃", "5 km run by the lake", "Fitness", 0.75, "Morning"),
    ("🍜", "Cook a dish from another country", "Creative", 1.5, "Evening"),
    ("📷", "Photo walk: find 10 interesting doors", "Creative", 1, "Afternoon"),
    ("🎲", "Board game night with friends", "Social", 2, "Evening"),
    ("🖼️", "Visit a museum or gallery", "Creative", 2, "Afternoon"),
    ("🚴", "Cycle somewhere you've never been", "Fitness", 1.5, "Morning"),
    ("🤝", "Volunteer for an hour", "Social", 1, "Afternoon"),
    ("✏️", "Sketch the view from a rooftop", "Creative", 1, "Evening"),
    ("🏊", "Swim 20 laps", "Fitness", 1, "Morning"),
    ("📞", "Call an old friend and go for a walk", "Social", 1, "Evening"),
    ("🌅", "Watch the sunset somewhere new", "Outdoors", 1, "Evening"),
    ("🎸", "Learn 3 chords on a guitar", "Creative", 0.75, "Evening"),
    ("🧺", "Picnic in the park", "Social", 2, "Afternoon"),
    ("🔭", "Stargazing away from city lights", "Outdoors", 1.5, "Evening"),
]


def books_for(interests: str) -> list[str]:
    low = interests.lower()
    for genre, pat in GENRE_WORDS.items():
        if re.search(pat, low):
            return BOOKS[genre]
    return BOOKS["general"]


def match_templates(interests: str) -> list[str]:
    low = interests.lower()
    keys = [k for k, t in TEMPLATES.items() if re.search(t.keywords, low)]
    if "half-marathon" in keys and "5k" in keys:
        keys.remove("5k")
    return keys


def suggest(interests: str, study_hours_next_week: float = 0.0, existing: list[Goal] | None = None,
            daily_cap: float = 3.0, limit: int = 6) -> list[dict]:
    """Recommend activities for the interests given, sized to next week's study load."""
    have = {g.template for g in existing or []}
    heavy = study_hours_next_week >= 0.7 * daily_cap * 7
    keys = [k for k in match_templates(interests) if k not in have]
    for k in (["meditation"] if heavy else []) + BALANCED_DEFAULTS:
        if len(keys) >= limit:
            break
        if k not in keys and k not in have:
            keys.append(k)
    books = books_for(interests)
    out = []
    for k in keys[:limit]:
        t = TEMPLATES[k]
        weekly = round(t.sessions_per_week * t.hours, 2)
        load = (f"Busy week ahead ({study_hours_next_week:g}h of study planned), so StudyPilot starts this light."
                if heavy else f"Fits next to {study_hours_next_week:g}h of planned study next week.")
        s = {
            "template": k, "title": t.title, "emoji": t.emoji, "category": t.category,
            "sessions_per_week": t.sessions_per_week, "hours": t.hours, "weekly_hours": weekly,
            "days": [DAY_NAMES[d] for d in t.days], "time": t.time,
            "why": f"{t.pitch} {load}", "matched": k in match_templates(interests),
            "target": books[0] if k == "reading" else t.default_target,
        }
        if k == "reading":
            s["books"] = books
        out.append(s)
    return out


@dataclass
class LifeConfig:
    study_start: time = time(18, 0)
    daily_cap: float = 3.0
    weeks: int = 4
    slots: dict[str, time] = field(default_factory=lambda: {"Morning": time(7, 0), "Afternoon": time(15, 0)})

    def slot(self, name: str) -> time:
        if name == "Evening":
            end = datetime.combine(date.today(), self.study_start) + timedelta(hours=self.daily_cap)
            return end.time()
        return self.slots.get(name, time(7, 0))


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def light_weeks(study_plan: Plan, items: list[Item], today: date, cfg: LifeConfig) -> set[date]:
    """Weeks with heavy study load or an exam are 'light' weeks for life activities."""
    out: set[date] = set()
    per_week: dict[date, float] = {}
    for d, h in study_plan.hours_by_day("Study").items():
        per_week[_week_start(d)] = per_week.get(_week_start(d), 0.0) + h
    for w, h in per_week.items():
        if h >= 0.7 * cfg.daily_cap * 7:
            out.add(w)
    for i in items:
        if i.type == "Exam" and i.status != "Done" and i.due >= today:
            out.add(_week_start(i.due))
    return out


def plan_life(goals: list[Goal], today: date, study_plan: Plan, items: list[Item] | None = None,
              cfg: LifeConfig | None = None, tz=None) -> tuple[list[Session], set[date]]:
    """Schedule active goals for the next few weeks in slots that don't clash with study blocks.

    In light weeks each goal runs about half as often and long activities shrink.
    On days already at the study cap only short (<= 30 min) activities are kept.
    """
    cfg = cfg or LifeConfig()
    items = items or []
    study_load = study_plan.hours_by_day("Study")
    light = light_weeks(study_plan, items, today, cfg)
    used: dict[tuple[date, str], float] = {}
    sessions: list[Session] = []
    life_load: dict[date, float] = {}
    first_week = _week_start(today)

    def goal_days(g: Goal) -> list[int]:
        tmpl = TEMPLATES.get(g.template)
        return sorted(set(g.days)) or (tmpl.days if tmpl else [0, 3])

    active = [g for g in goals if g.status == "Active"]
    active.sort(key=lambda g: g.sessions_per_week < len(goal_days(g)))  # fixed-day goals first
    for g in active:
        tmpl = TEMPLATES.get(g.template)
        days = goal_days(g)
        start = g.start or today
        for w in range(cfg.weeks):
            wk = first_week + timedelta(weeks=w)
            is_light = wk in light
            n = max(1, math.ceil(g.sessions_per_week / 2)) if is_light else g.sessions_per_week
            if n < len(days):  # flexible goal: use the days with the least life already planned
                order = _spread(days, len(days))
                chosen = sorted(sorted(order, key=lambda d: life_load.get(wk + timedelta(days=d), 0.0))[:n])
            else:
                chosen = days
            week_index = max(0, (wk - _week_start(start)).days // 7)
            for k, wd in enumerate(chosen):
                day = wk + timedelta(days=wd)
                if day < today or (day == today and datetime.now(tz).time() > cfg.slot(g.time)):
                    continue
                label, hours = (tmpl.label(g, week_index, k, is_light) if tmpl and tmpl.label else (g.title, g.hours))
                if is_light and hours > 1.5:
                    hours = 1.5
                if study_load.get(day, 0.0) >= cfg.daily_cap - 1e-6 and hours > 0.5:
                    continue
                slot = g.time if g.time in TIMES else "Evening"
                offset = used.get((day, slot), 0.0)
                start_dt = datetime.combine(day, cfg.slot(slot), tzinfo=tz) + timedelta(hours=offset)
                used[(day, slot)] = offset + hours
                life_load[day] = life_load.get(day, 0.0) + hours
                emoji = tmpl.emoji if tmpl else "\u2728"
                sessions.append(Session(item_title=g.title, start=start_dt, hours=hours, item_type=g.category,
                                        kind="Life", label=f"{emoji} {label}", goal_notion_id=g.notion_id))
    sessions.sort(key=lambda s: s.start)
    return sessions, light


def surprise(
    plan: Plan,
    today: date,
    cfg: LifeConfig,
    tz=None,
    rng: random.Random | None = None,
    interests: str = "",
) -> dict | None:
    """Choose a free time slot and a matching micro-adventure."""
    rng = rng or random.Random()
    matched_categories = {TEMPLATES[key].category for key in match_templates(interests)}
    now = datetime.now(tz)
    study_hours = plan.hours_by_day("Study")
    candidates = []
    weights = []
    for offset in range(7):
        day = today + timedelta(days=offset)
        day_study = study_hours.get(day, 0.0)
        for slot in ("Morning", "Afternoon", "Evening"):
            start = datetime.combine(day, cfg.slot(slot), tzinfo=tz)
            if day == today and start <= now:
                continue
            for emoji, title, category, hours, preferred_time in IDEAS:
                if hours > 0.5 and day_study >= cfg.daily_cap:
                    continue
                end = start + timedelta(hours=hours)
                if any(start < session.end and end > session.start for session in plan.sessions):
                    continue
                candidates.append((emoji, title, category, hours, start, end, slot))
                weight = 3 if preferred_time == slot else 1
                if category in matched_categories:
                    weight *= 3
                if day.weekday() >= 5:
                    weight *= 2
                weights.append(weight)
    if not candidates:
        return None
    emoji, title, category, hours, start, end, slot = rng.choices(candidates, weights=weights, k=1)[0]
    week_label = plan.weeks[0]["label"] if plan.weeks else None
    why = f"You're free {start:%A} {slot.lower()}"
    if week_label:
        why += f", and next week is {week_label}"
    return {
        "emoji": emoji,
        "title": title,
        "category": category,
        "hours": hours,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "why": why + ".",
    }


def _spread(days: list[int], n: int) -> list[int]:
    if n >= len(days):
        return days
    step = len(days) / n
    return sorted({days[int(i * step)] for i in range(n)})
