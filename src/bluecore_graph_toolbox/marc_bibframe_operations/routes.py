"""Stub routes for the Toolbox MARC-to-BIBFRAME, filled in by graph-toolbox #46."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(
    prefix="/marc-bibframe-operations", tags=["marc", "marc-to-bibframe"]
)


@router.get("")
def index() -> dict[str, str | bool]:
    """Say that the application is mounted but not built yet."""
    return {
        "application": "marc-bibframe-operations",
        "implemented": False,
        "issue": "https://github.com/blue-core-lod/graph-toolbox/issues/46",
    }
