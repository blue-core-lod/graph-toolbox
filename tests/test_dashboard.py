"""Tests for the Toolbox Dashboard page (graph-toolbox #38).

The page is rendered by the server; its Pinned searches and Saved settings rows
are filled in the browser by static/py/dashboard.py, whose row logic is tested
here by loading it the same way test_saved.py loads saved.py.
"""

from __future__ import annotations

import hashlib
import html
import importlib.util
import json
import re
import sys
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from bluecore_graph_toolbox import nav
from bluecore_graph_toolbox.dashboard import page
from bluecore_graph_toolbox.plugin import STATIC_DIR

# ---- The page ---------------------------------------------------------------


@pytest.fixture
def dashboard_html(signed_in_client: TestClient) -> str:
    response = signed_in_client.get("/")
    assert response.status_code == 200
    return response.text


def config_block(text: str) -> dict:
    [raw] = re.findall(
        r'<script type="application/json" id="dashboard-config">(.*?)</script>', text
    )
    return json.loads(raw)


def test_dashboard_requires_sign_in(client: TestClient) -> None:
    assert client.get("/").status_code == 401


def test_dashboard_has_heading_and_three_collapsible_sections(
    dashboard_html: str,
) -> None:
    assert '<h1 class="dashboard-title">Toolbox dashboard</h1>' in dashboard_html
    headings = re.findall(
        r'<details class="dashboard-section" open>\s*<summary>\s*'
        r'<h2 class="dashboard-section__heading">\s*([^<]+?)\s*<',
        dashboard_html,
    )
    assert headings == ["Pinned searches", "Saved settings", "Job status"]


def test_table_headers_match_the_design(dashboard_html: str) -> None:
    headers = [
        re.sub(r"<[^>]+>", "", cell).strip()
        for cell in re.findall(r'<th scope="col"[^>]*>(.*?)</th>', dashboard_html)
    ]
    assert headers == [
        "Search",
        "Unpin",
        "Setting name",
        "Type",
        "Last modified",
        "Open",
        "File name",
        "Status",
        "# MARC records",
        "# entities",
        "Job profile",
        "User",
    ]


def test_job_status_says_it_is_coming(plugin: ModuleType, dashboard_html: str) -> None:
    assert plugin.JOBS_UNAVAILABLE in dashboard_html


def test_dashboard_is_current_in_the_menu(dashboard_html: str) -> None:
    [current] = re.findall(r"<a[^>]*aria-current=\"page\"[^>]*>", dashboard_html)
    assert "graph-toolbox/" in current


def test_config_names_the_signed_in_user(dashboard_html: str) -> None:
    # StubUser's id is "<b>cataloger</b>": it must reach the browser intact
    # as JSON, never as markup.
    assert "<b>cataloger</b>" not in dashboard_html
    assert config_block(dashboard_html)["user_id"] == "<b>cataloger</b>"


def test_config_hides_destinations_that_have_no_page(dashboard_html: str) -> None:
    config = config_block(dashboard_html)

    assert config["searches"] == {"sparql": {"href": None}}
    assert config["settings"] == {
        "marc-to-bibframe": {"label": "MARC to BIBFRAME", "href": None},
        "bulk-update": {"label": "SPARQL update", "href": None},
    }
    assert config["unavailable_note"] == nav.UNAVAILABLE_NOTE


def test_pyscript_loads_both_modules_from_the_plugin(
    dashboard_html: str, root_path: str
) -> None:
    [raw] = re.findall(r"<script type=\"py\" config='([^']*)'>", dashboard_html)
    files = json.loads(html.unescape(raw))["files"]
    static = f"{root_path}/graph-toolbox/static"

    # Each URL carries a hash of the file, so a changed file is a new URL.
    assert sorted(files.values()) == ["./dashboard.py", "./saved.py"]
    for url, name in files.items():
        path, version = url.split("?v=")
        assert path == f"{static}/py/{name[2:]}"
        digest = hashlib.sha256((STATIC_DIR / "py" / name[2:]).read_bytes())
        assert version == digest.hexdigest()[:12]


def test_dashboard_module_is_served(client: TestClient) -> None:
    assert client.get("/static/py/dashboard.py").status_code == 200


