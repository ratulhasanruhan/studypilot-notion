"""Command-line interface for StudyPilot setup, planning and publishing."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .core import Config, StudyPilot
from .life import DAY_NAMES
from .notion import NotionClient, extract_id
from .syllabus import parse_syllabus


def _pilot() -> StudyPilot:
    return StudyPilot(NotionClient())


def cmd_setup(args) -> None:
    pilot = _pilot()
    if args.timezone:
        pilot.config.timezone = args.timezone
    cfg = pilot.bootstrap(extract_id(args.page))
    print(json.dumps({"ok": True, **cfg.__dict__}, indent=2))


def cmd_import(args) -> None:
    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text()
    term_start = date.fromisoformat(args.term_start) if args.term_start else None
    items = parse_syllabus(text, year=args.year, term_start=term_start, course=args.course)
    for i in items:
        print(f"  {i.due}  {i.type:<10} {i.hours:>4}h  {i.title}  [{i.course}]")
    if args.dry_run:
        print(f"{len(items)} deadlines found (dry run, nothing written)")
        return
    res = _pilot().import_items(items)
    print(f"Created {len(res['created'])}, skipped {len(res['skipped'])} duplicates")


def cmd_plan(args) -> None:
    pilot = _pilot()
    today = date.fromisoformat(args.today) if args.today else None
    plan = pilot.preview_plan(today) if args.dry_run else pilot.replan(today)
    for s in plan.sessions:
        print(f"  {s.start:%a %b %d %H:%M}  {s.hours:>4}h  {s.kind:<5}  {s.title}")
    for title, h in plan.at_risk.items():
        print(f"  AT RISK: {title} needs {h}h more than fits before its deadline")
    print(f"{len(plan.sessions)} sessions {'previewed' if args.dry_run else 'written to Notion'}\n")
    print("Balance score")
    for w in plan.weeks:
        print(f"  Week of {date.fromisoformat(w['start']):%b %d}: {w['score']:>3}/100 {w['label']:<12} "
              f"study {w['study_hours']}h, life {w['life_hours']}h - {w['tip']}")


def cmd_digest(args) -> None:
    today = date.fromisoformat(args.today) if args.today else None
    d, url = _pilot().digest(today, publish=not args.dry_run)
    print(d.to_markdown())
    if url:
        print(f"\nPublished: {url}")


def cmd_dashboard(args) -> None:
    pilot = _pilot()
    today = date.fromisoformat(args.today) if args.today else None
    ids = pilot.dashboard(today, args.after)
    print(f"Dashboard updated: {len(ids)} blocks")
    page = pilot.notion.get_page(pilot.config.parent_page_id)
    if page.get("url"):
        print(page["url"])


def cmd_surprise(args) -> None:
    pilot = _pilot()
    today = date.fromisoformat(args.today) if args.today else None
    idea = pilot.surprise(args.interests or "", today)
    if not idea:
        print("No free slot for a micro-adventure this week.")
        return
    print(f"{idea['emoji']} {idea['title']} · {idea['start']} · {idea['hours']}h")
    print(idea["why"])
    if args.add:
        pilot.add_surprise(idea)
        print("Added to your Schedule.")


def cmd_suggest(args) -> None:
    for s in _pilot().suggest(args.interests):
        print(f"{s['emoji']} {s['title']}  [{s['template']}]  {s['sessions_per_week']}x/week, {s['weekly_hours']}h  {s['time']} {'/'.join(s['days'])}")
        print(f"    {s['why']}")
        if s.get("books"):
            print(f"    Books: {'; '.join(s['books'])}")
    print("\nAdd one with: studypilot goal add <template> [--target ...]")


def cmd_goals(args) -> None:
    for g in _pilot().list_goals():
        days = "/".join(DAY_NAMES[d] for d in g.days)
        print(f"  [{g.status:<6}] {g.title}  {g.sessions_per_week}x{g.hours}h {g.time} {days}  {g.target}")


def cmd_goal(args) -> None:
    pilot = _pilot()
    if args.action == "add":
        days = [DAY_NAMES.index(d.strip().title()[:3]) for d in args.days.split(",")] if args.days else None
        g = pilot.add_goal(args.name, args.target or "", sessions_per_week=args.per_week, hours=args.hours,
                           days=days, time=args.time, title=args.title)
        print(f"Added life goal: {g.title} ({g.sessions_per_week}x/week). Run `studypilot plan` to schedule it.")
    else:
        status = {"pause": "Paused", "resume": "Active", "done": "Done"}[args.action]
        g = pilot.set_goal_status(args.name, status)
        print(f"{g.title} -> {status}")


def cmd_serve(args) -> None:
    import uvicorn

    uvicorn.run("studypilot.web:app", host=args.host, port=args.port, reload=False)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="studypilot", description="Syllabus -> Notion Student OS autopilot")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="create StudyPilot databases under a Notion page")
    s.add_argument("page", help="Notion page URL or ID (shared with your integration)")
    s.add_argument("--timezone", help="IANA timezone, e.g. Asia/Dhaka")
    s.set_defaults(func=cmd_setup)

    s = sub.add_parser("import", help="extract deadlines from a syllabus and add them to Notion")
    s.add_argument("file", help="syllabus text file, or - for stdin")
    s.add_argument("--course", help="course name (auto-detected if omitted)")
    s.add_argument("--year", type=int, help="year for dates without one")
    s.add_argument("--term-start", help="YYYY-MM-DD; dates before it roll into next year")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("plan", help="(re)schedule study sessions and life activities")
    s.add_argument("--today", help="YYYY-MM-DD (default: today)")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("digest", help="publish a weekly digest page to Notion")
    s.add_argument("--today", help="YYYY-MM-DD (default: today)")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_digest)

    s = sub.add_parser("dashboard", help="refresh the StudyPilot dashboard on its parent page")
    s.add_argument("--today", help="YYYY-MM-DD (default: today)")
    s.add_argument("--after", help="insert after this block ID")
    s.set_defaults(func=cmd_dashboard)

    s = sub.add_parser("surprise", help="find a free slot for a micro-adventure")
    s.add_argument("--interests", default="", help="interests to personalize the idea")
    s.add_argument("--add", action="store_true", help="add the idea to your Schedule")
    s.add_argument("--today", help="YYYY-MM-DD (default: today)")
    s.set_defaults(func=cmd_surprise)

    s = sub.add_parser("suggest", help="suggest life activities (hiking, running, reading...) that fit your load")
    s.add_argument("interests", help='e.g. "hiking, marathon, sci-fi books"')
    s.set_defaults(func=cmd_suggest)

    s = sub.add_parser("goals", help="list life goals")
    s.set_defaults(func=cmd_goals)

    s = sub.add_parser("goal", help="add, pause, resume or finish a life goal")
    s.add_argument("action", choices=["add", "pause", "resume", "done"])
    s.add_argument("name", help="template key for add (see `suggest`), or goal name")
    s.add_argument("--target", help="book, instrument, language, trail...")
    s.add_argument("--title", help="custom title")
    s.add_argument("--per-week", type=int)
    s.add_argument("--hours", type=float)
    s.add_argument("--days", help="e.g. Mon,Wed,Sat")
    s.add_argument("--time", choices=["Morning", "Afternoon", "Evening"])
    s.set_defaults(func=cmd_goal)

    s = sub.add_parser("serve", help="run the web app")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except Exception as e:  # surface API/config errors without a traceback
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
