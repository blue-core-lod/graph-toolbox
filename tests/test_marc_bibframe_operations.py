"""Tests for the MARC to BIBFRAME operations routes."""

from __future__ import annotations

import pathlib
from types import ModuleType

import lxml.etree as ET
import pytest
from airflow.api_fastapi.core_api.security import get_user
from airflow_client.client.exceptions import ApiException
from conftest import SETTINGS, FakeDagRuns, StubUser, marcxml, mrc
from fastapi.testclient import TestClient

from bluecore_graph_toolbox import deps
from bluecore_graph_toolbox.marc_bibframe_operations import routes

BASE = "/marc-bibframe-operations"
# The user signed_in_client signs in as.
USER = "<b>cataloger</b>"
NS = {"marc": "http://www.loc.gov/MARC21/slim"}


def _upload(client: TestClient, data: bytes, filename: str = "records.mrc") -> dict:
    response = client.post(f"{BASE}/uploads", files={"file": (filename, data)})
    assert response.status_code == 201, response.text
    return response.json()


def _user_files(uploads_dir: pathlib.Path) -> list[str]:
    """The signed-in user's files on the uploads volume."""
    directory = routes.user_dir(USER)
    assert directory.is_relative_to(uploads_dir)
    return sorted(p.name for p in directory.iterdir()) if directory.exists() else []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/uploads"),
        ("get", f"/uploads/{'0' * 32}/marcxml"),
        ("delete", f"/uploads/{'0' * 32}"),
        ("post", "/jobs"),
    ],
)
def test_routes_require_sign_in(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, f"{BASE}{path}").status_code == 401


@pytest.mark.parametrize(
    ("filename", "data"), [("records.mrc", mrc(1001)), ("records.xml", marcxml(1001))]
)
def test_upload_reports_counts_batches_and_a_preview(
    signed_in_client: TestClient, uploads_dir: pathlib.Path, filename: str, data: bytes
) -> None:
    body = _upload(signed_in_client, data, filename)

    assert body["filename"] == filename
    assert body["record_count"] == 1001
    assert body["batch_count"] == 2
    assert len(body["sha256"]) == 64
    preview = ET.fromstring(body["preview_marcxml"].encode())
    assert len(preview.findall("marc:record", NS)) == 10
    suffix = pathlib.PurePath(filename).suffix
    assert _user_files(uploads_dir) == [f"{body['upload_id']}{suffix}"]


def test_a_thousand_records_is_one_batch(
    signed_in_client: TestClient, uploads_dir: pathlib.Path
) -> None:
    assert _upload(signed_in_client, mrc(1000))["batch_count"] == 1


