import json

from datetime import datetime, timedelta, UTC
from urllib.parse import urlencode

from js import alert, console, document, File, FormData, sessionStorage
from pyodide.http import AbortError, pyfetch


def _get_app():
    """Get the app instance to access state."""
    from app import app
    return app


def _expires_at(seconds: int) -> str:
    now = datetime.now(UTC)
    expires = now + timedelta(seconds=seconds)
    return expires.isoformat()


async def _get_keycloak_token():
    global BLUECORE_ENV

    username = document.getElementById("user-name")
    user_element = document.getElementById("keycloak_username")
    keycloak_username = user_element.value
    user_password = document.getElementById("keycloak_password")
    keycloak_password = user_password.value
    form_bytes = bytes(
        f"client_id=bluecore_api&username={keycloak_username}&password={keycloak_password}&grant_type=password",
        encoding="utf-8",
    )
    try:
        token_request = await pyfetch(
            f"{BLUECORE_ENV}/keycloak/realms/bluecore/protocol/openid-connect/token",
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=form_bytes,
        )
        if token_request.ok:
            token_result = await token_request.json()
            username.innerHTML = keycloak_username
            return token_result
        else:
            error_text = await token_request.text()
            alert(f"Error retrieving token {error_text}")
    except AbortError as e:
        alert(f"Error! {e}")
        return


async def bluecore_login(event):
    close_btn = document.getElementById("loginModalhModalCloseBtn")
    tokens = await _get_keycloak_token()
    if not tokens:
        close_btn.click()
        return
    sessionStorage.setItem("keycloak_access_token", tokens.get("access_token"))
    sessionStorage.setItem(
        "keycloak_access_expires", _expires_at(tokens.get("expires_in"))
    )
    sessionStorage.setItem("keycloak_refresh_token", tokens.get("refresh_token"))
    sessionStorage.setItem(
        "keycloak_refresh_expires", _expires_at(tokens.get("refresh_expires_in"))
    )
    close_btn.click()


async def save_bluecore(event):
    app = _get_app()
    bluecore_env = app.state.get("bluecore_env")
    bf_graph = app.state.get("bf_graph")

    if bluecore_env is None:
        alert(f"Cannot save!\nBluecore Environment not set")
        return
    if len(bf_graph) < 0:
        alert(f"Cannot save empty graph")
        return
    access_token = sessionStorage.getItem("keycloak_access_token")
    form_data = FormData.new()

    bf_upload_file = File.new(
        [bf_graph.serialize(format="json-ld")], "upload", {"type": "text/plain"}
    )
    form_data.append("file", bf_upload_file)
    bench_heading = document.getElementById("bench-heading")
    bench_bc_result = document.getElementById("bc-results")
    bench_bc_result.innerHTML = ""
    batch_result = await pyfetch(
        f"{bluecore_env}/api/batches/upload/",
        method="POST",
        headers={"Authorization": f"Bearer {access_token}"},
        body=form_data,
    )
    if batch_result.ok:
        bench_heading.innerHTML = "Saving Graph to Blue Core API"
        batch_message = await batch_result.json()
        workflow_uri = f"{bluecore_env}/workflows/dags/resource_loader/runs/{batch_message.get('workflow_id')}"
        bench_bc_result.innerHTML = f"""Workflow at <a href="{workflow_uri}" target="_blank">{workflow_uri}</a>"""
    else:
        bench_heading.innerHTML = """<span class="text-danger">ERROR!!</span>"""
        bench_bc_result.innerHTML = await batch_result.text


