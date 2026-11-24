"""Shared fixtures for the Graph Toolbox plugin tests."""

from __future__ import annotations

import importlib
import pathlib
from collections.abc import Iterator
from types import ModuleType

import pymarc
import pytest
from airflow.api_fastapi.core_api.security import get_user
from bluecore_airflow_common.integration.settings import (
    BlueCoreSettings,
    get_settings,
)
from fastapi.testclient import TestClient
from pymarc.marcxml import record_to_xml

from bluecore_graph_toolbox import plugin as plugin_module

# A deployment's settings. The internal URLs must never reach a response.
SETTINGS = BlueCoreSettings(
    internal_url="http://bc-api.internal.test",
    public_url="https://bcld.test",
    airflow_internal_url="http://airflow.internal.test/workflows",
)

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
    has to be reloaded for each base path to see the change. Reloading also
    builds a new app, so overrides set by one test never reach the next.
    The Blue Core settings come from ``SETTINGS``, not the environment.
    """
    module = importlib.reload(plugin_module)
    module.app.dependency_overrides[get_settings] = lambda: SETTINGS
    return module


@pytest.fixture
def client(plugin: ModuleType) -> TestClient:
    """A browser with no Airflow cookie."""
    return TestClient(plugin.app)


def marc_records(count: int) -> list[pymarc.Record]:
    """Records numbered from 1, each with an 001 and a title."""
    records = []
    for number in range(1, count + 1):
        record = pymarc.Record()
        record.add_field(pymarc.Field(tag="001", data=f"rec{number}"))
        record.add_field(
            pymarc.Field(
                tag="245",
                indicators=pymarc.Indicators("0", "0"),
                subfields=[pymarc.Subfield("a", f"Title {number}")],
            )
        )
        records.append(record)
    return records


def mrc(count: int) -> bytes:
    """A binary MARC21 file of ``count`` records."""
    return b"".join(record.as_marc() for record in marc_records(count))


def marcxml(count: int) -> bytes:
    """A MARC XML file of ``count`` records."""
    body = b"".join(record_to_xml(r) for r in marc_records(count))
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<collection xmlns="http://www.loc.gov/MARC21/slim">' + body + b"</collection>"
    )


@pytest.fixture
def uploads_dir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> pathlib.Path:
    """An empty uploads volume."""
    directory = tmp_path / "uploads"
    monkeypatch.setenv("BLUECORE_UPLOADS_DIR", str(directory))
    return directory


@pytest.fixture
def signed_in_client(plugin: ModuleType) -> Iterator[TestClient]:
    """A browser whose Airflow cookie resolved to a user.

    The name contains markup so tests can check the page escapes it.
    """
    plugin.app.dependency_overrides[get_user] = lambda: StubUser("<b>cataloger</b>")
    yield TestClient(plugin.app)
    plugin.app.dependency_overrides.pop(get_user)
