"""Tests for the Graph Toolbox Airflow plugin: registration, URLs and access."""

from __future__ import annotations

import re
from types import ModuleType

from airflow.plugins_manager import AirflowPlugin
from fastapi.testclient import TestClient

from bluecore_graph_toolbox import __version__

STATIC_FILES = [
    "toolbox.css",
    "toolbox.svg",
    "toolbox-dark.svg",
    "blue-core-v1.svg",
    "bluecore/bluecore.css",
    "bluecore/bluecore.js",
]


def test_plugin_registers_app_and_nav_view(plugin: ModuleType) -> None:
    toolbox = plugin.GraphToolboxPlugin

    assert issubclass(toolbox, AirflowPlugin)
    assert toolbox.name == "bluecore_graph_toolbox"
    assert toolbox.fastapi_apps == [
        {"app": plugin.app, "url_prefix": "/graph-toolbox", "name": plugin.TITLE}
    ]
    [view] = toolbox.external_views
    assert view["name"] == "Toolbox"
    assert view["url_route"] == "graph-toolbox"
    assert view["destination"] == "nav"


def test_nav_urls_follow_base_url(plugin: ModuleType, root_path: str) -> None:
    [view] = plugin.GraphToolboxPlugin.external_views

    assert view["href"] == f"{root_path}/graph-toolbox/"
    assert view["icon"] == f"{root_path}/graph-toolbox/static/toolbox.svg"
    assert (
        view["icon_dark_mode"] == f"{root_path}/graph-toolbox/static/toolbox-dark.svg"
    )


def test_landing_page_requires_sign_in(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 401


def test_landing_page_shows_signed_in_user(signed_in_client: TestClient) -> None:
    response = signed_in_client.get("/")

    assert response.status_code == 200
    assert "Signed in as &lt;b&gt;cataloger&lt;/b&gt;" in response.text
    assert "<b>cataloger</b>" not in response.text
    assert f"Version {__version__}" in response.text


def test_landing_page_links_are_absolute(
    signed_in_client: TestClient, root_path: str
) -> None:
    html = signed_in_client.get("/").text
    static = f"{root_path}/graph-toolbox/static"

    local = [
        url
        for url in re.findall(r'(?:href|src)="([^"]+)"', html)
        if not url.startswith("https://")
    ]
    assert sorted(local) == sorted(
        [
            f"{static}/bluecore/bluecore.css",
            f"{static}/bluecore/bluecore.js",
            f"{static}/toolbox.css",
            f"{static}/blue-core-v1.svg",
        ]
    )


def test_health_is_public_and_minimal(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_static_files_are_served_without_sign_in(client: TestClient) -> None:
    for name in STATIC_FILES:
        response = client.get(f"/static/{name}")
        assert response.status_code == 200, name