def test_destinations_follow_the_menu(
    plugin: ModuleType, root_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Once a tool's page exists, its saved entries link to it.
    menu = tuple(
        nav.NavGroup(
            group.heading,
            tuple(
                nav.NavItem(item.id, item.label, f"/{item.id}", item.search)
                if item.path is None
                else item
                for item in group.items
            ),
        )
        for group in nav.MENU
    )
    monkeypatch.setattr(nav, "MENU", menu)

    config = page.client_config("/graph-toolbox", "u")

    assert config["searches"]["sparql"]["href"] == f"{root_path}/graph-toolbox/search"
    assert (
        config["settings"]["bulk-update"]["href"]
        == f"{root_path}/graph-toolbox/sparql-update"
    )


def test_unknown_menu_item_is_an_error() -> None:
    with pytest.raises(ValueError, match="nope"):
        nav.href("/graph-toolbox", "nope")


# ---- Row logic (static/py/dashboard.py) --------------------------------------


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        name, STATIC_DIR / "py" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


saved = _load("saved")
dashboard = _load("dashboard")

NOTE = "Coming soon"


def entry(kind: str, operation: str, **fields) -> saved.Entry:
    values = {
        "id": "id 1",
        "kind": kind,
        "name": "My entry",
        "operation": operation,
        "payload": {},
        "created": "2026-08-01T10:00:00+00:00",
        "modified": "2026-08-20T10:00:00+00:00",
        "user": "u",
        "schema_version": saved.SCHEMA_VERSION,
    }
    return saved.Entry(**{**values, **fields})


def test_search_row_links_to_its_page_with_the_id() -> None:
    [row] = dashboard.search_rows(
        [entry(saved.SEARCH, "sparql")], {"sparql": {"href": "/t/search"}}, NOTE
    )

    assert row == {
        "id": "id 1",
        "name": "My entry",
        "href": "/t/search?search=id%201",
        "note": None,
    }


def test_search_row_without_a_page_is_not_a_link() -> None:
    [row] = dashboard.search_rows(
        [entry(saved.SEARCH, "sparql")], {"sparql": {"href": None}}, NOTE
    )

    assert (row["href"], row["note"]) == (None, NOTE)


def test_search_from_a_newer_toolbox_is_listed_but_not_linked() -> None:
    [row] = dashboard.search_rows(
        [entry(saved.SEARCH, "ai-search")], {"sparql": {"href": "/t/search"}}, NOTE
    )

    assert (row["name"], row["href"], row["note"]) == (
        "My entry",
        None,
        dashboard.CANT_OPEN,
    )


def test_setting_row_has_type_date_and_link() -> None:
    types = {"marc-to-bibframe": {"label": "MARC to BIBFRAME", "href": "/t/m2bf"}}

    [row] = dashboard.setting_rows(
        [entry(saved.SETTING, "marc-to-bibframe")], types, NOTE
    )

    assert row == {
        "id": "id 1",
        "name": "My entry",
        "type": "MARC to BIBFRAME",
        "modified": "2026-08-20",
        "href": "/t/m2bf?setting=id%201",
        "note": None,
    }


def test_setting_row_without_a_page_says_coming_soon() -> None:
    types = {"bulk-update": {"label": "SPARQL update", "href": None}}

    [row] = dashboard.setting_rows([entry(saved.SETTING, "bulk-update")], types, NOTE)

    assert (row["type"], row["href"], row["note"]) == ("SPARQL update", None, NOTE)


def test_setting_from_a_newer_toolbox_is_listed_but_not_linked() -> None:
    [row] = dashboard.setting_rows([entry(saved.SETTING, "load-rdf")], {}, NOTE)

    assert (row["type"], row["href"], row["note"]) == (
        dashboard.NEWER_TOOLBOX,
        None,
        dashboard.CANT_OPEN,
    )


def test_ids_are_escaped_in_links() -> None:
    [row] = dashboard.search_rows(
        [entry(saved.SEARCH, "sparql", id="a&b=c")],
        {"sparql": {"href": "/t/search"}},
        NOTE,
    )

    assert row["href"] == "/t/search?search=a%26b%3Dc"
