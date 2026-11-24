"""Read uploaded MARC files: check them, count them, and write them as MARC XML.

An upload is binary MARC21 (``.mrc``) or MARC XML (``.xml``). Which one it is
comes from its content, and the suffix has to agree. Records are read one at a
time, so a large file is never held in memory.

Conversion to BIBFRAME is the DAG's job, with marc-bibframe. This module only
gets the file into the MARC XML the DAG and the preview both start from.
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterator

import lxml.etree as ET
import pymarc
from bluecore_airflow_common.integration.errors import InvalidInput
from pymarc.marcxml import record_to_xml

MARCXML_NS = "http://www.loc.gov/MARC21/slim"
COLLECTION_OPEN = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<collection xmlns="' + MARCXML_NS.encode() + b'">\n'
)
COLLECTION_CLOSE = b"</collection>\n"
PREVIEW_RECORDS = 10

_RECORD = f"{{{MARCXML_NS}}}record"
_LEADER = f"{{{MARCXML_NS}}}leader"
_SNIFF_BYTES = 1024


class InvalidMarc(InvalidInput):
    """An upload that isn't MARC, or has a record that can't be read

    The position is the only detail returned, since it says where to look
    without echoing any of the file back.
    """

    message = "The file is not valid MARC"

    def __init__(self, detail: str, position: int | None = None) -> None:
        super().__init__(detail)
        self.position = position

    def public_message(self) -> str:
        if self.position is None:
            return self.message
        return f"{self.message}: record {self.position} could not be read"


def is_marcxml(path: pathlib.Path) -> bool:
    """Whether the file looks like XML rather than binary MARC21"""
    with path.open("rb") as handle:
        start = handle.read(_SNIFF_BYTES)
    return start.removeprefix(b"\xef\xbb\xbf").lstrip().startswith(b"<")


def records(path: pathlib.Path) -> Iterator[bytes]:
    """Each record in the file as a MARC XML ``<record>`` element

    Raises:
        InvalidMarc: if the content doesn't match the suffix, or a record
            can't be read. Records before the bad one have been yielded.
    """
    xml = is_marcxml(path)
    if xml != (path.suffix.lower() == ".xml"):
        raise InvalidMarc(f"{path.name}: content does not match its suffix")
    yield from (_xml_records(path) if xml else _binary_records(path))


def _binary_records(path: pathlib.Path) -> Iterator[bytes]:
    with path.open("rb") as handle:
        reader = pymarc.MARCReader(handle, to_unicode=True)
        for position, record in enumerate(reader, start=1):
            if record is None:
                raise InvalidMarc(
                    f"{path.name}: {reader.current_exception!r}", position
                )
            yield record_to_xml(record, namespace=False)


def _xml_records(path: pathlib.Path) -> Iterator[bytes]:
    # No entity resolution and no network, so a file can't make the parser
    # read anything but itself.
    events = ET.iterparse(
        str(path),
        events=("end",),
        tag=_RECORD,
        resolve_entities=False,
        no_network=True,
    )
    position = 0
    try:
        for _, element in events:
            position += 1
            if element.find(_LEADER) is None:
                raise InvalidMarc(f"{path.name}: record has no leader", position)
            yield ET.tostring(element, with_tail=False)
            # Drop what's been read, so memory stays flat however long the
            # file is.
            element.clear()
            while element.getprevious() is not None:
                del element.getparent()[0]
    except ET.XMLSyntaxError as exc:
        raise InvalidMarc(f"{path.name}: {exc}", position + 1) from None


def summarize(path: pathlib.Path, preview: int = PREVIEW_RECORDS) -> tuple[int, bytes]:
    """Read the whole file, and return its record count and a preview

    The preview is a MARC XML ``<collection>`` of the first ``preview`` records.

    Raises:
        InvalidMarc: as ``records()`` does, or if the file has no records.
    """
    count = 0
    first = []
    for record in records(path):
        count += 1
        if count <= preview:
            first.append(record + b"\n")
    if not count:
        raise InvalidMarc(f"{path.name}: no MARC records")
    return count, b"".join([COLLECTION_OPEN, *first, COLLECTION_CLOSE])


def marcxml(path: pathlib.Path) -> Iterator[bytes]:
    """The whole file as a MARC XML ``<collection>``, a record at a time"""
    yield COLLECTION_OPEN
    for record in records(path):
        yield record + b"\n"
    yield COLLECTION_CLOSE