def test_invalid_marc_is_refused_and_not_kept(
    signed_in_client: TestClient, uploads_dir: pathlib.Path
) -> None:
    response = signed_in_client.post(
        f"{BASE}/uploads", files={"file": ("records.mrc", mrc(1) + b"00099trunc")}
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == (
        "The file is not valid MARC: record 2 could not be read"
    )
    assert _user_files(uploads_dir) == []


@pytest.mark.parametrize("filename", ["records.csv", "records.marc", "records"])
def test_other_suffixes_are_refused(
    signed_in_client: TestClient, uploads_dir: pathlib.Path, filename: str
) -> None:
    response = signed_in_client.post(
        f"{BASE}/uploads", files={"file": (filename, mrc(1))}
    )

    assert response.status_code == 422
    assert _user_files(uploads_dir) == []


def test_uploads_over_the_limit_are_refused(
    signed_in_client: TestClient,
    uploads_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(deps, "MAX_UPLOAD_BYTES", 100)

    response = signed_in_client.post(
        f"{BASE}/uploads", files={"file": ("records.mrc", mrc(5))}
    )

    assert response.status_code == 413
    assert _user_files(uploads_dir) == []


@pytest.mark.parametrize(
    ("filename", "data"), [("records.mrc", mrc(3)), ("records.xml", marcxml(3))]
)
def test_download_is_the_whole_file_as_marcxml(
    signed_in_client: TestClient, uploads_dir: pathlib.Path, filename: str, data: bytes
) -> None:
    upload_id = _upload(signed_in_client, data, filename)["upload_id"]

    response = signed_in_client.get(f"{BASE}/uploads/{upload_id}/marcxml")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/marcxml+xml"
    assert "attachment" in response.headers["content-disposition"]
    root = ET.fromstring(response.content)
    ids = root.xpath("marc:record/marc:controlfield[@tag='001']/text()", namespaces=NS)
    assert ids == ["rec1", "rec2", "rec3"]


def test_delete_removes_the_upload(
    signed_in_client: TestClient, uploads_dir: pathlib.Path
) -> None:
    upload_id = _upload(signed_in_client, mrc(1))["upload_id"]

    assert signed_in_client.delete(f"{BASE}/uploads/{upload_id}").status_code == 204
    assert _user_files(uploads_dir) == []
    response = signed_in_client.get(f"{BASE}/uploads/{upload_id}/marcxml")
    assert response.status_code == 404


def test_another_users_upload_is_not_found(
    plugin: ModuleType, signed_in_client: TestClient, uploads_dir: pathlib.Path
) -> None:
    upload_id = _upload(signed_in_client, mrc(1))["upload_id"]
    plugin.app.dependency_overrides[get_user] = lambda: StubUser("someone-else")

    assert (
        signed_in_client.get(f"{BASE}/uploads/{upload_id}/marcxml").status_code == 404
    )
    assert signed_in_client.delete(f"{BASE}/uploads/{upload_id}").status_code == 404
    assert len(_user_files(uploads_dir)) == 1


@pytest.mark.parametrize(
    "upload_id", ["..", "%2e%2e%2fsecret", "A" * 32, "0" * 31, "0" * 32 + ".mrc"]
)
def test_upload_ids_that_could_not_be_ours_are_not_found(
    signed_in_client: TestClient, uploads_dir: pathlib.Path, upload_id: str
) -> None:
    response = signed_in_client.get(f"{BASE}/uploads/{upload_id}/marcxml")

    assert response.status_code == 404


JOB = {
    "duplicate_policy": "skip_report",
    "confirmed_policy": "skip_report",
    "duplicate_report": True,
    "export_to_lsp": False,
    "dry_run": True,
}


def test_submit_starts_a_dag_run_with_the_conf_contract(
    signed_in_client: TestClient, uploads_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    upload_id = _upload(signed_in_client, mrc(1))["upload_id"]

    response = signed_in_client.post(
        f"{BASE}/jobs", json={**JOB, "upload_id": upload_id}
    )

    assert response.status_code == 201
    [(name, (dag_id, body), kwargs)] = dag_runs.calls
    assert name == "trigger_dag_run"
    assert dag_id == "marc_to_bibframe"
    assert kwargs == {"_request_timeout": SETTINGS.request_timeout}
    assert response.json() == {"job_id": body.dag_run_id, "state": "queued"}
    assert body.dag_run_id.startswith("toolbox__")
    assert body.conf == {
        "user_uid": USER,
        "marc_file": str(routes.user_dir(USER) / f"{upload_id}.mrc"),
        "batch_size": 1000,
        "duplicate_policy": "skip_report",
        "duplicate_report": True,
        "export_to_lsp": False,
        "dry_run": True,
    }


def test_each_submission_is_a_new_run(
    signed_in_client: TestClient, uploads_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    # A dry run, then the real thing, on the same upload.
    upload_id = _upload(signed_in_client, mrc(1))["upload_id"]
    job = {**JOB, "upload_id": upload_id}

    first = signed_in_client.post(f"{BASE}/jobs", json=job).json()["job_id"]
    second = signed_in_client.post(
        f"{BASE}/jobs", json={**job, "dry_run": False}
    ).json()["job_id"]

    assert first != second


@pytest.mark.parametrize(
    "change",
    [
        {"confirmed_policy": "replace"},
        {"duplicate_policy": "export_only", "confirmed_policy": "export_only"},
        {"duplicate_policy": "merge", "confirmed_policy": "merge"},
        {"dry_run": "true"},
        {"ingest": True},
    ],
    ids=["unconfirmed", "export-only-without-lsp", "unknown-policy", "string", "extra"],
)
def test_invalid_options_never_reach_airflow(
    signed_in_client: TestClient,
    uploads_dir: pathlib.Path,
    dag_runs: FakeDagRuns,
    change: dict,
) -> None:
    upload_id = _upload(signed_in_client, mrc(1))["upload_id"]

    response = signed_in_client.post(
        f"{BASE}/jobs", json={**JOB, "upload_id": upload_id, **change}
    )

    assert response.status_code == 422
    assert dag_runs.calls == []


def test_submitting_another_users_upload_is_not_found(
    plugin: ModuleType,
    signed_in_client: TestClient,
    uploads_dir: pathlib.Path,
    dag_runs: FakeDagRuns,
) -> None:
    upload_id = _upload(signed_in_client, mrc(1))["upload_id"]
    plugin.app.dependency_overrides[get_user] = lambda: StubUser("someone-else")

    response = signed_in_client.post(
        f"{BASE}/jobs", json={**JOB, "upload_id": upload_id}
    )

    assert response.status_code == 404
    assert dag_runs.calls == []


def test_airflow_refusing_the_run_returns_the_safe_error(
    signed_in_client: TestClient, uploads_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    upload_id = _upload(signed_in_client, mrc(1))["upload_id"]
    dag_runs.error = ApiException(status=403, reason="Forbidden")

    response = signed_in_client.post(
        f"{BASE}/jobs", json={**JOB, "upload_id": upload_id}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert len(dag_runs.calls) == 1


RUN = "toolbox__20261124T120000_abc"
OPTIONS = {k: v for k, v in JOB.items() if k != "confirmed_policy"}


def _admin(plugin: ModuleType) -> None:
    plugin.app.dependency_overrides[deps.user_roles] = lambda: frozenset(
        {"bluecore_admin"}
    )


def _report(reports_dir: pathlib.Path, name: str, text: str = "status\n") -> None:
    directory = reports_dir / "marc_to_bibframe" / RUN
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/jobs"),
        ("get", f"/jobs/{RUN}"),
        ("post", f"/jobs/{RUN}/cancel"),
        ("get", f"/jobs/{RUN}/reports/import"),
    ],
)
def test_job_routes_require_sign_in(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, f"{BASE}{path}").status_code == 401


def test_jobs_list_every_users_toolbox_runs_newest_first(
    signed_in_client: TestClient, reports_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    dag_runs.add("toolbox__1", "success", user_uid=USER, **OPTIONS)
    dag_runs.add("manual__2", "success", user_uid=USER, **OPTIONS)
    dag_runs.add("toolbox__3", "running", user_uid="someone-else", **OPTIONS)

    response = signed_in_client.get(f"{BASE}/jobs")

    assert response.status_code == 200
    body = response.json()
    assert [(j["job_id"], j["user_uid"]) for j in body["jobs"]] == [
        ("toolbox__3", "someone-else"),
        ("toolbox__1", USER),
    ]
    assert body["next_cursor"] is None
    [(name, (dag_id,), kwargs)] = dag_runs.calls
    assert (name, dag_id) == ("get_dag_runs", "marc_to_bibframe")
    assert kwargs == {
        "run_id_prefix_pattern": "toolbox__",
        "order_by": ["-run_after"],
        "limit": 25,
        "cursor": "",
        "_request_timeout": SETTINGS.request_timeout,
    }


def test_jobs_list_pages_with_a_cursor(
    signed_in_client: TestClient, reports_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    for n in range(3):
        dag_runs.add(f"toolbox__{n}", user_uid=USER, **OPTIONS)

    first = signed_in_client.get(f"{BASE}/jobs", params={"limit": 2}).json()
    rest = signed_in_client.get(
        f"{BASE}/jobs", params={"limit": 2, "cursor": first["next_cursor"]}
    ).json()

    assert [j["job_id"] for j in first["jobs"]] == ["toolbox__2", "toolbox__1"]
    assert [j["job_id"] for j in rest["jobs"]] == ["toolbox__0"]
    assert rest["next_cursor"] is None


@pytest.mark.parametrize("limit", [0, 101, "many"])
def test_jobs_list_limit_is_checked(
    signed_in_client: TestClient, dag_runs: FakeDagRuns, limit: object
) -> None:
    response = signed_in_client.get(f"{BASE}/jobs", params={"limit": limit})

    assert response.status_code == 422
    assert dag_runs.calls == []


def test_jobs_list_tolerates_runs_without_toolbox_conf(
    signed_in_client: TestClient, reports_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    dag_runs.add("toolbox__1", user_uid=7, marc_file="/x.mrc")

    [listed] = signed_in_client.get(f"{BASE}/jobs").json()["jobs"]

    assert (listed["user_uid"], listed["options"]) == (None, None)


def test_job_shows_state_options_and_available_reports(
    signed_in_client: TestClient, reports_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    dag_runs.add(RUN, "success", user_uid=USER, marc_file="/x.mrc", **OPTIONS)
    _report(reports_dir, "import.csv")

    response = signed_in_client.get(f"{BASE}/jobs/{RUN}")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": RUN,
        "user_uid": USER,
        "state": "success",
        "options": OPTIONS,
        "queued_at": None,
        "started_at": None,
        "ended_at": None,
        "reports": ["import"],
    }
    [(name, (dag_id, run_id), kwargs)] = dag_runs.calls
    assert (name, dag_id, run_id) == ("get_dag_run", "marc_to_bibframe", RUN)
    assert kwargs == {"_request_timeout": SETTINGS.request_timeout}


def test_a_run_without_toolbox_options_has_none(
    signed_in_client: TestClient, reports_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    dag_runs.add(RUN, user_uid=USER, marc_file="/x.mrc", ingest=True)

    assert signed_in_client.get(f"{BASE}/jobs/{RUN}").json()["options"] is None


def test_another_users_job_is_not_found(
    signed_in_client: TestClient, reports_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    dag_runs.add(RUN, user_uid="someone-else", **OPTIONS)
    _report(reports_dir, "import.csv")

    for method, path in [
        ("get", f"/jobs/{RUN}"),
        ("post", f"/jobs/{RUN}/cancel"),
        ("get", f"/jobs/{RUN}/reports/import"),
    ]:
        assert signed_in_client.request(method, f"{BASE}{path}").status_code == 404
    assert [call[0] for call in dag_runs.calls] == ["get_dag_run"] * 3
    assert dag_runs.runs[RUN].state == "running"


def test_a_run_with_no_owner_is_not_found(
    signed_in_client: TestClient, reports_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    dag_runs.add(RUN, **OPTIONS)

    assert signed_in_client.get(f"{BASE}/jobs/{RUN}").status_code == 404


def test_admins_see_and_cancel_other_users_jobs(
    plugin: ModuleType,
    signed_in_client: TestClient,
    reports_dir: pathlib.Path,
    dag_runs: FakeDagRuns,
) -> None:
    dag_runs.add(RUN, user_uid="someone-else", **OPTIONS)
    _admin(plugin)

    assert signed_in_client.get(f"{BASE}/jobs/{RUN}").status_code == 200
    response = signed_in_client.post(f"{BASE}/jobs/{RUN}/cancel")
    assert response.json()["state"] == "failed"


def test_a_job_airflow_does_not_have_is_not_found(
    signed_in_client: TestClient, reports_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    response = signed_in_client.get(f"{BASE}/jobs/{RUN}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("state", ["queued", "running"])
def test_cancel_stops_an_unfinished_run(
    signed_in_client: TestClient,
    reports_dir: pathlib.Path,
    dag_runs: FakeDagRuns,
    state: str,
) -> None:
    dag_runs.add(RUN, state, user_uid=USER, **OPTIONS)

    response = signed_in_client.post(f"{BASE}/jobs/{RUN}/cancel")

    assert response.status_code == 200
    assert response.json()["state"] == "failed"
    [_, (name, (dag_id, run_id, body), kwargs)] = dag_runs.calls
    assert (name, dag_id, run_id) == ("patch_dag_run", "marc_to_bibframe", RUN)
    assert body.state.value == "failed"
    assert kwargs == {"_request_timeout": SETTINGS.request_timeout}


@pytest.mark.parametrize("state", ["success", "failed"])
def test_cancel_leaves_a_finished_run_as_it_is(
    signed_in_client: TestClient,
    reports_dir: pathlib.Path,
    dag_runs: FakeDagRuns,
    state: str,
) -> None:
    dag_runs.add(RUN, state, user_uid=USER, **OPTIONS)

    response = signed_in_client.post(f"{BASE}/jobs/{RUN}/cancel")

    assert response.json()["state"] == state
    assert [call[0] for call in dag_runs.calls] == ["get_dag_run"]


@pytest.mark.parametrize(
    ("name", "filename"), [("import", "import.csv"), ("duplicates", "duplicates.csv")]
)
def test_reports_download_as_csv(
    signed_in_client: TestClient,
    reports_dir: pathlib.Path,
    dag_runs: FakeDagRuns,
    name: str,
    filename: str,
) -> None:
    dag_runs.add(RUN, "success", user_uid=USER, **OPTIONS)
    _report(reports_dir, filename, "status,title\ncreated,Title 1\n")

    response = signed_in_client.get(f"{BASE}/jobs/{RUN}/reports/{name}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert f"{RUN}-{name}.csv" in response.headers["content-disposition"]
    assert response.text == "status,title\ncreated,Title 1\n"


def test_a_report_not_written_yet_is_not_found(
    signed_in_client: TestClient, reports_dir: pathlib.Path, dag_runs: FakeDagRuns
) -> None:
    dag_runs.add(RUN, user_uid=USER, **OPTIONS)

    response = signed_in_client.get(f"{BASE}/jobs/{RUN}/reports/import")

    assert response.status_code == 404


@pytest.mark.parametrize("name", ["report.json", "index.html", "import.csv"])
def test_only_named_reports_can_be_downloaded(
    signed_in_client: TestClient,
    reports_dir: pathlib.Path,
    dag_runs: FakeDagRuns,
    name: str,
) -> None:
    dag_runs.add(RUN, user_uid=USER, **OPTIONS)
    _report(reports_dir, "report.json", "{}")

    response = signed_in_client.get(f"{BASE}/jobs/{RUN}/reports/{name}")

    assert response.status_code in (404, 422)
    assert response.text != "{}"


@pytest.mark.parametrize("job_id", ["..", "%2e%2e", "..%2f..%2fetc"])
def test_job_ids_that_could_escape_are_not_found(
    signed_in_client: TestClient,
    reports_dir: pathlib.Path,
    dag_runs: FakeDagRuns,
    job_id: str,
) -> None:
    response = signed_in_client.get(f"{BASE}/jobs/{job_id}/reports/import")

    assert response.status_code == 404
