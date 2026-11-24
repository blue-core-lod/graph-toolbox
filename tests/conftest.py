"""Shared fixtures for the Graph Toolbox plugin tests."""

from __future__ import annotations

import importlib
import pathlib
from collections.abc import Iterator
from types import ModuleType, SimpleNamespace

import pymarc
import pytest
from airflow.api_fastapi.core_api.security import get_user
from airflow_client.client import DagRunState
from airflow_client.client.exceptions import ApiException
from bluecore_airflow_common.integration.settings import (
    BlueCoreSettings,
    get_settings,
)
from fastapi.testclient import TestClient
from pymarc.marcxml import record_to_xml

from bluecore_graph_toolbox import deps
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
def reports_dir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> pathlib.Path:
    """An empty reports volume."""
    directory = tmp_path / "reports"
    monkeypatch.setenv("BLUECORE_REPORTS_DIR", str(directory))
    return directory


@pytest.fixture
def signed_in_client(plugin: ModuleType) -> Iterator[TestClient]:
    """A browser whose Airflow cookie resolved to a user.

    The name contains markup so tests can check the page escapes it.
    """
    plugin.app.dependency_overrides[get_user] = lambda: StubUser("<b>cataloger</b>")
    yield TestClient(plugin.app)
    plugin.app.dependency_overrides.pop(get_user)


class FakeDagRuns:
    """Stands in for ``DagRunApi``, the Airflow REST client, recording calls.

    ``runs`` holds the runs Airflow knows, by ID; ``error`` is raised by every
    call when set.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.runs: dict[str, SimpleNamespace] = {}
        self.error: Exception | None = None

    def _record(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append((name, args, kwargs))
        if self.error:
            raise self.error

    def trigger_dag_run(self, dag_id: str, body: object, **kwargs: object):
        self._record("trigger_dag_run", dag_id, body, **kwargs)
        run = SimpleNamespace(
            dag_id=dag_id,
            dag_run_id=body.dag_run_id,
            conf=body.conf,
            state=DagRunState.QUEUED,
            queued_at=None,
            start_date=None,
            end_date=None,
        )
        self.runs[body.dag_run_id] = run
        return run

    def get_dag_run(self, dag_id: str, dag_run_id: str, **kwargs: object):
        self._record("get_dag_run", dag_id, dag_run_id, **kwargs)
        return self._run(dag_id, dag_run_id)

    def patch_dag_run(self, dag_id: str, dag_run_id: str, body, **kwargs: object):
        self._record("patch_dag_run", dag_id, dag_run_id, body, **kwargs)
        run = self._run(dag_id, dag_run_id)
        run.state = DagRunState(body.state.value)
        return run

    def add(self, dag_run_id: str, state: str = "running", **conf: object):
        """A run Airflow already has."""
        self.runs[dag_run_id] = SimpleNamespace(
            dag_id=deps.MARC_DAG,
            dag_run_id=dag_run_id,
            conf=conf,
            state=DagRunState(state),
            queued_at=None,
            start_date=None,
            end_date=None,
        )

    def _run(self, dag_id: str, dag_run_id: str) -> SimpleNamespace:
        run = self.runs.get(dag_run_id)
        if run is None or run.dag_id != dag_id:
            raise ApiException(status=404, reason="Not Found")
        return run


@pytest.fixture
def dag_runs(plugin: ModuleType) -> FakeDagRuns:
    """The Airflow REST client the routes get, as a fake."""
    fake = FakeDagRuns()
    plugin.app.dependency_overrides[deps.dag_runs] = lambda: fake
    return fake
