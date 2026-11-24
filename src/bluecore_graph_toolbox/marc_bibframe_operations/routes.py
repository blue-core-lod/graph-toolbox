"""Routes for MARC to BIBFRAME bulk operations (graph-toolbox #46).

Relative to ``/marc-bibframe-operations``:

- ``POST /uploads``: store and check a MARC file, and preview its first records
- ``GET /uploads/{upload_id}/marcxml``: the whole upload as MARC XML
- ``DELETE /uploads/{upload_id}``: remove an upload that won't be submitted
- ``POST /jobs``: start a ``marc_to_bibframe`` DAG run on an upload
- ``GET /jobs/{job_id}``: a run's state, options and which reports it has
- ``POST /jobs/{job_id}/cancel``: stop a run that hasn't finished
- ``GET /jobs/{job_id}/reports/{import|duplicates}``: download a report

Uploads are kept on the shared uploads volume under the signed-in user's own
directory, so one user's upload IDs mean nothing to another. Jobs are DAG runs,
started and read only through the Airflow REST API as the signed-in user. A
run is only visible to the user who started it and to admins; to anyone else
it doesn't exist.
"""

from __future__ import annotations

import math
import pathlib
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from airflow_client.client import (
    DagRunApi,
    DagRunMutableStates,
    DAGRunPatchBody,
    DAGRunResponse,
    DagRunState,
    TriggerDAGRunPostBody,
)
from bluecore_airflow_common.integration import reports, uploads
from bluecore_airflow_common.integration.errors import NotFound
from bluecore_airflow_common.integration.reports import safe_parts
from bluecore_airflow_common.integration.settings import BlueCoreSettings
from fastapi import APIRouter, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from bluecore_graph_toolbox import deps
from bluecore_graph_toolbox.marc_bibframe_operations import marc
from bluecore_graph_toolbox.marc_bibframe_operations.options import (
    MarcJobRequest,
    MarcJobSettings,
)


class ErrorDetail(BaseModel):
    code: str
    message: str
    upstream_status: int | None
    request_id: str


class Error(BaseModel):
    """The body install_error_handler returns for every refused request.

    Declared here only so the OpenAPI document shows it.
    """

    error: ErrorDetail


router = APIRouter(
    prefix="/marc-bibframe-operations",
    tags=["marc", "marc-to-bibframe"],
    responses={status: {"model": Error} for status in (401, 403, 404, 413, 502, 504)},
)

# The random name stage_upload gives a file, without its suffix.
UPLOAD_ID = re.compile(r"[0-9a-f]{32}")

# The files the DAG writes to reports/marc_to_bibframe/<run_id>/. The import
# report is always written; the duplicate report only when asked for.
ReportName = Literal["import", "duplicates"]
REPORT_FILES: dict[str, str] = {"import": "import.csv", "duplicates": "duplicates.csv"}

# States a run can still be stopped in. A finished run is never marked failed,
# so cancelling can't relabel work that's already done.
UNFINISHED = frozenset({DagRunState.QUEUED, DagRunState.RUNNING})


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


class JobSubmitted(BaseModel):
    """A DAG run that has been started, and the state Airflow gave it."""

    job_id: str
    state: str


class Job(BaseModel):
    """A run as the UI shows it."""

    job_id: str
    state: str
    # The options the run was started with, or none for a run the Toolbox
    # didn't start.
    options: MarcJobSettings | None
    queued_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    # The reports that can be downloaded now, from /jobs/{job_id}/reports/{name}.
    reports: list[ReportName]


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


def job_conf(
    user_uid: str, marc_file: pathlib.Path, job: MarcJobRequest
) -> dict[str, Any]:
    """The ``conf`` a ``marc_to_bibframe`` run is started with.

    This is the contract with the DAG in bluecore-workflows. ``user_uid`` is
    also what the job routes check ownership against.
    """
    return {
        "user_uid": user_uid,
        "marc_file": str(marc_file),
        "batch_size": deps.BATCH_SIZE,
        **job.settings().model_dump(),
    }


