"""Shared fixtures for the Graph Toolbox plugin tests."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from types import ModuleType

import pytest
from airflow.api_fastapi.core_api.security import get_user
from fastapi.testclient import TestClient

from bluecore_graph_toolbox import plugin as plugin_module

# [api] base_url values, with the path each one should put in front of every
# URL: Airflow at the root, proxied under /workflows, and not set at all.
BASE_URLS = {
    "root": ("http://localhost:8080/", ""),
    "workflows": ("http://localhost/workflows", "/workflows"),
    "unset": ("", ""),
}


class StubUser:
    """Stands in for the user Airflow resolves from its JWT cookie."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.id = name

    def get_name(self) -> str:
        return self.name

    def get_id(self) -> str:
        return self.id


@pytest.fixture(params=sorted(BASE_URLS))
def root_path(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """Set [api] base_url and return the root path URLs should start with."""
    base_url, path = BASE_URLS[request.param]
    monkeypatch.setenv("AIRFLOW__API__BASE_URL", base_url)
    return path


@pytest.fixture
def plugin(root_path: str) -> ModuleType:
    """The plugin module, imported again under the current base_url.

    The nav link and icon URLs are built when the module is imported, so it
    has to be reloaded for each base path to see the change.
    """
    return importlib.reload(plugin_module)


@pytest.fixture
def client(plugin: ModuleType) -> TestClient:
    """A browser with no Airflow cookie."""
    return TestClient(plugin.app)


@pytest.fixture
def signed_in_client(plugin: ModuleType) -> Iterator[TestClient]:
    """A browser whose Airflow cookie resolved to a user.

    The name contains markup so tests can check the page escapes it.
    """
    plugin.app.dependency_overrides[get_user] = lambda: StubUser("<b>cataloger</b>")
    yield TestClient(plugin.app)
    plugin.app.dependency_overrides.clear()
