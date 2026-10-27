"""Blue Core Graph Toolbox, served as an Airflow 3 plugin.

The plugin registers two things with Airflow:

1. A FastAPI application mounted into the Airflow API server at
   ``/graph-toolbox``, so its routes share Airflow's authentication.
2. An external view that adds a "Toolbox" item to the Airflow navigation.
   Because it supplies a ``url_route``, the Airflow UI renders the page in an
   iframe at ``/plugin/graph-toolbox``.

   Routes, relative to the prefix:

- ``GET /``: landing page (signed in)
- ``GET /health``: ``{"status", "version"}`` (public)
- ``/static/*`` and ``/static/bluecore/*``: assets (public)

Toolbox screens are built out in graph-toolbox #43 and #45-47.
"""

from __future__ import annotations

import pathlib

import bluecore_airflow_common as common
from airflow.api_fastapi.core_api.security import GetUserDep
from airflow.plugins_manager import AirflowPlugin
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse

from bluecore_graph_toolbox import __version__

PLUGIN_NAME = "bluecore_graph_toolbox"
TITLE = "Blue Core Graph Toolbox"

# The Airflow nav truncates long labels, so the nav item has its own short name.
NAV_LABEL = "Toolbox"

# Where the FastAPI app is mounted on the Airflow API server, and the path the
# Airflow UI uses for the iframe that wraps it. The route must be unique across
# plugins, or Airflow drops the view.
URL_PREFIX = "/graph-toolbox"
URL_ROUTE = "graph-toolbox"

PACKAGE_DIR = pathlib.Path(__file__).parent
STATIC_DIR = PACKAGE_DIR / "static"
TEMPLATES_DIR = PACKAGE_DIR / "templates"

app = FastAPI(title=TITLE, docs_url=None, redoc_url=None, openapi_url=None)
common.mount_static(app, STATIC_DIR)
templates = common.templates(TEMPLATES_DIR)

# Everything on this router needs a signed-in user, so screens added later are
# protected without each route having to remember to ask.
pages = APIRouter(dependencies=[Depends(common.requires_login)])


@pages.get("/", response_class=HTMLResponse)
def index(request: Request, user: GetUserDep) -> HTMLResponse:
    """Render the landing page."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=common.context(
            URL_PREFIX, title=TITLE, username=user.get_name(), version=__version__
        ),
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the plugin is loaded. Public, so it carries nothing sensitive."""
    return {"status": "ok", "version": __version__}


app.include_router(pages)


class GraphToolboxPlugin(AirflowPlugin):
    name = PLUGIN_NAME

    fastapi_apps = [  # noqa: RUF012
        {
            "app": app,
            "url_prefix": URL_PREFIX,
            "name": TITLE,
        }
    ]

    external_views = [  # noqa: RUF012
        {
            "name": NAV_LABEL,
            "href": f"{common.airflow_root_path()}{URL_PREFIX}/",
            "url_route": URL_ROUTE,
            "destination": "nav",
            # Rendered by the Airflow UI in an <img>, so the icon cannot pick up
            # the nav's text color and each color mode needs its own file.
            "icon": common.static_url(URL_PREFIX, "toolbox.svg"),
            "icon_dark_mode": common.static_url(URL_PREFIX, "toolbox-dark.svg"),
        }
    ]
