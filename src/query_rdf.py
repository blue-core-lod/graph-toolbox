import json

import js
import helpers

from load_rdf import bibframe_sparql

def _get_app():
    """Get the app instance to access state."""
    from app import app

    return app



async def download_query_results(event):
    app = _get_app()
    results_df = app.state.get("results_df")

    if results_df is None:
        js.alert("No query results to download")
        return

    serialization = event.target.getAttribute("data-serialization")
    js.console.log(f"Download query results {serialization} {len(results_df)}")
    mime_type, content = None, None
    match serialization:
        case "csv":
            mime_type = "text/csv"
            contents = results_df.to_csv(index=False)

        case "json":
            mime_type = "application/json"
            contents = json.dumps(results_df.to_dict(orient="records"))

        case _:
            js.alert(f"Unknown serialization {serialization}")
            return
    blob = js.Blob.new([contents], {"type": mime_type})
    anchor = js.document.createElement("a")
    anchor.href = js.URL.createObjectURL(blob)
    anchor.download = f"query-results.{serialization}"
    js.document.body.appendChild(anchor)
    anchor.click()
    js.document.body.removeChild(anchor)


async def run_query(*args, **kwargs):
    app = kwargs.get("app")
    sparql_query = kwargs.get("sparql_query", "")

    if len(sparql_query) < 1:
        js.alert("No SPARQL query to run.")
        return

    if not app:
        app = _get_app()
    
    bf_graph = app.state.get("bf_graph")

    if not bf_graph:
        js.alert("Graph not initialized. Please load data first.")
        return

    try:
        app.state["sparql_results"] = bf_graph.query(sparql_query)
    except Exception as e:
        js.alert(f"SPARQL Query Error {e}")


def run_summary_query(query_type):

    match query_type:
        case "all":
            sparql_query = """SELECT ?subject ?predicate ?object WHERE { ?subject ?predicate ?object . }"""

        case "object":
            sparql_query = """SELECT DISTINCT ?object WHERE { ?s ?p ?object . }"""

        case "predicate":
            sparql_query = """SELECT DISTINCT ?predicate WHERE { ?s ?predicate ?o . }"""

        case "subject":
            sparql_query = """SELECT DISTINCT ?subject WHERE { ?subject ?p ?o . }"""

    bibframe_sparql("bf-sparql-query")
    query_element = js.document.getElementById("bf-sparql-query")
    query_element.value = f"{query_element.innerHTML}\n{sparql_query}"
    run_query_btn = js.document.getElementById("run-query-btn")
    run_query_btn.click()
