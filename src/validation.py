import pyshacl
import rdflib

from js import console, document
from state import BF_GRAPH

async def create_alert(is_valid: bool, total_triples: int):
    alert = document.createElement("div")
    alert.setAttribute("style", "margin: 1em;")
    alert.setAttribute("role", "alert")
    alert_msg = f"{total_triples:,} triples"
    css_classes = ["alert", "alert-dismissible", "fade", "show"]
    match is_valid:

        case True:
            css_classes.append("alert-success")
            alert.innerText = f"{alert_msg} Passed!"

        case False:
            css_classes.append("alert-danger")
            alert.innerText = f"{alert_msg} Failed!"

    for css_class in css_classes:
        alert.classList.add(css_class)

    return alert



async def bf(graph: rdflib.Graph | None):
    global BF_GRAPH

    if not graph:
        graph = BF_GRAPH

    console.log(f"BF graph", len(graph))
    validation_graph = rdflib.Graph()
    validation_graph.parse("./shacl/all.ttl", format='turtle')

    conforms, results_graph, _ = pyshacl.validate(
        graph, shacl_graph=validation_graph, allow_warnings=True
    )

    alert = create_alert(conforms, len(graph))
    console.log(conforms, results_graph.serialize(format='turtle'))
