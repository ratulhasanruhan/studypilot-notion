"""In-memory stand-in for NotionClient, used by tests and `--demo` mode."""

from __future__ import annotations

import itertools
import uuid


class FakeNotion:
    def __init__(self):
        self.databases: dict[str, dict] = {}
        self.pages: dict[str, dict] = {}
        self.children: dict[str, list[dict]] = {}
        self._ids = itertools.count(1)

    def _id(self) -> str:
        return str(uuid.UUID(int=next(self._ids)))

    def me(self) -> dict:
        return {"name": "Demo workspace", "type": "bot"}

    def create_database(self, parent_page_id, title, properties, icon=None):
        db = {"id": self._id(), "title": title, "parent": parent_page_id, "properties": properties}
        self.databases[db["id"]] = db
        self.children.setdefault(parent_page_id, [])
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

    def append_children(self, block_id, children, after=None):
        target = self.pages[block_id]["children"] if block_id in self.pages else self.children.setdefault(block_id, [])
        ids = []
        for child in children:
            block = dict(child)
            block["id"] = self._id()
            if after:
                position = next((i for i, existing in enumerate(target) if existing.get("id") == after), None)
                if position is None:
                    raise ValueError(f"No block found for after anchor {after!r}")
                target.insert(position + 1, block)
            else:
                target.append(block)
            ids.append(block["id"])
            after = block["id"]
        return ids

    def delete_block(self, block_id):
        for children in [*self.children.values(), *(page["children"] for page in self.pages.values())]:
            for index, child in enumerate(children):
                if child.get("id") == block_id:
                    del children[index]
                    return {"id": block_id, "archived": True}
        raise ValueError(f"No block found with id {block_id!r}")

    def rows(self, database_id):
        return self.query_database(database_id)
