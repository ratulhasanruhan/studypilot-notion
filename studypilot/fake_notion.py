"""In-memory stand-in for NotionClient, used by tests and `--demo` mode."""

from __future__ import annotations

import itertools
import uuid


class FakeNotion:
    def __init__(self):
        self.databases: dict[str, dict] = {}
        self.pages: dict[str, dict] = {}
        self._ids = itertools.count(1)

    def _id(self) -> str:
        return str(uuid.UUID(int=next(self._ids)))

    def me(self) -> dict:
        return {"name": "Demo workspace", "type": "bot"}

    def create_database(self, parent_page_id, title, properties, icon=None):
        db = {"id": self._id(), "title": title, "parent": parent_page_id, "properties": properties}
        self.databases[db["id"]] = db
        return db

    def get_database(self, database_id):
        return self.databases[database_id]

    def update_database(self, database_id, properties=None, title=None):
        db = self.databases[database_id]
        if properties:
            db["properties"].update(properties)
        if title:
            db["title"] = title
        return db

    def query_database(self, database_id, filter=None, sorts=None):
        return [
            p for p in self.pages.values()
            if p["parent"].get("database_id") == database_id and not p["archived"]
        ]

    def create_page(self, parent, properties, children=None, icon=None):
        pid = self._id()
        page = {
            "id": pid,
            "parent": parent,
            "properties": properties,
            "children": list(children or []),
            "archived": False,
            "url": f"https://www.notion.so/{pid.replace('-', '')}",
        }
        self.pages[pid] = page
        return page

    def update_page(self, page_id, properties=None, archived=None):
        page = self.pages[page_id]
        if properties:
            page["properties"].update(properties)
        if archived is not None:
            page["archived"] = archived
        return page

    def append_children(self, block_id, children):
        self.pages[block_id]["children"].extend(children)

    def rows(self, database_id):
        return self.query_database(database_id)
