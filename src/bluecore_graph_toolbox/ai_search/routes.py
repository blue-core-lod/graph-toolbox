"""Stub routes for the Toolbox AI-Search, filled in by graph-toolbox #39."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/ai-search", tags=["search"])


@router.get("")
def index() -> dict[str, str | bool]:
    """Say that the application is mounted but not built yet."""
    return {
        "application": "ai-search",
        "implemented": False,
        "issue": "https://github.com/blue-core-lod/graph-toolbox/issues/39",
    }
