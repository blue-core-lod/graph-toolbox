# Blue Core Graph Toolbox
Web Application for loading and manipulating [Blue Core](https://bcld.info) RDF. 

The Toolbox is being rebuilt as an [Airflow 3 plugin](#running-as-an-airflow-plugin)
that runs inside Blue Core Workflows. The original standalone PyScript site has
been removed; its screens are being rebuilt as Toolbox applications.

SPARQL queries and graph analysis will run in the browser, using
[PyScript](https://pyscript.net/) and [rdflib](https://rdflib.readthedocs.io/en/stable/),
over RDF loaded from Blue Core. The plugin has no backend SPARQL endpoint.

## Existing and Planned Functionality
- Run SPARQL queries on one or more Blue Core Resources
- Download RDF in various serializations like Turtle, XML/RDF, and json-ld
- Chat with Blue Core AI Agents
- Import and convert MARC to Blue Core BIBFRAME Resources
- Export Blue Core Constrained Bound Descriptions (CBD) to 
  MARC21 records

## Running as an Airflow plugin

The `bluecore_graph_toolbox` package registers itself with Airflow through the
`airflow.plugins` entry point, so installing it into the Airflow environment is
all that's needed; nothing goes in the plugins folder. Shared helpers, the base
template and styles come from
[bluecore-airflow-common](https://github.com/blue-core-lod/bluecore-airflow-common).

Requires Python 3.12 and Airflow 3.2 or later (tested against 3.3.2).

Releases are published to PyPI as
[bluecore-graph-toolbox](https://pypi.org/p/bluecore-graph-toolbox)

```sh
uv build
uv add bluecore-graph-toolbox
```

In [bluecore-workflows](https://github.com/blue-core-lod/bluecore-workflows),
add the pin to `dependencies` in its `pyproject.toml` and run `uv lock`; the
Docker image installs it from the lockfile, so no wheel is copied in. When a
new Toolbox release adds screens or API routes, bump that pin and `uv lock`
again in a Workflows pull request.

Once installed, a Toolbox item appears in the Airflow navigation. The UI
shows it in an iframe at `/plugin/graph-toolbox`; the app itself is mounted at
`/graph-toolbox`:

| Route | Sign-in | Purpose |
|---|---|---|
| `GET /graph-toolbox/` | required | Landing page |
| `GET /graph-toolbox/api/config` | required | Browser-safe settings: `{"version", "public_url"}` |
| `GET /graph-toolbox/dashboard` | required | Dashboard (stub, [#45](https://github.com/blue-core-lod/graph-toolbox/issues/45)) |
| `GET /graph-toolbox/marc-bibframe-operations` | required | MARC and BIBFRAME operations (stub, [#46](https://github.com/blue-core-lod/graph-toolbox/issues/46)) |
| `GET /graph-toolbox/sparql` | required | SPARQL Query and Update (stub, [#54](https://github.com/blue-core-lod/graph-toolbox/issues/54)) |
| `GET /graph-toolbox/ai-search` | required | AI-Assisted Search (stub, [#39](https://github.com/blue-core-lod/graph-toolbox/issues/39)) |
| `GET /graph-toolbox/health` | none | `{"status", "version"}` |
| `/graph-toolbox/static/…` | none | Toolbox and shared Blue Core assets |

Each stub answers `{"application", "implemented": false, "issue"}` until its
ticket replaces it. Errors from every route use one shape,
`{"error": {"code", "message", "upstream_status", "request_id"}}`; details
are logged under the `request_id`, never returned.

Sign-in is Airflow's own: the page uses Airflow's JWT cookie (Keycloak in a
Blue Core stack), and the Toolbox has no login of its own.

All URLs follow [api] base_url, so the same build works with Airflow at the
root or proxied under a path such as /workflows
(AIRFLOW__API__BASE_URL=`http://localhost/workflows`), where the routes above
become `/workflows/graph-toolbox/…`.

## Configuration

The Toolbox adds no settings of its own. It reads the Blue Core integration
settings from
[bluecore-airflow-common](https://github.com/blue-core-lod/bluecore-airflow-common#integration),
from the same environment variables the rest of the bluecore-stack passes to
every Airflow container:

| Variable | Required | Meaning |
|---|---|---|
| `BLUECORE_API_INTERNAL_URL` | yes | Blue Core API root as the Airflow containers reach it, e.g. `http://bc_api:8100`. Never sent to browsers. |
| `BLUECORE_URL` | yes | Blue Core site root as browsers reach it, e.g. `https://bcld.info`. Returned by `/api/config` as `public_url`. |
| `AIRFLOW_API_INTERNAL_URL` | yes | Airflow root as the plugin reaches it, e.g. `http://airflow-apiserver:8080/workflows`. Never sent to browsers. |
| `BLUECORE_REQUEST_TIMEOUT` | no | Seconds allowed for each upstream request. Default 10. |
| `BLUECORE_MAX_RETRIES` | no | Retries for GET and HEAD requests only. Default 2, at most 5. |

There is one environment per deployment: no route accepts an environment or
API URL, and the UI has no environment selector. Missing or invalid settings
are logged when the plugin loads, and only the routes that need them fail.

Calls to Blue Core and Airflow are made as the signed-in user, with their own
Keycloak and Airflow tokens, never a shared service account. Leave
`API_KEYCLOAK_USER` and `API_KEYCLOAK_PASSWORD` unset in the Airflow
containers. Tokens are redacted from the logs.

The service contracts the Toolbox applications build on are in
bluecore-airflow-common's
[integration contracts](https://github.com/blue-core-lod/bluecore-airflow-common/blob/main/docs/integration-contracts.md).

## Development

```sh
uv sync
uv run ruff check
uv run ruff format --check
uv run pytest
```

## Releasing

Releases go to PyPI from
[`.github/workflows/python-publish.yml`](.github/workflows/python-publish.yml)
using [trusted publishing](https://docs.pypi.org/trusted-publishers/), so no
API token is stored in the repo.

1. Bump `version` in `pyproject.toml` (`uv version --bump minor`, say) and
   merge it to `main`.
2. Create a GitHub release whose tag is `v` plus that version, e.g. `v2.1.0`.
3. Publishing the release runs the workflow: it checks the tag against
   `pyproject.toml`, runs the tests, builds the wheel and sdist, checks that the
   wheel installs as an Airflow plugin, and uploads both to PyPI. Approve the
   `pypi` environment deployment if it asks.
4. Bump the pin in bluecore-workflows as described above.