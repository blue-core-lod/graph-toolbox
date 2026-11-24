"""The Toolbox's left-hand menu, shared by every Toolbox page (graph-toolbox #50).

The menu is defined once here and rendered by ``templates/toolbox/_nav.html``,
which ``templates/toolbox/base.html`` includes. A page renders through
``page_context``, naming the menu item it belongs to::

    templates.TemplateResponse(
        request=request,
        name="dashboard.html",  # extends "toolbox/base.html"
        context=nav.page_context(URL_PREFIX, active="dashboard", title=...),
    )

An item with no ``path`` has no page yet: it's shown, but disabled and marked
"Coming soon", instead of linking somewhere that doesn't work. When a tool's
page ships, give its item a ``path``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import bluecore_airflow_common as common

# This app's id in the shared Blue Core header (bluecore-airflow-common).
HEADER_APP = "toolbox"

# Shown on, and read out for, an item whose page doesn't exist yet.
UNAVAILABLE_NOTE = "Coming soon"


@dataclass(frozen=True)
class NavItem:
    id: str
    label: str
    # Relative to the plugin's mount point; None while the tool has no page.
    path: str | None = None
    # Styled as the Search button in the design (filled, with an icon).
    search: bool = False


@dataclass(frozen=True)
class NavGroup:
    # None for the ungrouped items at the top of the menu.
    heading: str | None
    items: tuple[NavItem, ...]


# Dashboard isn't in the design; it's here so every page has a way back
# (graph-toolbox #50). The other pages arrive with #39 (Search), #40 (MARC
# to BIBFRAME) and #55 (SPARQL); Bulk export has no ticket yet.
#
# Search is plain "Search" until an AI-assisted search service exists: the
# menu must not promise AI the backend can't provide.
MENU: tuple[NavGroup, ...] = (
    NavGroup(
        None,
        (
            NavItem("dashboard", "Dashboard", path="/"),
            NavItem("search", "Search", search=True),
        ),
    ),
    NavGroup(
        "Import or update",
        (
            NavItem("marc-to-bibframe", "MARC to BIBFRAME"),
            NavItem("sparql-update", "SPARQL update"),
        ),
    ),
    NavGroup("Export", (NavItem("bulk-export", "Bulk export"),)),
)

ITEM_IDS = frozenset(item.id for group in MENU for item in group.items)


def menu(url_prefix: str, active: str) -> list[dict[str, Any]]:
    """Return the menu as template data, with absolute links and the active item.

    Links start with Airflow's root path (``/workflows`` in the bluecore-stack),
    so they work from any page, however deeply it's nested.

    Raises:
        ValueError: if ``active`` isn't a menu item, so a typo in a page can't
            silently leave nothing highlighted.
    """
    if active not in ITEM_IDS:
        raise ValueError(f"unknown Toolbox menu item: {active!r}")
    root = f"{common.airflow_root_path()}{url_prefix}"
    return [
        {
            "heading": group.heading,
            "items": [
                {
                    "id": item.id,
                    "label": item.label,
                    "href": None if item.path is None else f"{root}{item.path}",
                    "active": item.id == active,
                    "search": item.search,
                }
                for item in group.items
            ],
        }
        for group in MENU
    ]


def href(url_prefix: str, item_id: str) -> str | None:
    """Return a menu item's absolute link, or None while it has no page.

    Lets other parts of a page (the Dashboard's "Use this setting", say) link to
    a tool only when the menu does.
    """
    for group in MENU:
        for item in group.items:
            if item.id == item_id:
                if item.path is None:
                    return None
                return f"{common.airflow_root_path()}{url_prefix}{item.path}"
    raise ValueError(f"unknown Toolbox menu item: {item_id!r}")


def page_context(url_prefix: str, active: str, **extra: Any) -> dict[str, Any]:
    """Build the template context for a Toolbox page.

    Adds what every Toolbox page shares (the header's app name and the left
    menu, with ``active`` highlighted) to bluecore-airflow-common's context.
    """
    return common.context(
        url_prefix,
        app_name=HEADER_APP.upper(),
        current_app=HEADER_APP,
        nav=menu(url_prefix, active),
        nav_unavailable_note=UNAVAILABLE_NOTE,
        **extra,
    )
