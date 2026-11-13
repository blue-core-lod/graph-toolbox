"""Routes for the Toolbox applications, all behind Airflow sign-in.

Relative to the plugin's mount point, ``/graph-toolbox``:

- ``GET /api/config``: browser-safe settings
- ``/dashboard``: Dashboard
- ``/marc-bibframe-operations``: MARC and BIBFRAME operations
- ``/sparql``: SPARQL Query and Update
- ``/ai-search``: AI search

Each application's routes live in its own package
"""

import bluecore_airflow_common as common
from bluecore_airflow_common.integration.settings import public_config
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from bluecore_graph_toolbox import __version__, deps
from bluecore_graph_toolbox.ai_search.routes import router as ai_search
from bluecore_graph_toolbox.dashboard.routes import router as dashboard
from bluecore_graph_toolbox.marc_bibframe_operations.routes import (
    router as marc_bibframe_operations,
)
from bluecore_graph_toolbox.sparql.routes import (
    router as sparql,
)

router = APIRouter(dependencies=[Depends(common.requires_login)])


class ToolboxConfig(BaseModel):
    """Everything ``/api/config`` sends to a browser.

    Fields that aren't declared here are dropped, so a setting only reaches the
    browser when someone adds it to this model on purpose.
    """

    version: str
    public_url: str


@router.get("/api/config")
def config(settings: deps.Settings) -> ToolboxConfig:
    # The Toolbox's version wins even if common's public_config adds its own.
    return ToolboxConfig(**{**public_config(settings), "version": __version__})


router.include_router(dashboard)
router.include_router(marc_bibframe_operations)
router.include_router(sparql)
router.include_router(ai_search)
