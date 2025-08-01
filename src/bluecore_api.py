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

    bluecore_env_radio = document.getElementsByName("bluecore_env")
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
    batch_result = await pyfetch(
        f"{BLUECORE_ENV}/api/batches/upload/",
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        body=form_data
    )
    if batch_result.ok:
        console.log(f"Saved graph")
