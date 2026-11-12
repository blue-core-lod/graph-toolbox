"""Stub routes for the Toolbox SPARQL Query and Update, filled in by graph-toolbox #54."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/sparql", tags=["sparql"])


@router.get("")
def index() -> dict[str, str | bool]:
    """Say that the application is mounted but not built yet."""
    return {
        "application": "sparql",
        "implemented": False,
        "issue": "https://github.com/blue-core-lod/graph-toolbox/issues/54",
    }
