import json

import js
import rdflib

from jinja2 import Template
from pyodide.ffi import create_proxy
from pyodide.http import pyfetch

from state import NAMESPACES, BF_GRAPH
from sinopia_api import environments


def skolemize_resource(resource_url: str, raw_rdf: str) -> str:
    resource_graph = rdflib.Graph()
    resource_graph.parse(data=json.dumps(raw_rdf), format="json-ld")
    skolemize_graph = resource_graph.skolemize(basepath=f"{resource_url.strip()}#")
    return skolemize_graph.serialize(format="turtle")


async def build_graph(*args) -> rdflib.Graph:
    global BF_GRAPH

    individual_resources = js.document.getElementById("resource-urls")
    loading_spinner = js.document.getElementById("graph-loading-status")
    loading_spinner.classList.remove("d-none")

    if len(individual_resources.value) > 0:
        resources = individual_resources.value.split(",")
        for resource_url in resources:
            resource_result = await pyfetch(resource_url)
            resource_payload = await resource_result.json()
            turtle_rdf = skolemize_resource(
                resource_url.strip(), resource_payload["data"]
            )
            BF_GRAPH.parse(data=turtle_rdf, format="turtle")
    loading_spinner.classList.add("d-none")
    summarize_graph(BF_GRAPH)
    return BF_GRAPH


async def download_graph(event):
    anchor = event.target
    serialization = anchor.getAttribute("data-serialization")

    if len(BF_GRAPH) < 1:
        js.alert("Empty graph cannot be download")
        return
    for prefix, uri in NAMESPACES:
        BF_GRAPH.namespace_manager.bind(prefix, uri)
    mime_type, contents = None, None
    match serialization:
        case "json-ld":
            mime_type = "application/json"
            contents = BF_GRAPH.serialize(format="json-ld")

        case "nt":
            mime_type = "application/n-triples"
            contents = BF_GRAPH.serialize(format="nt")

        case "ttl":
            mime_type = "application/x-turtle"
            contents = BF_GRAPH.serialize(format="turtle")

        case "xml":
            mime_type = "application/rdf+xml"
            contents = BF_GRAPH.serialize(format="pretty-xml")

        case _:
            js.alert(f"Unknown RDF serialization {serialization}")
            return
    blob = js.Blob.new([contents], {"type": mime_type})
    anchor = js.document.createElement("a")
    anchor.href = js.URL.createObjectURL(blob)
    anchor.download = f"sinopia-graph.{serialization}"
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
    counts=query_result.bindings[0]
    subjects_count = int(counts.get('subjCount'))
    predicates_count = int(counts.get('predCount'))
    objects_count = int(counts.get('objCount'))
    total_triples_badge.innerHTML = f"{len(graph):,}"
    subjects_count_badge.innerHTML = f"{subjects_count:,}"
    predicates_count_badge.innerHTML = f"{predicates_count :,}"
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
    """<div class="mb-3">
    <label for="bf-sparql-queries" class="form-label">SPARQL Query</label>
    <textarea class="form-control" id="bf-sparql-queries" rows="10">
{% for ns in namespaces %}PREFIX {{ ns[0] }}: <{{ ns[1] }}>\n{% endfor %}
    </textarea>
  </div>
  <div class="mb-3">
    <button class="btn btn-primary" py-click="run_query" id="run-query-btn">Run query</button>
  </div>
</div>"""
)


def bibframe_sparql(element_id: str):
    wrapper_div = js.document.getElementById(element_id)
    all_namespaces = NAMESPACES + [("rdf", rdflib.RDF), ("rdfs", rdflib.RDFS)]
    wrapper_div.innerHTML = sparql_template.render(namespaces=all_namespaces)


async def load_cbd_file(event):
    global BF_GRAPH

    cbd_file_input = js.document.getElementById("cbd-file")
    if cbd_file_input.files.length > 0:
        cbd_file = cbd_file_input.files.item(0)
        rdf_type = rdflib.util.guess_format(cbd_file_input.value)
        raw_rdf = await cbd_file.text()
        BF_GRAPH.parse(data=raw_rdf, format=rdf_type)
        _summarize_graph(BF_GRAPH)
