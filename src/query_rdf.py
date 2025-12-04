import json

import pandas as pd

from pyparsing.exceptions import ParseException

from js import alert, console, document
from load_rdf import bibframe_sparql


def _get_app():
    """Get the app instance to access state."""
    from app import app

    return app


async def download_query_results(app, serialization):
    sparql_results = app.state.get("sparql_results")
    results_df = pd.DataFrame(sparql_results.bindings)

    if len(results_df) < 1:
        alert("No query results to download")
        return

    console.log(f"Download query results {serialization} {len(results_df)}")
    mime_type, contents = None, None
    match serialization:
        case "csv":
            mime_type = "text/csv"
            contents = results_df.to_csv(index=False)

        case "json":
            mime_type = "application/json"
            contents = json.dumps(results_df.to_dict(orient="records"))

        case _:
            alert(f"Unknown serialization {serialization}")
            return
    return contents, mime_type


async def run_query(*args, **kwargs):
    app = kwargs.get("app")
    sparql_query = kwargs.get("sparql_query", "")

    if len(sparql_query) < 1:
        alert("No SPARQL query to run.")
        return

    if not app:
        app = _get_app()

    bf_graph = app.state.get("bf_graph")

    if not bf_graph:
        alert("Graph not initialized. Please load data first.")
        return

    try:
        app.state["sparql_results"] = bf_graph.query(sparql_query)
    except ParseException:
        bf_graph.update(sparql_query)
        # TODO: Need to update app state with results
    except Exception as e:
        alert(f"SPARQL Query Error {e}")


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
    query_element = document.getElementById("bf-sparql-query")
    query_element.value = f"{query_element.innerHTML}\n{sparql_query}"
    run_query_btn = document.getElementById("run-query-btn")
    run_query_btn.click()