async def search_bluecore(event):
    """
    Searches Blue Core using API.
    Creates search result items using direct DOM manipulation.
    """
    import rdflib
    from pyodide.ffi import create_proxy

    BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")

    app = _get_app()
    bluecore_env = app.state.get("bluecore_env")

    query_elem = document.getElementById("ai-search-resources")
    bench_heading = document.getElementById("bench-heading")
    search_results_tab = document.getElementById("search-results-tab")
    search_results_tab.classList.remove("d-none")
    bench_bc_results = document.getElementById("search-results")
    for class_ in ["active", "show"]:
        bench_bc_results.classList.add(class_)
    bench_bc_results.innerHTML = ""
    search_url = f"{bluecore_env}/api/search?" + urlencode({"q": query_elem.value})
    search_result = await pyfetch(search_url)
    if search_result.ok:
        search_result_json = await search_result.json()
        total_results = int(search_result_json.get("total", 0))
        if total_results < 1:
            bench_heading.innerHTML = """<h3>No results from Blue Core</h3>"""
        else:
            bench_heading.innerHTML = (
                f"""<h3>{total_results:,} results from Blue Core</h3>"""
            )

        div_query = document.createElement("div")
        div_query.innerHTML = f"""<strong>Query:</strong><p>{query_elem.value}</p>"""
        bench_bc_results.append(div_query)

        # Create search result items using direct DOM manipulation
        # Note: SearchResultItem component exists in components.py but is meant for use
        # within Puepy templates. For programmatic creation, we use DOM directly.
        for item in search_result_json.get("results", []):
            from load_rdf import load_uri_into_graph

            # Create alert container
            alert_div = document.createElement("div")
            for class_ in ["alert", "alert-info", "alert-dismissible", "fade", "show"]:
                alert_div.classList.add(class_)

            # Extract data from item
            uri = item.get("uri", "")
            resource_type = item.get("type", "").title()

            # Parse RDF data and extract titles
            graph = rdflib.Graph()
            graph.parse(data=item.get("data"), format="json-ld")
            title_query = graph.query(
                """
                SELECT ?mainTitle
                WHERE {
                    ?title a bf:Title .
                    ?title bf:mainTitle ?mainTitle .
                }
                """,
                initNs={"bf": BF},
            )
            main_titles = [str(main_title[0]) for main_title in title_query]
            serialized_rdf = graph.serialize(format="json-ld")

            # Build HTML content
            titles_html = f"<h3>{chr(10).join(main_titles)}</h3>" if main_titles else ""

            alert_div.innerHTML = f"""
                <strong class="text-primary">Blue Core Resource</strong>
                <small>{resource_type}</small>
                {titles_html}
                <p><a href="{uri}">{uri}</a></p>
                <textarea class="d-none" id="{uri}-rdf">{serialized_rdf}</textarea>
                <button type="button" class="btn btn-success btn-load-uri" data-uri="{uri}">Load</button>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            """

            # Add click handler for Load button
            def create_load_handler(item_uri):
                def handler(event):
                    from load_rdf import load_uri_into_graph
                    from js import document

                    # Get the current graph from application state
                    bf_graph = app.state.get("bf_graph")
                    if bf_graph is None:
                        alert("Graph not initialized. Please initialize the application first.")
                        return

                    # Get the RDF data
                    rdf_data_div = document.getElementById(f"{item_uri}-rdf")
                    if not rdf_data_div:
                        alert(f"Could not find RDF data for {item_uri}")
                        return

                    rdf_data = rdf_data_div.value

                    # Load the URI into the graph
                    updated_graph = load_uri_into_graph(bf_graph, item_uri, rdf_data)

                    # Update the application state
                    app.state["bf_graph"] = updated_graph

                    # Close the alert
                    button = event.target
                    parent_div = button.parentElement
                    close_btn = parent_div.querySelector(".btn-close")
                    if close_btn:
                        close_btn.click()

                return handler

            # Find and attach the load button handler
            load_button = alert_div.querySelector(".btn-load-uri")
            if load_button:
                # Create a proxy to prevent the handler from being garbage collected
                handler_proxy = create_proxy(create_load_handler(uri))
                load_button.addEventListener("click", handler_proxy)

            bench_bc_results.append(alert_div)


async def set_environment(this):
    app = _get_app()
    bluecore_env = this.target.getAttribute("data-env")
    app.state["bluecore_env"] = bluecore_env
    sessionStorage.removeItem("keycloak_access_token")
    sessionStorage.removeItem("keycloak_access_expires")
    sessionStorage.removeItem("keycloak_refresh_token")
    sessionStorage.removeItem("keycloak_refresh_expires")
