"""Stub routes for the Toolbox Dashboard, filled in by graph-toolbox #45."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def index() -> dict[str, str | bool]:
    """Say that the application is mounted but not built yet."""
    return {
        "application": "dashboard",
        "implemented": False,
        "issue": "https://github.com/blue-core-lod/graph-toolbox/issues/45",
    }
