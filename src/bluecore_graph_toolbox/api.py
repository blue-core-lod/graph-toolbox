"""Routes for the Toolbox applications, all behind Airflow sign-in.

Relative to the plugin's mount point, ``/graph-toolbox``:

- ``GET /api/config``: browser-safe settings and the signed-in user's ID
- ``/dashboard``: Dashboard
- ``/marc-bibframe-operations``: MARC and BIBFRAME operations
- ``/sparql``: SPARQL Query and Update supported by Blue Core search

Each application's routes live in its own package
"""

import bluecore_airflow_common as common
from bluecore_airflow_common.integration.settings import public_config
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from bluecore_graph_toolbox import __version__, deps
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
    # The signed-in user's stable Keycloak subject. Pages use it to keep each
    # user's saved searches and settings under their own LocalStorage keys.
    user_id: str


@router.get("/api/config")
def config(settings: deps.Settings, user_uid: deps.UserUid) -> ToolboxConfig:
    # The Toolbox's version and the user's ID win even if common's
    # public_config sends keys of the same name.
    return ToolboxConfig(
        **{**public_config(settings), "version": __version__, "user_id": user_uid}
    )


router.include_router(dashboard)
router.include_router(marc_bibframe_operations)
router.include_router(sparql)
