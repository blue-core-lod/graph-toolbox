import json

from datetime import datetime, timedelta, UTC
from js import alert, console, document, File, FormData, sessionStorage
from pyodide.http import pyfetch
from state import BLUECORE_ENV, BF_GRAPH

def _expires_at(seconds: int) -> str:
    now = datetime.now(UTC)
    expires = now + timedelta(seconds=seconds)
    return expires.isoformat()


async def _get_keycloak_token():
    global BLUECORE_ENV

    username = document.getElementById("user-name")
    bluecore_env_label = document.getElementById("bluecore-env-label")
    bluecore_env_radio = document.getElementsByName("bluecore_env")
    env_label = ""
    for radio_input in bluecore_env_radio:
        if radio_input.checked:
            BLUECORE_ENV = radio_input.value
    user_element = document.getElementById("keycloak_username")
    keycloak_username = user_element.value
    user_password = document.getElementById("keycloak_password")
    keycloak_password = user_password.value
    form_bytes = bytes(f"client_id=bluecore_api&username={keycloak_username}&password={keycloak_password}&grant_type=password",
                       encoding='utf-8')
    token_request = await pyfetch(
        f"{BLUECORE_ENV}/keycloak/realms/bluecore/protocol/openid-connect/token",
        method = "POST",
        headers={
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body=form_bytes
    )
    token_result = await token_request.json()
    username.innerHTML = keycloak_username
    bluecore_env_label.innerHTML = f"for {BLUECORE_ENV}"
    return token_result
    

async def bluecore_login(event):
    tokens = await _get_keycloak_token()
    sessionStorage.setItem("keycloak_access_token", tokens.get("access_token"))
    sessionStorage.setItem("keycloak_access_expires", _expires_at(tokens.get("expires_in")))
    sessionStorage.setItem("keycloak_refresh_token", tokens.get("refresh_token"))
    sessionStorage.setItem("keycloak_refresh_expires", _expires_at(tokens.get('refresh_expires_in')))

    close_btn = document.getElementById("loginModalhModalCloseBtn")
    close_btn.click()

async def save_bluecore(event):
    global BLUECORE_ENV
    global BF_GRAPH

    if BLUECORE_ENV is None:
        alert(f"Cannot save!\nBluecore Environment not set")
        return
    if len(BF_GRAPH) < 0:
        alert(f"Cannot save empty graph")
        return
    access_token = sessionStorage.getItem("keycloak_access_token")
    form_data = FormData.new()
    
    bf_upload_file = File.new([BF_GRAPH.serialize(format='json-ld')],
                              "upload",
                              { "type": "text/plain"})
    form_data.append('file', bf_upload_file)
    bench_heading = document.getElementById("bench-heading")
    bench_bc_result = document.getElementById("bc-results")
    batch_result = await pyfetch(
        f"{BLUECORE_ENV}/api/batches/upload/",
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        body=form_data
    )
    if batch_result.ok:
        bench_heading.innerHTML = "Saving Graph to Blue Core API"
        batch_message = await batch_result.json()
        console.log(f"Saved graph", batch_message.keys())
        workflow_uri = f"{BLUECORE_ENV}/workflows/dags/resource_loader/runs/{batch_message.get('workflow_id')}"
        bench_bc_result.innerHTML = f"""Workflow at <a href="{workflow_uri}" target="_blank">{workflow_uri}</a>"""
    else:
        bench_heading.innerHTML = """<span class="text-danger">ERROR!!</span>"""
        bench_bc_result.innerHTML = await batch_result.text

