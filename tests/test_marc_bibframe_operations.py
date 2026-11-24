"""Tests for the MARC to BIBFRAME operations routes."""

from __future__ import annotations

import os
import pathlib
import time
from types import ModuleType

import lxml.etree as ET
import pytest
from airflow.api_fastapi.core_api.security import get_user
from conftest import StubUser, marcxml, mrc
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


def test_expired_uploads_go_when_the_user_next_uploads(
    signed_in_client: TestClient, uploads_dir: pathlib.Path
) -> None:
    old = _upload(signed_in_client, mrc(1))["upload_id"]
    recent = _upload(signed_in_client, mrc(1))["upload_id"]
    directory = routes.user_dir(USER)
    a_day_ago = time.time() - deps.UPLOAD_TTL.total_seconds() - 60
    os.utime(directory / f"{old}.mrc", (a_day_ago, a_day_ago))

    newest = _upload(signed_in_client, mrc(1))["upload_id"]

    assert _user_files(uploads_dir) == sorted([f"{recent}.mrc", f"{newest}.mrc"])


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
