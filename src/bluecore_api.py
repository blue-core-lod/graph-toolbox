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


async def save_bluecore(event, app=None):
    if app is None:
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
    bench_bc_result = document.getElementById("search-results")
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


async def search_bluecore(event, app=None, query=""):
    """
    Searches Blue Core using API.
    Stores results in application state for Puepy components to render.
    """
    if app is None:
        app = _get_app()

    bluecore_env = app.state.get("bluecore_env")

    search_url = f"{bluecore_env}/api/search?" + urlencode({"q": query})
    search_result = await pyfetch(search_url)

    if search_result.ok:
        search_result_json = await search_result.json()
        total_results = int(search_result_json.get("total", 0))

        if total_results < 1:
            app.state["search_results"] = []
        else:
            # Store results in state - Puepy components will render them
            app.state["search_results"] = search_result_json.get("results", [])


async def set_environment(this):
    app = _get_app()
    bluecore_env = this.target.getAttribute("data-env")
    app.state["bluecore_env"] = bluecore_env
    sessionStorage.removeItem("keycloak_access_token")
    sessionStorage.removeItem("keycloak_access_expires")
    sessionStorage.removeItem("keycloak_refresh_token")
    sessionStorage.removeItem("keycloak_refresh_expires")
