"""Blue Core Graph Toolbox, served as an Airflow 3 plugin.

The plugin registers two things with Airflow:

1. A FastAPI application mounted into the Airflow API server at
   ``/graph-toolbox``, so its routes share Airflow's authentication.
2. An external view that adds a "Toolbox" item to the Airflow navigation.
   Because it supplies a ``url_route``, the Airflow UI renders the page in an
   iframe at ``/plugin/graph-toolbox``.

   Routes, relative to the prefix:

- ``GET /``: Dashboard page (signed in)
- ``GET /api/config``: browser-safe settings (signed in)
- ``GET /dashboard``, ``/marc-bibframe-operations``, ``/sparql``:
  application stubs (signed in), see ``api``
- ``GET /health``: ``{"status", "version"}`` (public)
- ``/static/*`` and ``/static/bluecore/*``: assets (public)
"""

from __future__ import annotations

import hashlib
import pathlib

import bluecore_airflow_common as common
from airflow.plugins_manager import AirflowPlugin
from bluecore_airflow_common.integration.auth import install_token_redaction
from bluecore_airflow_common.integration.errors import install_error_handler
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse

from bluecore_graph_toolbox import __version__, api, deps, nav
from bluecore_graph_toolbox.dashboard import page as dashboard_page

PLUGIN_NAME = "bluecore_graph_toolbox"
TITLE = "Blue Core Graph Toolbox"

# The Airflow nav truncates long labels, so the nav item has its own short name.
NAV_LABEL = "Toolbox"

# Where the FastAPI app is mounted on the Airflow API server, and the path the
# Airflow UI uses for the iframe that wraps it. The route must be unique across
# plugins, or Airflow drops the view.
URL_PREFIX = "/graph-toolbox"
URL_ROUTE = "graph-toolbox"

# Job status waits for the job API (graph-toolbox #45).
JOBS_UNAVAILABLE = (
    "Job status is coming soon. Running and finished jobs will show here."
)

PACKAGE_DIR = pathlib.Path(__file__).parent
STATIC_DIR = PACKAGE_DIR / "static"
TEMPLATES_DIR = PACKAGE_DIR / "templates"

app = FastAPI(title=TITLE, docs_url=None, redoc_url=None, openapi_url=None)
install_error_handler(app)
install_token_redaction()
common.mount_static(app, STATIC_DIR)
templates = common.templates(TEMPLATES_DIR)

# Everything on this router needs a signed-in user, so screens added later are
# protected without each route having to remember to ask.
pages = APIRouter(dependencies=[Depends(common.requires_login)])


def _browser_module_url(name: str) -> str:
    """URL of a static/py module, with a hash of its contents.

    PyScript fetches these with fetch(), which the browser caches, so the hash
    makes a changed file a new URL and the browser never runs stale code.
    """
    digest = hashlib.sha256((STATIC_DIR / "py" / name).read_bytes()).hexdigest()
    return f"{common.static_url(URL_PREFIX, f'py/{name}')}?v={digest[:12]}"


@pages.get("/", response_class=HTMLResponse)
def index(request: Request, user_uid: deps.UserUid) -> HTMLResponse:
    """Render the Toolbox Dashboard (graph-toolbox #38)."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=nav.page_context(
            URL_PREFIX,
            active="dashboard",
            title=TITLE,
            dashboard_config=dashboard_page.client_config(URL_PREFIX, user_uid),
            pyscript_config={
                "files": {
                    _browser_module_url(name): f"./{name}"
                    for name in ("saved.py", "dashboard.py")
                }
            },
            jobs_unavailable=JOBS_UNAVAILABLE,
        ),
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the plugin is loaded. Public, so it carries nothing sensitive."""
    return {"status": "ok", "version": __version__}


app.include_router(pages)
app.include_router(api.router)


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
