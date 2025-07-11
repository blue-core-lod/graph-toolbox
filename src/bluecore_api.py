import json

from datetime import datetime, timedelta, UTC
from js import console, document, sessionStorage
from pyodide.http import pyfetch


def _expires_at(seconds: int) -> str:
    now = datetime.now(UTC)
    expires = now + timedelta(seconds=seconds)
    return expires.isoformat()


async def _get_keycloak_token():
    bluecore_env_radio = document.getElementsByName("bluecore_env")
    for radio_input in bluecore_env_radio:
        if radio_input.checked:
            bluecore_env = radio_input.value
    user_element = document.getElementById("keycloak_username")
    keycloak_username = user_element.value
    user_password = document.getElementById("keycloak_password")
    keycloak_password = user_password.value
    form_bytes = bytes(f"client_id=bluecore_api&username={keycloak_username}&password={keycloak_password}&grant_type=password",
                       encoding='utf-8')
    token_request = await pyfetch(
        f"{bluecore_env}/keycloak/realms/bluecore/protocol/openid-connect/token",
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