def new_job_id() -> str:
    """A run ID that sorts by time and can't collide with another submission."""
    return f"toolbox__{datetime.now(UTC):%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:12]}"


@router.post("/jobs", status_code=201)
def submit_job(
    job: MarcJobRequest,
    user_uid: deps.UserUid,
    dag_runs: deps.DagRuns,
    settings: deps.Settings,
) -> JobSubmitted:
    """Start converting one of the caller's uploads.

    Submitting isn't retried: a failure is returned, and the user decides
    whether to submit again.
    """
    path = find_upload(user_uid, job.upload_id)
    run = dag_runs.trigger_dag_run(
        deps.MARC_DAG,
        TriggerDAGRunPostBody(
            dag_run_id=new_job_id(), conf=job_conf(user_uid, path, job)
        ),
        _request_timeout=settings.request_timeout,
    )
    return JobSubmitted(job_id=run.dag_run_id, state=str(run.state.value))


def owned_run(
    job_id: str,
    user_uid: str,
    roles: frozenset[str],
    dag_runs: DagRunApi,
    settings: BlueCoreSettings,
) -> DAGRunResponse:
    """The run, if the caller started it or is an admin.

    Raises:
        NotFound: if there's no such run, or it isn't the caller's to see.
    """
    run = dag_runs.get_dag_run(
        deps.MARC_DAG, job_id, _request_timeout=settings.request_timeout
    )
    if not reports.owner_matches(
        run.conf, user_uid, roles=roles, admin_roles=deps.ADMIN_ROLES
    ):
        raise NotFound(f"run {job_id!r} is not this user's")
    return run


def job(run: DAGRunResponse) -> Job:
    """What the UI is told about a run."""
    conf = run.conf or {}
    try:
        options = MarcJobSettings.model_validate(
            {name: conf.get(name) for name in MarcJobSettings.model_fields}
        )
    except ValueError:
        options = None
    directory = reports.run_dir(deps.MARC_DAG, run.dag_run_id)
    return Job(
        job_id=run.dag_run_id,
        state=str(run.state.value),
        options=options,
        queued_at=run.queued_at,
        started_at=run.start_date,
        ended_at=run.end_date,
        reports=[
            name
            for name, filename in REPORT_FILES.items()
            if (directory / filename).is_file()
        ],
    )


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    user_uid: deps.UserUid,
    roles: deps.UserRoles,
    dag_runs: deps.DagRuns,
    settings: deps.Settings,
) -> Job:
    """A run's state and the reports it has written so far."""
    return job(owned_run(job_id, user_uid, roles, dag_runs, settings))


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    user_uid: deps.UserUid,
    roles: deps.UserRoles,
    dag_runs: deps.DagRuns,
    settings: deps.Settings,
) -> Job:
    """Stop a queued or running run, and return the state it's left in.

    Airflow stops the run's remaining tasks. Batches that have already finished
    keep what they did: cancelling doesn't undo them. A run that has already
    finished is returned as it is.
    """
    run = owned_run(job_id, user_uid, roles, dag_runs, settings)
    if run.state in UNFINISHED:
        run = dag_runs.patch_dag_run(
            deps.MARC_DAG,
            job_id,
            DAGRunPatchBody(state=DagRunMutableStates.FAILED),
            _request_timeout=settings.request_timeout,
        )
    return job(run)


@router.get(
    "/jobs/{job_id}/reports/{name}",
    response_class=FileResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
def download_report(
    job_id: str,
    name: ReportName,
    user_uid: deps.UserUid,
    roles: deps.UserRoles,
    dag_runs: deps.DagRuns,
    settings: deps.Settings,
) -> FileResponse:
    """One of a run's reports, once the DAG has written it."""
    run = owned_run(job_id, user_uid, roles, dag_runs, settings)
    path = reports.run_dir(deps.MARC_DAG, run.dag_run_id) / REPORT_FILES[name]
    if not path.is_file():
        raise NotFound(f"run {job_id!r} has no {name} report yet")
    return FileResponse(
        path,
        media_type="text/csv",
        filename=f"{reports.slug(run.dag_run_id)}-{name}.csv",
    )
