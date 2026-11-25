"""Tests for reading uploaded MARC files."""

from __future__ import annotations

import pathlib

import lxml.etree as ET
import pytest
from conftest import marcxml, mrc

from bluecore_graph_toolbox.marc_bibframe_operations import marc

NS = {"marc": marc.MARCXML_NS}


def _write(tmp_path: pathlib.Path, name: str, data: bytes) -> pathlib.Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _ids(collection: bytes) -> list[str]:
    root = ET.fromstring(collection)
    return root.xpath("marc:record/marc:controlfield[@tag='001']/text()", namespaces=NS)


@pytest.mark.parametrize(
    ("name", "data"), [("records.mrc", mrc(12)), ("records.xml", marcxml(12))]
)
def test_summarize_counts_every_record_and_previews_ten(
    tmp_path: pathlib.Path, name: str, data: bytes
) -> None:
    count, preview = marc.summarize(_write(tmp_path, name, data))

    assert count == 12
    assert _ids(preview) == [f"rec{n}" for n in range(1, 11)]


@pytest.mark.parametrize(
    ("name", "data"), [("records.mrc", mrc(3)), ("records.xml", marcxml(3))]
)
def test_marcxml_is_one_collection_of_every_record(
    tmp_path: pathlib.Path, name: str, data: bytes
) -> None:
    collection = b"".join(marc.marcxml(_write(tmp_path, name, data)))

    assert _ids(collection) == ["rec1", "rec2", "rec3"]


def test_suffix_is_case_insensitive(tmp_path: pathlib.Path) -> None:
    assert marc.summarize(_write(tmp_path, "records.XML", marcxml(1)))[0] == 1


def test_xml_with_a_byte_order_mark_is_xml(tmp_path: pathlib.Path) -> None:
    path = _write(tmp_path, "records.xml", b"\xef\xbb\xbf" + marcxml(1))

    assert marc.summarize(path)[0] == 1


@pytest.mark.parametrize(
    ("name", "data"),
    [("records.xml", mrc(1)), ("records.mrc", marcxml(1))],
    ids=["binary-named-xml", "xml-named-mrc"],
)
def test_content_must_match_the_suffix(
    tmp_path: pathlib.Path, name: str, data: bytes
) -> None:
    with pytest.raises(marc.InvalidMarc) as raised:
        marc.summarize(_write(tmp_path, name, data))

    assert raised.value.public_message() == "The file is not valid MARC"


@pytest.mark.parametrize(
    ("name", "data"), [("empty.mrc", b""), ("empty.xml", marcxml(0))]
)
def test_a_file_with_no_records_is_refused(
    tmp_path: pathlib.Path, name: str, data: bytes
) -> None:
    with pytest.raises(marc.InvalidMarc):
        marc.summarize(_write(tmp_path, name, data))


def test_a_truncated_binary_record_is_named_by_position(
    tmp_path: pathlib.Path,
) -> None:
    path = _write(tmp_path, "records.mrc", mrc(2) + mrc(1)[:20])

    with pytest.raises(marc.InvalidMarc) as raised:
        marc.summarize(path)

    assert raised.value.position == 3
    assert raised.value.public_message() == (
        "The file is not valid MARC: record 3 could not be read"
    )


def test_malformed_xml_is_named_by_position(tmp_path: pathlib.Path) -> None:
    path = _write(tmp_path, "records.xml", marcxml(2).replace(b"</collection>", b""))

    with pytest.raises(marc.InvalidMarc) as raised:
        marc.summarize(path)

    assert raised.value.position == 3


def test_an_xml_record_without_a_leader_is_refused(tmp_path: pathlib.Path) -> None:
    data = marcxml(2).replace(b"<leader>", b"<x>", 1).replace(b"</leader>", b"</x>", 1)

    with pytest.raises(marc.InvalidMarc) as raised:
        marc.summarize(_write(tmp_path, "records.xml", data))

    assert raised.value.position == 1


def test_xml_entities_are_not_resolved(tmp_path: pathlib.Path) -> None:
    secret = _write(tmp_path, "secret.txt", b"do-not-read")
    data = (
        marcxml(1)
        .replace(
            b"<collection",
            f'<!DOCTYPE collection [<!ENTITY s SYSTEM "file://{secret}">]><collection'.encode(),
        )
        .replace(b"rec1", b"&s;")
    )

    try:
        _, preview = marc.summarize(_write(tmp_path, "records.xml", data))
    except marc.InvalidMarc:
        return
    assert b"do-not-read" not in preview
