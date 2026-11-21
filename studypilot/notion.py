"""Minimal Notion REST client (API version 2022-06-28)."""

from __future__ import annotations

import os
import re
import time
from typing import Any, Iterator

import requests

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"


class NotionError(RuntimeError):
    pass


def extract_id(url_or_id: str) -> str:
    """Return a dashed Notion ID from a page URL or raw ID."""
    s = url_or_id.strip().split("?")[0].replace("-", "")
    m = re.findall(r"[0-9a-fA-F]{32}", s)
    if not m:
        raise ValueError(f"No Notion ID found in {url_or_id!r}")
    h = m[-1].lower()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


class NotionClient:
    def __init__(self, token: str | None = None, session: requests.Session | None = None):
        self.token = token or os.environ.get("NOTION_TOKEN", "")
        if not self.token:
            raise NotionError("NOTION_TOKEN is not set")
        self.http = session or requests.Session()
        self.http.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": VERSION,
                "Content-Type": "application/json",
            }
        )

    def request(self, method: str, path: str, json: dict | None = None) -> dict:
        for attempt in range(5):
            r = self.http.request(method, f"{API}{path}", json=json, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(float(r.headers.get("Retry-After", 1 + attempt)))
                continue
            if r.status_code >= 400:
                try:
                    msg = r.json().get("message", r.text)
                except ValueError:
                    msg = r.text
                raise NotionError(f"{method} {path} -> {r.status_code}: {msg}")
            return r.json()
        raise NotionError(f"{method} {path} failed after retries")

    def me(self) -> dict:
        return self.request("GET", "/users/me")

    def get_page(self, page_id: str) -> dict:
        return self.request("GET", f"/pages/{page_id}")

    def get_database(self, database_id: str) -> dict:
        return self.request("GET", f"/databases/{database_id}")

    def create_database(self, parent_page_id: str, title: str, properties: dict, icon: str | None = None) -> dict:
        body: dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
        }
        if icon:
            body["icon"] = {"type": "emoji", "emoji": icon}
        return self.request("POST", "/databases", body)

    def update_database(self, database_id: str, properties: dict | None = None, title: str | None = None) -> dict:
        body: dict[str, Any] = {}
        if properties:
            body["properties"] = properties
        if title:
            body["title"] = [{"type": "text", "text": {"content": title}}]
        return self.request("PATCH", f"/databases/{database_id}", body)

    def query_database(self, database_id: str, filter: dict | None = None, sorts: list | None = None) -> Iterator[dict]:
        body: dict[str, Any] = {"page_size": 100}
        if filter:
            body["filter"] = filter
        if sorts:
            body["sorts"] = sorts
        while True:
            res = self.request("POST", f"/databases/{database_id}/query", body)
            yield from res["results"]
            if not res.get("has_more"):
                return
            body["start_cursor"] = res["next_cursor"]

    def create_page(self, parent: dict, properties: dict, children: list | None = None, icon: str | None = None) -> dict:
        body: dict[str, Any] = {"parent": parent, "properties": properties}
        if children:
            body["children"] = children[:100]
        if icon:
            body["icon"] = {"type": "emoji", "emoji": icon}
        page = self.request("POST", "/pages", body)
        if children and len(children) > 100:
            self.append_children(page["id"], children[100:])
        return page

    def update_page(self, page_id: str, properties: dict | None = None, archived: bool | None = None) -> dict:
        body: dict[str, Any] = {}
        if properties:
            body["properties"] = properties
        if archived is not None:
            body["archived"] = archived
        return self.request("PATCH", f"/pages/{page_id}", body)

    def append_children(self, block_id: str, children: list, after: str | None = None) -> list[str]:
        ids = []
        for i in range(0, len(children), 100):
            batch = children[i : i + 100]
            body = {"children": batch}
            if after:
                body["after"] = after
            response = self.request("PATCH", f"/blocks/{block_id}/children", body)
            results = response.get("results", [])
            # Notion may also return the existing siblings around the new blocks; keep only the new ones.
            new = results[: len(batch)] if after else results[-len(batch) :]
            ids.extend(block["id"] for block in new)
            if ids:
                after = ids[-1]
        return ids

    def delete_block(self, block_id: str) -> dict:
        return self.request("PATCH", f"/blocks/{block_id}", {"archived": True})
