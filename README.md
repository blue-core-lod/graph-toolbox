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
| `GET /graph-toolbox/api/config` | required | Browser-safe settings: `{"version", "public_url", "user_id"}` |
| `GET /graph-toolbox/dashboard` | required | Dashboard (stub, [#45](https://github.com/blue-core-lod/graph-toolbox/issues/45)) |
| `/graph-toolbox/marc-bibframe-operations/…` | required | MARC to BIBFRAME uploads and jobs, see [below](#marc-to-bibframe-jobs) |
| `GET /graph-toolbox/sparql` | required | SPARQL Query and Update (stub, [#54](https://github.com/blue-core-lod/graph-toolbox/issues/54)) |
| `GET /graph-toolbox/health` | none | `{"status", "version"}` |
| `/graph-toolbox/static/…` | none | Toolbox and shared Blue Core assets |

Each stub answers `{"application", "implemented": false, "issue"}` until its
ticket replaces it. Errors from every route use one shape,
`{"error": {"code", "message", "upstream_status", "request_id"}}`; details
are logged under the `request_id`, never returned. The exception is a request
FastAPI can't parse (a missing field, a wrong type), which gets FastAPI's
own 422 body, `{"detail": [...]}`, naming each field at fault.

The routes and their request and response shapes are in
[`docs/openapi.json`](docs/openapi.json). The plugin doesn't serve it;
regenerate it with `uv run python scripts/openapi.py` after changing a route,
and a test fails until you do.

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

## MARC to BIBFRAME jobs

The MARC to BIBFRAME page (#40) uploads a MARC file, previews it, and submits
it to the `marc_to_bibframe` DAG in
[bluecore-workflows](https://github.com/blue-core-lod/bluecore-workflows),
which does the conversion (with
[marc-bibframe](https://github.com/blue-core-lod/marc-bibframe)), duplicate
matching, saving to Blue Core, LSP export and the reports. The Toolbox checks
what it's given and passes it on. Every call to the DAG goes through the
Airflow REST API as the signed-in user. Relative to
`/graph-toolbox/marc-bibframe-operations`:

| Route | Purpose |
|---|---|
| `POST /uploads` | Multipart `file`, a `.mrc` or `.xml` file. Returns `{"upload_id", "filename", "record_count", "batch_count", "sha256", "preview_marcxml"}` |
| `GET /uploads/{upload_id}/marcxml` | The whole upload as one MARC XML collection |
| `DELETE /uploads/{upload_id}` | Drop an upload that won't be submitted |
| `POST /jobs` | Start a run on an upload. Returns `{"job_id", "state"}` |
| `GET /jobs/{job_id}` | `{"job_id", "state", "options", "queued_at", "started_at", "ended_at", "reports"}` |
| `POST /jobs/{job_id}/cancel` | Stop a queued or running run; returns the job as above |
| `GET /jobs/{job_id}/reports/{import\|duplicates}` | Download a report as CSV |

[`examples/marc-bibframe.sh`](examples/marc-bibframe.sh) runs through all of
them with curl.

**Uploads.** Binary MARC21 (`.mrc`) or MARC XML (`.xml`), up to 512 MiB.
Which one a file is comes from its content, and it has to match the suffix.
Every record is read before the upload is accepted; if one can't be, the
upload is refused with a 422 naming that record's position, and nothing is
kept. The preview is the first ten records. `batch_count` is how many runs of
at most 1,000 records the DAG will make. Uploads are kept under the user's own
directory on the uploads volume, so another user's `upload_id` is a 404. An
upload not deleted is removed a day after it was made, the next time the same
user uploads, so a job should be submitted within a day of its upload.

**Options.** `POST /jobs` takes:

```json
{
  "upload_id": "…",
  "duplicate_policy": "create_new | export_only | replace | skip_report",
  "confirmed_policy": "the same policy, as the user confirmed it",
  "duplicate_report": true,
  "export_to_lsp": false,
  "dry_run": true
}
```

Every field is required and must be the right JSON type; unknown fields are
refused. `confirmed_policy` must equal `duplicate_policy`, and `export_only`
needs `export_to_lsp`. A refused submission never reaches Airflow. Each
submission is a new run, so a dry run and then the real run can use the same
upload.

**What the DAG gets.** The run's `conf`, the contract with the DAG:

```json
{
  "user_uid": "the Keycloak subject of the user who submitted it",
  "marc_file": "/opt/airflow/uploads/graph-toolbox/<user>/<upload_id>.mrc",
  "batch_size": 1000,
  "duplicate_policy": "skip_report",
  "duplicate_report": true,
  "export_to_lsp": false,
  "dry_run": true
}
```

The DAG is expected to write `import.csv` (always) and `duplicates.csv` (when
`duplicate_report` is set) to `reports/marc_to_bibframe/<run_id>/` on the
reports volume. How long reports are kept is up to bluecore-workflows.

**Jobs.** A run is visible only to the user whose `user_uid` started it and to
users with the `bluecore_admin` realm role; to anyone else it's a 404.
Cancelling marks a queued or running run failed, which stops its remaining
tasks, and returns the state Airflow then reports. Batches that finished
before the cancel keep what they did: nothing is undone. A finished run is
returned unchanged. Cancelling before submission is just `DELETE`ing the
upload.

## Saved searches and settings
Pinned searches and saved job settings are kept only in the browser's
LocalStorage, never on the server. Every screen uses the one adapter in
`static/py/saved.py`, loaded with PyScript's `files` config and opened
with the `user_id` from `/api/config`:

```python
import saved

store = saved.open_store(config["user_id"])
store.create(saved.SEARCH, "Recent works", "sparql", {"query": "SELECT ..."})
```

- Keys are `bluecore:graph-toolbox:v<schema>:<user>:<searches|settings>`, so
  each signed-in user sees only their own entries. That's tidiness, not
  authorization: whatever a saved entry runs is still checked by the backend.
- Entries last across reloads and restarts in the same browser profile, don't
  sync between browsers, and go when site data is cleared.
- Only a query and its options, or a job's settings, are saved: never
  credentials, tokens, MARC files, reports or results. Option keys that look
  like secrets are refused, and options are limited to 16 KiB.
- Reads never fail. If storage is blocked or holds unreadable JSON, there's
  nothing saved. Saves raise `saved.StorageError`, whose message can be shown
  as is, and leave what was already saved alone. Bad input raises
  `ValueError` or `TypeError`.
- A `marc-to-bibframe` setting's options are the `POST /jobs` body without
  `upload_id` and `confirmed_policy`. Submitting them still checks them.
- Entries for operations this version doesn't know (from a newer Toolbox)
  are listed with `supported=False`: show them, allow delete, don't run them.
  Older schema versions are upgraded through `saved.MIGRATIONS` on the next
  save.

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