"""Tests for the Toolbox's identity and policy dependencies."""

from __future__ import annotations

import jwt
import pytest

from bluecore_graph_toolbox import __version__, deps


class KeycloakUser:
    """Stands in for the Keycloak auth manager's user."""

    def __init__(self, access_token: str | None, user_id: str = "sub-123") -> None:
        self.access_token = access_token
        self.user_id = user_id

    def get_id(self) -> str:
        return self.user_id


def _token(claims: dict) -> str:
    return jwt.encode(
        claims, "not-the-keycloak-signing-key-0123456789", algorithm="HS256"
    )


def test_user_agent_names_the_toolbox_and_its_version() -> None:
    assert deps.USER_AGENT == f"bluecore-graph-toolbox/{__version__}"


def test_user_uid_is_the_keycloak_subject() -> None:
    assert deps.user_uid(KeycloakUser(None, user_id="sub-456")) == "sub-456"


def test_user_roles_come_from_the_realm_roles() -> None:
    token = _token({"realm_access": {"roles": ["bluecore_admin", "cataloger"]}})

    assert deps.user_roles(KeycloakUser(token)) == {"bluecore_admin", "cataloger"}


@pytest.mark.parametrize(
    "token",
    [
        None,
        "",
        "not-a-jwt",
        _token({}),
        _token({"realm_access": ["bluecore_admin"]}),
        _token({"realm_access": {}}),
        _token({"realm_access": {"roles": None}}),
        _token({"realm_access": {"roles": 42}}),
        _token({"realm_access": {"roles": "bluecore_admin"}}),
        _token({"realm_access": {"roles": {"bluecore_admin": True}}}),
    ],
    ids=[
        "none",
        "empty",
        "malformed",
        "no-claim",
        "not-a-dict",
        "no-roles",
        "roles-null",
        "roles-number",
        "roles-string",
        "roles-dict",
    ],
)
def test_user_roles_fail_closed(token: str | None) -> None:
    assert deps.user_roles(KeycloakUser(token)) == frozenset()


def test_user_roles_skip_entries_that_are_not_strings() -> None:
    # str() would turn null into a role named "None"; drop such entries instead.
    token = _token({"realm_access": {"roles": ["cataloger", None, 7, ["x"], {}]}})

    assert deps.user_roles(KeycloakUser(token)) == {"cataloger"}


def test_user_without_a_token_attribute_has_no_roles() -> None:
    # The simple auth manager, used in local development, has no access_token.
    class SimpleUser:
        def get_id(self) -> str:
            return "admin"

    assert deps.user_roles(SimpleUser()) == frozenset()


def test_only_bluecore_admin_is_an_admin_role() -> None:
    assert deps.ADMIN_ROLES == {"bluecore_admin"}
