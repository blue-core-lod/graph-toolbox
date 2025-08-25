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



async def validate(event):
    global BF_GRAPH

    validation_graph = rdflib.Graph()
    validation_graph.parse("./shacl/all.ttl", format='turtle')

    conforms, results_graph, results_str = pyshacl.validate(
        BF_GRAPH, shacl_graph=validation_graph, allow_warnings=True
    )

    alert = await create_alert(conforms, len(BF_GRAPH))
    validation_tab = document.getElementById("bf-validation-results-tab")
    validation_tab.classList.remove("d-none")
    validation_tab_pane = document.getElementById("bf-validation-results")
    validation_tab_pane.classList.remove("d-none")
    validation_tab_pane.appendChild(alert)
    results_str = results_graph.serialize(format='turtle')
    pre = document.createElement("pre")
    pre.setAttribute("style", "margin: 1em;")
    pre.innerHTML = results_str.replace("<", "&lt;").replace(">", "&gt;")
    validation_tab_pane.appendChild(pre)
