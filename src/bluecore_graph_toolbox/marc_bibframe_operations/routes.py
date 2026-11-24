"""Routes for MARC to BIBFRAME bulk operations (graph-toolbox #46).

Relative to ``/marc-bibframe-operations``:

- ``POST /uploads``: store and check a MARC file, and preview its first records
- ``GET /uploads/{upload_id}/marcxml``: the whole upload as MARC XML
- ``DELETE /uploads/{upload_id}``: remove an upload that won't be submitted

Uploads are kept on the shared uploads volume under the signed-in user's own
directory, so one user's upload IDs mean nothing to another.
"""

from __future__ import annotations

import math
import pathlib
import re
import time

from bluecore_airflow_common.integration import uploads
from bluecore_airflow_common.integration.errors import NotFound
from bluecore_airflow_common.integration.reports import safe_parts
from fastapi import APIRouter, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from bluecore_graph_toolbox import deps
from bluecore_graph_toolbox.marc_bibframe_operations import marc

router = APIRouter(
    prefix="/marc-bibframe-operations", tags=["marc", "marc-to-bibframe"]
)

# The random name stage_upload gives a file, without its suffix.
UPLOAD_ID = re.compile(r"[0-9a-f]{32}")


class Upload(BaseModel):
    """A stored upload: what was read from it, and its first records."""

    upload_id: str
    filename: str
    record_count: int
    # How many DAG batches the records make, at most BATCH_SIZE each.
    batch_count: int
    sha256: str
    # A MARC XML <collection> of the first PREVIEW_RECORDS records.
    preview_marcxml: str


def user_dir(user_uid: str) -> pathlib.Path:
    """Where stage_upload keeps this user's uploads."""
    return uploads.uploads_dir().joinpath(*safe_parts(deps.PLUGIN_SLUG, user_uid))


def find_upload(user_uid: str, upload_id: str) -> pathlib.Path:
    """The caller's upload with this ID.

    Raises:
        NotFound: if the caller has no such upload, whoever else might.
    """
    if UPLOAD_ID.fullmatch(upload_id):
        for suffix in sorted(deps.MARC_SUFFIXES):
            path = user_dir(user_uid) / f"{upload_id}{suffix}"
            if path.is_file():
                return path
    raise NotFound(f"no upload {upload_id!r} for this user")


def remove_expired(directory: pathlib.Path, now: float | None = None) -> None:
    """Delete files in the directory older than UPLOAD_TTL."""
    cutoff = (now or time.time()) - deps.UPLOAD_TTL.total_seconds()
    if not directory.is_dir():
        return
    for path in directory.iterdir():
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)


@router.post("/uploads", status_code=201)
def create_upload(file: UploadFile, user_uid: deps.UserUid) -> Upload:
    """Store a MARC file for a later job, after checking every record reads."""
    remove_expired(user_dir(user_uid))
    filename = file.filename or ""
    path, sha256 = uploads.stage_upload(
        file.file,
        filename,
        plugin=deps.PLUGIN_SLUG,
        user=user_uid,
        suffixes=deps.MARC_SUFFIXES,
        max_bytes=deps.MAX_UPLOAD_BYTES,
    )
    try:
        count, preview = marc.summarize(path)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return Upload(
        upload_id=path.stem,
        filename=filename,
        record_count=count,
        batch_count=math.ceil(count / deps.BATCH_SIZE),
        sha256=sha256,
        preview_marcxml=preview.decode(),
    )


@router.get(
    "/uploads/{upload_id}/marcxml",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/marcxml+xml": {}}}},
)
def download_marcxml(upload_id: str, user_uid: deps.UserUid) -> StreamingResponse:
    """The whole upload as one MARC XML collection."""
    path = find_upload(user_uid, upload_id)
    return StreamingResponse(
        marc.marcxml(path),
        media_type="application/marcxml+xml",
        headers={"Content-Disposition": f'attachment; filename="{upload_id}.xml"'},
    )


@router.delete("/uploads/{upload_id}", status_code=204)
def delete_upload(upload_id: str, user_uid: deps.UserUid) -> Response:
    """Remove an upload, for a job the user decided not to submit."""
    find_upload(user_uid, upload_id).unlink(missing_ok=True)
    return Response(status_code=204)
