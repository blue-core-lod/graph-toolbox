"""The Dashboard page (graph-toolbox #38): what its browser code is told.

Pinned searches and saved settings live in the browser's LocalStorage (#44), so
the page's PyScript (``static/py/dashboard.py``) lists them itself. The server
only tells it whose entries to open and where each kind of entry opens.

An entry opens on its tool's page with its id in the query string, which that
page reads back from the same store:

- a pinned search: ``<Search page>?search=<id>``
- a saved setting: ``<tool page>?setting=<id>``

A destination is None while its tool has no page yet, matching the left-hand
menu, so the Dashboard shows the entry without a working link.
"""

from __future__ import annotations

from typing import Any

from bluecore_graph_toolbox import nav

# Saved-setting operation (static/py/saved.py OPERATIONS) -> label for the
# Type column, and the menu item whose page restores it.
SETTING_TYPES = {
    "marc-to-bibframe": ("MARC to BIBFRAME", "marc-to-bibframe"),
    "bulk-update": ("SPARQL update", "sparql-update"),
}

# Pinned-search operation -> the menu item whose page reruns it.
SEARCH_PAGES = {"sparql": "search"}


def client_config(url_prefix: str, user_id: str) -> dict[str, Any]:
    """Everything the Dashboard's browser code needs, as JSON-safe data."""
    return {
        "user_id": user_id,
        "searches": {
            operation: {"href": nav.href(url_prefix, item)}
            for operation, item in SEARCH_PAGES.items()
        },
        "settings": {
            operation: {"label": label, "href": nav.href(url_prefix, item)}
            for operation, (label, item) in SETTING_TYPES.items()
        },
        "unavailable_note": nav.UNAVAILABLE_NOTE,
    }
