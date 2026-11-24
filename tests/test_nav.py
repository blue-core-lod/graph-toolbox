"""Tests for the Toolbox's shared left-hand menu (graph-toolbox #50)."""

from __future__ import annotations

import re
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from bluecore_graph_toolbox import nav

# Tools whose pages haven't shipped yet. When one does, give its NavItem a
# path and move it out of this list.
UNAVAILABLE = ["search", "marc-to-bibframe", "sparql-update", "bulk-export"]


def items(menu: list[dict]) -> dict[str, dict]:
    return {item["id"]: item for group in menu for item in group["items"]}


def test_menu_matches_the_design() -> None:
    menu = nav.menu("/graph-toolbox", active="dashboard")

    assert [group["heading"] for group in menu] == [None, "Import or update", "Export"]
    assert [[item["label"] for item in group["items"]] for group in menu] == [
        ["Dashboard", "Search"],
        ["MARC to BIBFRAME", "SPARQL update"],
        ["Bulk export"],
    ]


def test_only_search_is_styled_as_search() -> None:
    menu = items(nav.menu("/graph-toolbox", active="dashboard"))

    assert [id for id, item in menu.items() if item["search"]] == ["search"]


def test_search_does_not_promise_ai() -> None:
    # No AI-assisted search service exists, so the menu mustn't offer one.
    menu = items(nav.menu("/graph-toolbox", active="dashboard"))

    assert "ai" not in menu["search"]["label"].lower()


@pytest.mark.parametrize("active", sorted(nav.ITEM_IDS))
def test_exactly_one_item_is_active(active: str) -> None:
    menu = items(nav.menu("/graph-toolbox", active=active))

    assert [id for id, item in menu.items() if item["active"]] == [active]


def test_unknown_active_item_is_an_error() -> None:
    with pytest.raises(ValueError, match="dashbaord"):
        nav.menu("/graph-toolbox", active="dashbaord")


def test_links_follow_base_url(plugin: ModuleType, root_path: str) -> None:
    menu = items(nav.menu("/graph-toolbox", active="dashboard"))

    assert menu["dashboard"]["href"] == f"{root_path}/graph-toolbox/"
    for id in UNAVAILABLE:
        assert menu[id]["href"] is None, id


def test_page_context_names_the_toolbox_in_the_header(plugin: ModuleType) -> None:
    context = nav.page_context("/graph-toolbox", active="dashboard", title="T")

    assert context["app_name"] == "TOOLBOX"
    assert context["current_app"] == "toolbox"
    assert context["title"] == "T"
    assert items(context["nav"])["dashboard"]["active"]


# ---- Rendered on a page ------------------------------------------------------


@pytest.fixture
def html(signed_in_client: TestClient) -> str:
    return signed_in_client.get("/").text


def nav_html(html: str) -> str:
    [menu] = re.findall(r'<nav class="toolbox-nav".*?</nav>', html, re.DOTALL)
    return menu


def test_page_has_one_labelled_menu(html: str) -> None:
    assert html.count('<nav class="toolbox-nav" aria-label="Toolbox">') == 1


def test_dashboard_is_the_current_page(html: str, root_path: str) -> None:
    menu = nav_html(html)

    [current] = re.findall(r'<a[^>]*aria-current="page"[^>]*>', menu)
    assert f'href="{root_path}/graph-toolbox/"' in current


def test_unavailable_tools_are_not_links(html: str) -> None:
    menu = nav_html(html)
    links = re.findall(r"<a\b.*?</a>", menu, re.DOTALL)

    # Dashboard is the only working destination for now.
    assert len(links) == 1
    assert "Dashboard" in links[0]
    for label in ["Search", "MARC to BIBFRAME", "SPARQL update", "Bulk export"]:
        disabled = re.search(
            rf'<span class="[^"]*" aria-disabled="true">(?:(?!</li>).)*?{label}'
            rf"(?:(?!</li>).)*?{nav.UNAVAILABLE_NOTE}",
            menu,
            re.DOTALL,
        )
        assert disabled, label


def test_groups_have_headings_that_label_their_lists(html: str) -> None:
    menu = nav_html(html)

    for heading in ["Import or update", "Export"]:
        [id] = re.findall(
            rf'<h2 class="toolbox-nav__heading" id="([^"]+)">{heading}</h2>', menu
        )
        assert f'aria-labelledby="{id}"' in menu


def test_search_icon_is_hidden_from_screen_readers(html: str) -> None:
    [icon] = re.findall(r'<svg class="toolbox-nav__icon"[^>]*>', nav_html(html))

    assert 'aria-hidden="true"' in icon
    assert 'focusable="false"' in icon
