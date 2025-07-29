import io
import pymarc
import rdflib

from js import alert, Blob, console, document, Uint8Array, URL
from lxml import etree
from pyscript import fetch

from helpers import BF
from load_rdf import summarize_graph
from state import BF_GRAPH


async def _bf_graph_to_xml(bf_graph: rdflib.Graph):
    instances = [instance for instance in bf_graph.subjects(predicate=rdflib.RDF.type, object=BF.Instance)]
    if len(instances) < 1:
        alert(f"ERROR! Need at least 1 BIBFRAME Instance")
    #bf_graph = bf_graph.de_skolemize(uriref=instances[0])
    raw_xml = bf_graph.serialize(format="pretty-xml")
    return etree.XML(bytes(raw_xml, encoding="utf-8"))


async def bf2marc(event):
    global BF_GRAPH
    anchor = event.target
    marc_format = anchor.getAttribute("data-marc-format")

    if len(BF_GRAPH) < 1:
        alert(f"ERROR! Cannot export empty graph to {marc_format[0:4].upper()} {marc_format[4:]}")
        return

    xslt_root = etree.parse("./bibframe2marc.xsl")
    bf2marc_xslt = etree.XSLT(xslt_root)
    bf_xml = await _bf_graph_to_xml(BF_GRAPH)
    marc_xml = bf2marc_xslt(bf_xml)

    match marc_format:

        case "marc21":
            marc_io = io.StringIO()
            marc_io.write(str(marc_xml))
            
            # console.log(f"Marc bytes", marc_bytes.read())
            # raw_xml = str(marc_xml)
            # console.log(raw_xml)
            marc_record = pymarc.marcxml.parse_xml_to_array(marc_io)[0]
            mime_type = "application/octet-stream"
            serialization = "mrc"

        case "marcXML":
            marc_record = marc_xml
            mime_type = "application/rdf+xml"
            serialization = "xml"

        case _:
            alert(f"ERROR! Unknown MARC Format {marc_format}")
            return

    blob = Blob.new([marc_record], {"type": mime_type})
    anchor = document.createElement("a")
    anchor.href = URL.createObjectURL(blob)
    anchor.download = f"bf-marc.{serialization}"
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)


async def marc2bf(event):
    global BF_GRAPH
    marc_upload_file = document.querySelector("#marc-file")
    if marc_upload_file.files.length < 1:
        alert("ERROR! Missing MARC21 or MARC XML file.") 
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
            marc_bytes = io.BytesIO()
            writer = pymarc.XMLWriter(marc_bytes)
            writer.write(marc_record)
            writer.close(close_fh=False)
            marc_xml = marc_bytes.getvalue()

        case "xml":
            marc_xml = await raw_marc_file.text()

        case _:
            alert(f"ERROR! Unknown file type {raw_marc_file.name}, should be mrc, marc, or xml")
            return

    xslt_root = etree.parse("./marc2bf/marc2bibframe2.xsl")
    marc2bf_xslt = etree.XSLT(xslt_root)
    marc_doc = etree.XML(marc_xml)
    try:
        bf_xml = marc2bf_xslt(marc_doc)
        BF_GRAPH.parse(data=str(bf_xml), format='xml')
        summarize_graph(BF_GRAPH)
    except Exception as e:
        alert(f"ERROR! Failed to convert MARC to BIBFRAME\n{e}")
