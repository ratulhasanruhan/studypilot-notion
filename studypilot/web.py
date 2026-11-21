"""FastAPI web app for StudyPilot."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .core import Config, StudyPilot
from .models import Item
from .notion import NotionClient, NotionError, extract_id
from .syllabus import parse_syllabus

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="StudyPilot")
_pilot: StudyPilot | None = None


def pilot() -> StudyPilot:
    global _pilot
    if _pilot is None:
        if os.environ.get("STUDYPILOT_DEMO") or not os.environ.get("NOTION_TOKEN"):
            from .fake_notion import FakeNotion

            _pilot = StudyPilot(FakeNotion(), Config(), config_path=Path(os.devnull))
            _pilot.demo = True
        else:
            _pilot = StudyPilot(NotionClient())
            _pilot.demo = False
    return _pilot


class SetupIn(BaseModel):
    page: str
    timezone: str | None = None


class ParseIn(BaseModel):
    text: str
    course: str | None = None
    year: int | None = None
    term_start: date | None = None


class ImportIn(BaseModel):
    items: list[dict]


class DayIn(BaseModel):
    today: date | None = None
    daily_cap: float | None = None


def _guard(fn):
    try:
        return fn()
    except (NotionError, RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    p = pilot()
    return {"demo": p.demo, "ready": p.config.ready, "config": p.config.__dict__}


@app.post("/api/setup")
def setup(body: SetupIn):
    p = pilot()
    if body.timezone:
        p.config.timezone = body.timezone
    page_id = "demo-page" if p.demo and not body.page.strip() else body.page
    return _guard(lambda: p.bootstrap(page_id if p.demo else extract_id(page_id)).__dict__)


@app.post("/api/parse")
def parse(body: ParseIn):
    items = parse_syllabus(body.text, year=body.year, term_start=body.term_start, course=body.course)
    return {"items": [i.to_dict() for i in items]}


@app.post("/api/import")
def import_items(body: ImportIn):
    items = [Item.from_dict(d) for d in body.items]
    return _guard(lambda: pilot().import_items(items))


@app.get("/api/items")
def items():
    return _guard(lambda: {"items": [i.to_dict() for i in pilot().list_items()]})


def _apply(body: DayIn):
    if body.daily_cap:
        pilot().config.daily_cap = body.daily_cap


@app.post("/api/plan")
def plan(body: DayIn):
    _apply(body)
    return _guard(lambda: pilot().replan(body.today).to_dict())


@app.post("/api/digest")
def digest(body: DayIn):
    _apply(body)

    def run():
        d, url = pilot().digest(body.today)
        return {**d.to_dict(), "url": url}

    return _guard(run)
