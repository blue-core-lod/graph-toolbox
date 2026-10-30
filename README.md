# Blue Core Graph Toolbox
Web Application for loading and manipulating [Blue Core](https://bcld.info) RDF. 

The Toolbox is being rebuilt as an [Airflow 3 plugin](#running-as-an-airflow-plugin)
that runs inside Blue Core Workflows. Until its screens are moved over, the
original PyScript site lives alongside it in this repo.

Through [Pyscript](https://pyscript.net/), the [rdflib](https://rdflib.readthedocs.io/en/stable/) Python package is used 
for loading RDF through Blue Core.

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
| `GET /graph-toolbox/health` | none | `{"status", "version"}` |
| `/graph-toolbox/static/…` | none | Toolbox and shared Blue Core assets |

Sign-in is Airflow's own: the page uses Airflow's JWT cookie (Keycloak in a
Blue Core stack), and the Toolbox has no login of its own.

All URLs follow [api] base_url, so the same build works with Airflow at the
root or proxied under a path such as /workflows
(AIRFLOW__API__BASE_URL=`http://localhost/workflows`), where the routes above
become `/workflows/graph-toolbox/…`.

## Development

```sh
uv sync
uv run ruff check src/bluecore_graph_toolbox tests
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