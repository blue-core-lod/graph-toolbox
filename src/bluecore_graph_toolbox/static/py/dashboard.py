"""The Dashboard's Pinned searches and Saved settings (graph-toolbox #38).

Runs in the browser under PyScript, next to ``saved.py`` (the LocalStorage
adapter, #44). The page loads both through PyScript's ``files`` config and
calls ``main()``. The server describes where entries open in the
``#dashboard-config`` JSON block (see ``dashboard/page.py``).

``search_rows`` and ``setting_rows`` turn saved entries into plain row data and
are tested under pytest; ``Dashboard`` only puts those rows on the page. All
saved text goes in with ``textContent``, never as HTML.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import saved

# Shown in a table before the browser code has run, and replaced by it.
EMPTY_SEARCHES = "No pinned searches yet. Searches you pin will show here."
EMPTY_SETTINGS = "No saved settings yet. Job settings you save will show here."
NO_STORAGE = (
    "This browser isn't letting the Toolbox save anything, "
    "so there's nothing to show here."
)
NEWER_TOOLBOX = "Saved by a newer Toolbox"
CANT_OPEN = "Can't be opened here"


def search_rows(
    entries: list[saved.Entry], pages: dict[str, dict[str, Any]], note: str
) -> list[dict[str, Any]]:
    """Rows for the Pinned searches table, most recently changed first.

    ``href`` is None when the search can't be rerun from here, and ``note``
    then says why.
    """
    rows = []
    for entry in entries:
        page = pages.get(entry.operation, {}).get("href") if entry.supported else None
        rows.append(
            {
                "id": entry.id,
                "name": entry.name,
                "href": f"{page}?search={quote(entry.id)}" if page else None,
                "note": None if page else (note if entry.supported else CANT_OPEN),
            }
        )
    return rows


def setting_rows(
    entries: list[saved.Entry], types: dict[str, dict[str, Any]], note: str
) -> list[dict[str, Any]]:
    """Rows for the Saved settings table, most recently changed first."""
    rows = []
    for entry in entries:
        kind = types.get(entry.operation) if entry.supported else None
        page = kind["href"] if kind else None
        rows.append(
            {
                "id": entry.id,
                "name": entry.name,
                "type": kind["label"] if kind else NEWER_TOOLBOX,
                # Stored as an ISO timestamp; the design shows the date.
                "modified": entry.modified[:10],
                "href": f"{page}?setting={quote(entry.id)}" if page else None,
                "note": None if page else (note if kind else CANT_OPEN),
            }
        )
    return rows


class Dashboard:
    """Puts the saved entries on the page and handles Unpin."""

    def __init__(self, document: Any, store: saved.SavedStore, config: dict) -> None:
        self.document = document
        self.store = store
        self.config = config

    def render(self) -> None:
        self.render_searches()
        self.render_settings()

    # ---- Pinned searches ------------------------------------------------------

    def render_searches(self) -> None:
        body = self._clear("pinned-searches-rows")
        if not self.store.available:
            self._message_row(body, NO_STORAGE, columns=2)
            return
        rows = search_rows(
            self.store.list(saved.SEARCH),
            self.config["searches"],
            self.config["unavailable_note"],
        )
        if not rows:
            self._message_row(body, EMPTY_SEARCHES, columns=2)
        for row in rows:
            tr = self._add(body, "tr")
            name = self._add(tr, "td")
            if row["href"]:
                self._add(name, "a", row["name"]).href = row["href"]
            else:
                self._add(name, "span", row["name"])
                self._add(name, "span", row["note"], cls="dashboard-note")
            unpin_cell = self._add(tr, "td", cls="dashboard-table__action")
            button = self._add(unpin_cell, "button", cls="dashboard-unpin")
            button.type = "button"
            button.setAttribute("aria-label", f"Unpin {row['name']}")
            button.appendChild(self._icon("dashboard-pin-icon"))
            button.addEventListener("click", self._proxy(self._unpin, row))

    def _unpin(self, row: dict[str, Any]) -> None:
        try:
            self.store.delete(saved.SEARCH, row["id"])
        except saved.StorageError as error:
            self._status("pinned-searches-status", str(error))
            return
        self.render_searches()
        self._status("pinned-searches-status", f"Unpinned {row['name']}.")

    # ---- Saved settings -------------------------------------------------------

    def render_settings(self) -> None:
        body = self._clear("saved-settings-rows")
        if not self.store.available:
            self._message_row(body, NO_STORAGE, columns=4)
            return
        rows = setting_rows(
            self.store.list(saved.SETTING),
            self.config["settings"],
            self.config["unavailable_note"],
        )
        if not rows:
            self._message_row(body, EMPTY_SETTINGS, columns=4)
        for row in rows:
            tr = self._add(body, "tr")
            self._add(tr, "td", row["name"])
            self._add(tr, "td", row["type"])
            self._add(tr, "td", row["modified"])
            action = self._add(tr, "td", cls="dashboard-table__action")
            if row["href"]:
                link = self._add(action, "a", "Use this setting", cls="toolbox-button")
                link.href = row["href"]
            else:
                button = self._add(
                    action, "span", "Use this setting", cls="toolbox-button"
                )
                button.setAttribute("aria-disabled", "true")
                self._add(action, "span", row["note"], cls="dashboard-note")

    # ---- DOM helpers ----------------------------------------------------------

    def _add(self, parent: Any, tag: str, text: str | None = None, cls: str = ""):
        element = self.document.createElement(tag)
        if text is not None:
            element.textContent = text
        if cls:
            element.className = cls
        parent.appendChild(element)
        return element

    def _clear(self, element_id: str) -> Any:
        body = self.document.getElementById(element_id)
        body.replaceChildren()
        return body

    def _message_row(self, body: Any, text: str, columns: int) -> None:
        cell = self._add(self._add(body, "tr"), "td", text, cls="dashboard-empty")
        cell.colSpan = columns

    def _icon(self, template_id: str) -> Any:
        template = self.document.getElementById(template_id)
        return template.content.firstElementChild.cloneNode(True)

    def _status(self, element_id: str, text: str) -> None:
        self.document.getElementById(element_id).textContent = text

    @staticmethod
    def _proxy(handler: Any, row: dict[str, Any]) -> Any:
        from pyodide.ffi import create_proxy

        return create_proxy(lambda _event: handler(row))


def main() -> None:
    """Fill in the Dashboard from this browser's saved entries."""
    from pyscript import document

    config = json.loads(document.getElementById("dashboard-config").textContent)
    Dashboard(document, saved.open_store(config["user_id"]), config).render()
