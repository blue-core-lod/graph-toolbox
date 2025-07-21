import io
import pymarc

from js import console, document, Uint8Array
from lxml import etree
from pyscript import fetch

from state import BF_GRAPH

async def bf2marc(event):
    pass

async def marc2bf(event):
    marc_upload_file = document.querySelector("#marc-file")
    error_msg = document.querySelector("#marc-error")
    if marc_upload_file.files.length < 1:
        error_msg.classList.remove("d-none")
        error_msg.innerHTML = "Missing MARC21 or MARC XML file." + error_msg.innerHTML 
        return
    raw_marc_file = marc_upload_file.files.item(0)
    ext = raw_marc_file.name.split(".")[-1]
    match ext:
        case "mrc" | "marc":
            # Need to convert to XML
            array_buffer = await raw_marc_file.arrayBuffer()
            raw_marc = bytes(Uint8Array.new(array_buffer))
            marc_reader = pymarc.MARCReader(raw_marc)
            marc_record = next(marc_reader)
            marc_xml = io.BytesIO()
            writer = pymarc.XMLWriter(marc_xml)
            writer.write(marc_record)
            writer.close(close_fh=False)

        case "xml":
            marc_xml = await raw_marc_file.text()

    marc2bf_xslt_request = await fetch("static/xslt/marc2bibframe2.xsl")
    marc2bf_xslt_file = await marc2bf_xslt_request.text()
    xslt_root = etree.XML(marc2bf_xslt_file)
    marc2bf_xslt = etree.XSLT(xslt_root)
    marc_doc = etree.parse(marc_xml)
    bf_xml = marc2bf_xslt(marc_doc)
    BF_GRAPH.parse(data=bf_xml, format='rdf')