import json

import js

import pandas as pd

import helpers

from load_rdf import bibframe_sparql

from jinja2 import Template


def _get_app():
    """Get the app instance to access state."""
    from app import app
    return app

query_results_template = Template(
    """<div class="w-100">
 <div>
  <div class="dropdown">
    <button class="btn btn-secondary dropdown-toggle" 
            type="button" 
            data-bs-toggle="dropdown"
            id="rdf-download-file"
            aria-expanded="false">
      Download Results
    </button>
    <ul class="dropdown-menu" aria-labelledby="rdf-download-file">
        <li><a py-click="download_query_results" data-serialization='csv' class="dropdown-item" href="#">CSV (.csv)</a></li>
        <li><a class="dropdown-item" py-click="download_query_results" data-serialization='json' href="#">JSON (.json)</a></li>
    </ul>
  </div>
</div>
<table class="table">          
  <thead>
    <tr>
   {% for var in vars %}
     <th>{{ var }}</th>
   {% endfor %} 
    </tr>                       
  </thead>
  <tbody>
    {% for result in results %}
     <tr>
      {% for var in vars %}
      <td>{{ result[var] }}</td>
      {% endfor %}                     
     </tr> 
    {% endfor %}                        
  </tbody>
</table>
</div>           
"""
)


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


async def run_query(*args):
    app = _get_app()
    bf_graph = app.state.get("bf_graph")

    if not bf_graph:
        js.alert("Graph not initialized. Please load data first.")
        return

    bench_header = js.document.getElementById("bench-heading")
    query_element = js.document.getElementById("bf-sparql-query")
    sparql_query = query_element.value
    tab = js.document.getElementById("bf-sparql-results-tab")
    tab.classList.remove("d-none")
    output_element = js.document.getElementById("bf-sparql-results")
    for class_ in ["active", "show"]:
        output_element.classList.add(class_)
    output_element.content = ""
    try:
        query = bf_graph.query(sparql_query)
        results_df = pd.DataFrame(query.bindings)
        app.state["results_df"] = results_df
        output_element.innerHTML = query_results_template.render(
            vars=query.vars, results=query.bindings
        )
        bench_header.innerHTML = f"<h2>Query Results {len(query.bindings):,} Rows</h2>"
    except Exception as e:
        output_element.content = f"""<h2>Query Error</h2><p>{e}</p>"""


async def run_summary_query(event):
    data_query = getattr(event.target.attributes, "data-query")

    match data_query.value:
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
    query_element.innerHTML = f"{query_element.innerHTML}\n{sparql_query}"
    run_query_btn = js.document.getElementById("run-query-btn")
    run_query_btn.click()
