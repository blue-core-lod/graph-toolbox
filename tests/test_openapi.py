"""Tests that docs/openapi.json still describes the API.

The comparison is of routes, methods, parameters and model fields rather than
the whole text, since the exact JSON varies with the FastAPI and pydantic
versions each Airflow release brings.
"""

from __future__ import annotations

import json
import pathlib
from types import ModuleType

DOCUMENT = pathlib.Path(__file__).parent.parent / "docs" / "openapi.json"
REGENERATE = "docs/openapi.json is stale: run uv run python scripts/openapi.py"


def _outline(document: dict) -> dict:
    operations = {
        (path, method): sorted(
            (param["in"], param["name"]) for param in operation.get("parameters", [])
        )
        for path, item in document["paths"].items()
        for method, operation in item.items()
    }
    statuses = {
        (path, method): sorted(operation["responses"])
        for path, item in document["paths"].items()
        for method, operation in item.items()
    }
    schemas = {
        name: sorted(schema.get("properties", {}))
        for name, schema in document["components"]["schemas"].items()
    }
    return {"operations": operations, "statuses": statuses, "schemas": schemas}


def test_the_openapi_document_matches_the_app(plugin: ModuleType) -> None:
    published = json.loads(DOCUMENT.read_text())

    assert _outline(published) == _outline(plugin.app.openapi()), REGENERATE


def test_the_openapi_document_has_the_marc_routes() -> None:
    paths = json.loads(DOCUMENT.read_text())["paths"]

    assert {path for path in paths if path.startswith("/marc-bibframe-operations")} == {
        "/marc-bibframe-operations/uploads",
        "/marc-bibframe-operations/uploads/{upload_id}",
        "/marc-bibframe-operations/uploads/{upload_id}/marcxml",
        "/marc-bibframe-operations/jobs",
        "/marc-bibframe-operations/jobs/{job_id}",
        "/marc-bibframe-operations/jobs/{job_id}/cancel",
        "/marc-bibframe-operations/jobs/{job_id}/reports/{name}",
    }
