"""Vercel entry point for the StudyPilot web app."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if not os.environ.get("NOTION_TOKEN"):
    os.environ.setdefault("STUDYPILOT_DEMO", "1")
os.environ.setdefault("STUDYPILOT_CONFIG", "/tmp/studypilot.json")

from studypilot.web import app  # noqa: E402
