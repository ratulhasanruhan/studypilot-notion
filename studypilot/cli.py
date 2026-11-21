"""Command-line interface: `studypilot setup|import|plan|digest|serve`."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .core import Config, StudyPilot
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
        print(f"  {s.start:%a %b %d %H:%M}  {s.hours:>4}h  {s.title}")
    for title, h in plan.at_risk.items():
        print(f"  AT RISK: {title} needs {h}h more than fits before its deadline")
    print(f"{len(plan.sessions)} sessions {'previewed' if args.dry_run else 'written to Notion'}")


def cmd_digest(args) -> None:
    today = date.fromisoformat(args.today) if args.today else None
    d, url = _pilot().digest(today, publish=not args.dry_run)
    print(d.to_markdown())
    if url:
        print(f"\nPublished: {url}")


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

    s = sub.add_parser("plan", help="(re)schedule study sessions before every deadline")
    s.add_argument("--today", help="YYYY-MM-DD (default: today)")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("digest", help="publish a weekly digest page to Notion")
    s.add_argument("--today", help="YYYY-MM-DD (default: today)")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_digest)

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
