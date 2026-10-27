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

```sh
uv build
uv pip install dist/blue_core_graph_toolbox-*.whl
```

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