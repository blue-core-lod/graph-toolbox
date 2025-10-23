import json

import js
import rdflib


from jinja2 import Template
from pyodide.ffi import create_proxy
from pyodide.http import pyfetch

from sinopia_api import environments

# Define common RDF namespaces
NAMESPACES = [
    ("bf", rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")),
    ("bflc", rdflib.Namespace("http://id.loc.gov/ontologies/bflc/")),
    ("madsrdf", rdflib.Namespace("http://www.loc.gov/mads/rdf/v1#")),
    ("sin", rdflib.Namespace("http://sinopia.io/vocabulary/")),
]


def _get_app():
    """Get the app instance to access state."""
    from app import app
    return app


def skolemize_resource(resource_url: str, raw_rdf: str) -> str:
    resource_graph = rdflib.Graph()
    if not isinstance(raw_rdf, str):
        raw_rdf = json.dumps(raw_rdf)
    resource_graph.parse(data=raw_rdf, format="json-ld")
    # skolemize_graph = resource_graph.skolemize(basepath=f"{resource_url.strip()}#")
    # return skolemize_graph.serialize(format="turtle")
    return resource_graph.serialize(format="turtle")


async def build_graph(*args) -> rdflib.Graph:
    app = _get_app()
    bf_graph = app.state.get("bf_graph")

    individual_resources = js.document.getElementById("resource-urls")
    loading_spinner = js.document.getElementById("graph-loading-status")
    loading_spinner.classList.remove("d-none")
    bench_heading = js.document.getElementById("bench-heading")
    bench_bc_result = js.document.getElementById("bc-results")

    if len(individual_resources.value) > 0:
        resources = individual_resources.value.split(",")
        for resource_url in resources:
            resource_result = await pyfetch(resource_url)
            if not resource_result.ok:
                bench_heading.innerHTML = """<span class="text-danger">ERROR!</span>"""
                error = await resource_result.text()
                bench_bc_result.innerHTML = f"Message: {error}"
                break

            resource_payload = await resource_result.json()
            turtle_rdf = skolemize_resource(
                resource_url.strip(), resource_payload["data"]
            )
            bf_graph.parse(data=turtle_rdf, format="turtle")
    loading_spinner.classList.add("d-none")
    app.state["bf_graph"] = bf_graph
    summarize_graph(bf_graph)
    return bf_graph


def load_uri_into_graph(bf_graph: rdflib.Graph, uri: str, rdf_data: str) -> rdflib.Graph:
    """
    Load RDF data for a URI into the given graph.

    Args:
        bf_graph: The RDF graph to load data into
        uri: The URI of the resource
        rdf_data: The RDF data as a string (JSON-LD format)

    Returns:
        The updated graph
    """
    turtle_rdf = skolemize_resource(uri, rdf_data)
    bf_graph.parse(data=turtle_rdf, format="turtle")
    return bf_graph


async def download_graph(event):
    app = _get_app()
    bf_graph = app.state.get("bf_graph")

    anchor = event.target
    serialization = anchor.getAttribute("data-serialization")

    if not bf_graph or len(bf_graph) < 1:
        js.alert("Empty graph cannot be download")
        return
    for prefix, uri in NAMESPACES:
        bf_graph.namespace_manager.bind(prefix, uri)
    mime_type, contents = None, None
    match serialization:
        case "json-ld":
            mime_type = "application/json"
            contents = bf_graph.serialize(format="json-ld")

        case "nt":
            mime_type = "application/n-triples"
            contents = bf_graph.serialize(format="nt")

        case "ttl":
            mime_type = "application/x-turtle"
            contents = bf_graph.serialize(format="turtle")

        case "xml":
            mime_type = "application/rdf+xml"
            contents = bf_graph.serialize(format="pretty-xml")

        case _:
            js.alert(f"Unknown RDF serialization {serialization}")
            return
    blob = js.Blob.new([contents], {"type": mime_type})
    anchor = js.document.createElement("a")
    anchor.href = js.URL.createObjectURL(blob)
    anchor.download = f"bluecore-graph.{serialization}"
    js.document.body.appendChild(anchor)
    anchor.click()
    js.document.body.removeChild(anchor)


def summarize_graph(graph: rdflib.Graph):
    query_result = graph.query(
        """SELECT (count(DISTINCT ?s) as ?subjCount) (count(DISTINCT ?p) as ?predCount) (count(DISTINCT ?o) as ?objCount) 
    WHERE { ?s ?p ?o . }"""
    )
    total_triples_badge = js.document.getElementById("total-triples")
    subjects_count_badge = js.document.getElementById("subjects-count")
    predicates_count_badge = js.document.getElementById("predicates-count")
    objects_count_badge = js.document.getElementById("objects-count")
    counts = query_result.bindings[0]
    subjects_count = int(counts.get("subjCount"))
    predicates_count = int(counts.get("predCount"))
    objects_count = int(counts.get("objCount"))
    total_triples_badge.innerHTML = f"{len(graph):,}"
    subjects_count_badge.innerHTML = f"{subjects_count:,}"
    predicates_count_badge.innerHTML = f"{predicates_count:,}"
    objects_count_badge.innerHTML = f"{objects_count:,}"
    works_result = graph.query(
        """
        PREFIX bf: <http://id.loc.gov/ontologies/bibframe/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT (count(DISTINCT ?s) as ?workCount)
        WHERE { ?s rdf:type bf:Work . }
        """
    )
    works_count = works_result.bindings[0]
    works_count_badge = js.document.getElementById("bf-works-count")
    works_count_badge.innerHTML = f"{int(works_count.get('workCount')):,}"
    instances_result = graph.query(
        """
        PREFIX bf: <http://id.loc.gov/ontologies/bibframe/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT (count(DISTINCT ?s) as ?instanceCount)
        WHERE { ?s rdf:type bf:Instance . }
        """
    )
    instances_count = instances_result.bindings[0]
    instances_count_badge = js.document.getElementById("bf-instances-count")
    instances_count_badge.innerHTML = f"{int(instances_count.get('instanceCount')):,}"


sparql_template = Template(
    """{% for ns in namespaces %}PREFIX {{ ns[0] }}: <{{ ns[1] }}>\n{% endfor %}"""
)


def bibframe_sparql(element_id: str):
    wrapper_div = js.document.getElementById(element_id)
    all_namespaces = NAMESPACES + [("rdf", rdflib.RDF), ("rdfs", rdflib.RDFS)]
    wrapper_div.innerHTML = sparql_template.render(namespaces=all_namespaces)


async def load_cbd_file(event):
    app = _get_app()
    bf_graph = app.state.get("bf_graph")

    cbd_file_input = js.document.getElementById("cbd-file")
    cbd_file_modal_close_btn = js.document.getElementById("cbd-modal-close-btn")
    if cbd_file_input.files.length > 0:
        cbd_file = cbd_file_input.files.item(0)
        rdf_type = rdflib.util.guess_format(cbd_file_input.value)
        raw_rdf = await cbd_file.text()
        bf_graph.parse(data=raw_rdf, format=rdf_type)
        app.state["bf_graph"] = bf_graph
        summarize_graph(bf_graph)
        cbd_file_modal_close_btn.click()
