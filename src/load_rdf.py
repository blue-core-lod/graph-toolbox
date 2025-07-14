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


async def _get_all_graph(api_url: str, limit: int = 250) -> None:
    next_url = f"{api_url}resource?limit={limit}"
    loading_resources = True
    while loading_resources:
        result = await pyfetch(next_url)
        payload = await result.json()
        for i, row in enumerate(payload["data"]):
            if not "data" in row:
                js.console.log(f"No data for {i}")
                continue
            if not "uri" in row:
                js.console.log("No URI for resource {i}")
                continue
            try:
                turtle_rdf = skolemize_resource(row["uri"], row["data"])
                BF_GRAPH.parse(data=turtle_rdf, format="turtle")
            except Exception as e:
                js.console.log(f"Failed to parse {row['uri']} {e}")
        next_url = payload["links"].get("next")
        if next_url is None:
            loading_resources = False
    return BF_GRAPH


async def _get_group_graph(group: str, api_url: str, limit: int = 2_500) -> None:
    start = 0
    if not api_url.endswith("/"):
        api_url = f"{api_url}/"
    initial_url = f"{api_url}resource?limit={limit}&group={group}&start={start}"
    initial_result = await pyfetch(initial_url)
    group_payload = await initial_result.json()
    for i, row in enumerate(group_payload["data"]):
        if not "data" in row:
            js.console.log(f"No RDF found for {row.get('uri', 'bad url')}")
            continue
        if not "uri" in row:
            js.console.log(f"No URI for {i}")
            continue
        try:
            turtle_rdf = skolemize_resource(row["uri"], row["data"])
            BF_GRAPH.parse(data=turtle_rdf, format="turtle")
        except Exception as e:
            js.console.log(f"Cannot load {row['uri']} Error:\n{e}")
            continue
    return BF_GRAPH


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
    _summarize_graph(BF_GRAPH)
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


def _summarize_graph(graph: rdflib.Graph):
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
    


bf_template = Template(
    """<div class="col">
{% for bf_entity in entities %}
  {% set id = bf_entity[1].split("/")[-1] %}
  <div class="mb-3">
    <label for="{{ id }}" class="col-form-label">BIBFRAME {{ bf_entity[0] }} URL</label> 
    <input type="text" id="{{ id }}" class="form-control bf-entity" value="{{ bf_entity[1] }}">
  </div>
{% endfor %}
  <button type="button" id="build-graph-btn" class="btn btn-primary">Build RDF Graph</button>
</div>"""
)


def bibframe(element_id: str, urls: list):
    form_element = js.document.getElementById(element_id)
    form_element.classList.add("col")
    entities = zip(("Work", "Instance", "Item"), urls)
    form_element.innerHTML = bf_template.render(entities=entities)
    button = js.document.getElementById("build-graph-btn")
    button.addEventListener("click", create_proxy(_build_graph))


sparql_template = Template(
    """<div class="mb-3">
    <label for="bf-sparql-queries" class="form-label">SPARQL Query</label>
    <textarea class="form-control" id="bf-sparql-queries" rows="10">
{% for ns in namespaces %}PREFIX {{ ns[0] }}: <{{ ns[1] }}>\n{% endfor %}
    </textarea>
  </div>
  <div class="mb-3">
    <button class="btn btn-primary" py-click="run_query">Run query</button>
  </div>
</div>"""
)


def bibframe_sparql(element_id: str):
    wrapper_div = js.document.getElementById(element_id)
    all_namespaces = NAMESPACES + [("rdf", rdflib.RDF), ("rdfs", rdflib.RDFS)]
    wrapper_div.innerHTML = sparql_template.render(namespaces=all_namespaces)
