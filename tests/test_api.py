"""Tests for the Toolbox API: sign-in, the stubs, config and safe errors."""

from __future__ import annotations

from types import ModuleType

import pytest
from airflow_client.client.exceptions import ApiException
from bluecore_airflow_common.integration.errors import NotFound
from fastapi.dependencies.utils import get_flat_dependant
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from bluecore_graph_toolbox import __version__

ISSUES = "https://github.com/blue-core-lod/graph-toolbox/issues"

# Each application's path, the name its stub reports, and its ticket.
APPLICATIONS = {
    "/dashboard": ("dashboard", f"{ISSUES}/45"),
    "/marc-bibframe-operations": ("marc-bibframe-operations", f"{ISSUES}/46"),
    "/sparql": ("sparql", f"{ISSUES}/54"),
    "/ai-search": ("ai-search", f"{ISSUES}/39"),
}

SIGNED_IN_ROUTES = ["/api/config", *APPLICATIONS]

# A route that took one of these could let the browser pick the backend.
ENVIRONMENT_PARAMETERS = {
    "env",
    "environment",
    "api_url",
    "base_url",
    "bluecore_url",
    "internal_url",
}


def _api_routes(plugin: ModuleType) -> list[APIRoute]:
    return [route for route in plugin.app.routes if isinstance(route, APIRoute)]


@pytest.mark.parametrize("path", SIGNED_IN_ROUTES)
def test_api_routes_require_sign_in(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 401


@pytest.mark.parametrize("path", APPLICATIONS)
def test_application_stubs_say_they_are_not_built(
    signed_in_client: TestClient, path: str
) -> None:
    application, issue = APPLICATIONS[path]

    # No trailing slash, and no redirect to add one: behind the /workflows
    # proxy a redirect can lose the root path.
    response = signed_in_client.get(path, follow_redirects=False)

    assert response.status_code == 200
    assert response.json() == {
        "application": application,
        "implemented": False,
        "issue": issue,
    }


def test_config_sends_only_browser_safe_settings(signed_in_client: TestClient) -> None:
    response = signed_in_client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {
        "version": __version__,
        "public_url": "https://bcld.test",
    }
    assert "internal.test" not in response.text


def test_no_route_lets_the_browser_choose_an_environment(plugin: ModuleType) -> None:
    for route in _api_routes(plugin):
        dependant = get_flat_dependant(route.dependant)
        names = {
            param.alias
            for params in (
                dependant.path_params,
                dependant.query_params,
                dependant.header_params,
                dependant.cookie_params,
                dependant.body_params,
            )
            for param in params
        }
        assert not names & ENVIRONMENT_PARAMETERS, route.path


def test_no_route_runs_sparql_on_the_server(plugin: ModuleType) -> None:
    # SPARQL runs in the browser (#37, #47). The only route named for it is
    # the SPARQL stub, which takes no query. When #54 adds the bulk
    # update route, it starts a DAG run rather than running the query here.
    sparql = {
        (route.path, method)
        for route in _api_routes(plugin)
        if "sparql" in route.path.lower()
        for method in route.methods
    }

    assert sparql == {("/sparql", "GET")}


def test_integration_errors_return_the_safe_body(
    plugin: ModuleType, signed_in_client: TestClient
) -> None:
    @plugin.app.get("/_test/not-found")
    def not_found() -> None:
        raise NotFound("no run at http://airflow.internal.test/workflows/api/v2")

    response = signed_in_client.get("/_test/not-found")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    assert "internal.test" not in response.text


def test_airflow_errors_return_the_safe_body(
    plugin: ModuleType, signed_in_client: TestClient
) -> None:
    @plugin.app.get("/_test/airflow-forbidden")
    def airflow_forbidden() -> None:
        raise ApiException(status=403, reason="Forbidden")

    response = signed_in_client.get("/_test/airflow-forbidden")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert response.json()["error"]["upstream_status"] == 403
