"""Policy and dependencies for the Toolbox's calls through bluecore-airflow-common.

bluecore-airflow-common supplies the settings, clients, errors and helpers;
this module holds the choices that are the Toolbox's own: its User-Agent, which
DAGs it may start, size limits, and admin roles. Routes take
clients from the dependencies here, so tests replace them with
``app.dependency_overrides``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

import jwt
from airflow.api_fastapi.core_api.security import GetUserDep
from airflow_client.client import ApiClient, DagRunApi, TaskInstanceApi
from bluecore_airflow_common.integration import airflow
from bluecore_airflow_common.integration.auth import AirflowToken
from bluecore_airflow_common.integration.settings import (
    BlueCoreSettings,
    get_settings,
)
from fastapi import Depends

from bluecore_graph_toolbox import __version__

USER_AGENT = f"bluecore-graph-toolbox/{__version__}"

# Uploads are staged under $BLUECORE_UPLOADS_DIR/<PLUGIN_SLUG>/<user>/.
PLUGIN_SLUG = "graph-toolbox"

# The only DAGs the Toolbox starts, reads or cancels. Any other dag_id in a
# job route is a 404, so the routes can't be used to reach other DAGs.
BULK_UPDATE_DAG, MARC_DAG = "bulk_update", "marc_to_bibframe"
JOB_DAGS = frozenset({BULK_UPDATE_DAG, MARC_DAG})

# Keycloak realm roles that may see and cancel other users' runs.
ADMIN_ROLES = frozenset({"bluecore_admin"})

Settings = Annotated[BlueCoreSettings, Depends(get_settings)]


def airflow_api(settings: Settings, token: AirflowToken) -> Iterator[ApiClient]:
    """An Airflow API client acting as the signed-in user, for one request."""
    with airflow.make_client(settings, token=token, user_agent=USER_AGENT) as client:
        yield client


AirflowApi = Annotated[ApiClient, Depends(airflow_api)]


def dag_runs(client: AirflowApi) -> DagRunApi:
    return DagRunApi(client)


def task_instances(client: AirflowApi) -> TaskInstanceApi:
    return TaskInstanceApi(client)


DagRuns = Annotated[DagRunApi, Depends(dag_runs)]
TaskInstances = Annotated[TaskInstanceApi, Depends(task_instances)]


def user_uid(user: GetUserDep) -> str:
    """The caller's Keycloak subject, the value DAG runs record as ``user_uid``."""
    return user.get_id()


def user_roles(user: GetUserDep) -> frozenset[str]:
    """The caller's Keycloak realm roles, or none if they have no Keycloak token.

    The signature isn't checked here: Airflow's Keycloak auth manager got this
    token from Keycloak and keeps it inside the Airflow JWT it has already
    verified, so the claims are only being read, not trusted afresh.
    """
    token = getattr(user, "access_token", None)
    if not token:
        return frozenset()
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        return frozenset()
    realm_access = claims.get("realm_access")
    if not isinstance(realm_access, dict):
        return frozenset()
    return frozenset(str(role) for role in realm_access.get("roles", []))


UserUid = Annotated[str, Depends(user_uid)]
UserRoles = Annotated[frozenset[str], Depends(user_roles)]
