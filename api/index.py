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

from urllib.parse import parse_qsl, urlencode  # noqa: E402

from studypilot.web import app as fastapi_app  # noqa: E402


async def app(scope, receive, send):
    """Restore the original request path that vercel.json passes as ?__path=."""
    if scope["type"] == "http":
        query = parse_qsl(scope.get("query_string", b"").decode(), keep_blank_values=True)
        path = next((v for k, v in query if k == "__path"), None)
        if path is not None:
            path = "/" + path.lstrip("/")
            rest = urlencode([(k, v) for k, v in query if k != "__path"]).encode()
            scope = {**scope, "path": path, "raw_path": path.encode(), "query_string": rest}
    await fastapi_app(scope, receive, send)
