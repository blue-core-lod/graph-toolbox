"""Pinned searches and saved job settings, kept in the browser's LocalStorage.

This runs in the browser under PyScript and never talks to the server. A page
loads it through PyScript's ``files`` config and opens a store for the user
that ``/api/config`` names::

    <script type="py" config='{"files": {"<static_url py/saved.py>": "./saved.py"}}'>
    import saved
    store = saved.open_store(config["user_id"])
    </script>

Saved entries only exist in one browser profile. They don't sync between
browsers, and clearing site data removes them. Keeping each user's entries
under their own key keeps them tidy but doesn't authorize anything: any search
or job started from a saved entry is still checked by the backend.

Layout: one key per user and kind,
``bluecore:graph-toolbox:v<SCHEMA_VERSION>:<user>:<searches|settings>``, holding
a JSON list of entries. Each list is written with one ``setItem``, so a failed
write leaves the previous list as it was.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote

try:
    # Pyodide raises JavaScript errors (QuotaExceededError, SecurityError)
    # as JsException.
    from pyodide.ffi import JsException as BrowserError
except ImportError:
    # Outside the browser, as under pytest, a fake storage raises OSError.
    BrowserError = OSError


APP = "graph-toolbox"
SCHEMA_VERSION = 1

SEARCH, SETTING = "search", "setting"

KINDS = {SEARCH: "searches", SETTING: "settings"}

# Operations this version can rerun or restore. Entries for any other
# operation (one saved by a newer Toolbox, say) are kept and listed with
# supported=False, so a screen can show them without offering to run them.
OPERATIONS = {
    SEARCH: frozenset({"sparql"}),
    SETTING: frozenset({"marc-to-bibframe", "bulk-update"}),
}

MAX_NAME_LENGTH = 200

# Enough for a query and its options, or a job profile.
MAX_PAYLOAD_BYTES = 16 * 1024

# A payload key containing any of these means a secret was about to be saved.
FORBIDDEN_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "credential",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
)

# Upgrades for entries saved by older versions: MIGRATIONS[n] turns a version n
# entry into a version n + 1 entry. Empty until SCHEMA_VERSION goes past 1.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


class Storage(Protocol):
    """The part of the Web Storage API the store uses."""

    def getItem(self, key: str) -> str | None: ...

    def setItem(self, key: str, value: str) -> None: ...


class StorageError(Exception):
    """A save, change or delete that didn't happen. ``str()`` is safe to show."""


@dataclasses.dataclass(frozen=True)
class Entry:
    id: str
    kind: str
    name: str
    operation: str
    payload: dict[str, Any]
    created: str
    modified: str
    user: str
    schema_version: int

    @property
    def supported(self) -> bool:
        """Whether this version of the Toolbox can rerun or restore it."""
        return self.operation in OPERATIONS[self.kind]

    def to_json(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class SavedStore:
    """Create, list, get, update and delete one signed-in user's saved entries.

    ``storage`` is ``window.localStorage``, or None when the browser won't
    provide it. Reads never raise: unavailable or unreadable storage reads as
    empty. Writes raise StorageError and leave what was already saved alone.
    """

    def __init__(
        self,
        storage: Storage | None,
        user_id: str,
        *,
        now: Callable[[], str] | None = None,
        new_id: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("A signed-in user's ID is required.")
        self._storage = storage
        self.user_id = user_id
        self._now = now or (lambda: datetime.now(UTC).isoformat(timespec="seconds"))
        self._new_id = new_id or (lambda: str(uuid.uuid4()))

    @property
    def available(self) -> bool:
        return self._storage is not None

    def key(self, kind: str, version: int | None = None) -> str:
        if kind not in KINDS:
            raise ValueError(f"Unknown kind {kind!r}.")
        version = SCHEMA_VERSION if version is None else version
        user = quote(self.user_id, safe="")
        return f"bluecore:{APP}:v{version}:{user}:{KINDS[kind]}"

    def list(self, kind: str) -> list[Entry]:
        """Valid entries of ``kind``, most recently changed first."""
        entries = (_parse(item, kind, self.user_id) for item in self._read(kind))
        return sorted(
            (entry for entry in entries if entry is not None),
            key=lambda entry: entry.modified,
            reverse=True,
        )

    def get(self, kind: str, entry_id: str) -> Entry | None:
        return next((e for e in self.list(kind) if e.id == entry_id), None)

    def create(
        self, kind: str, name: str, operation: str, payload: dict[str, Any]
    ) -> Entry:
        self.key(kind)
        if operation not in OPERATIONS[kind]:
            raise ValueError(f"{operation!r} can't be saved as a {kind}.")
        now = self._now()
        entry = Entry(
            id=self._new_id(),
            kind=kind,
            name=_check_name(name),
            operation=operation,
            payload=_check_payload(payload),
            created=now,
            modified=now,
            user=self.user_id,
            schema_version=SCHEMA_VERSION,
        )
        self._write(kind, [*self._read(kind), entry.to_json()])
        return entry

    def update(
        self,
        kind: str,
        entry_id: str,
        *,
        name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Entry:
        stored = self._read(kind)
        for index, item in enumerate(stored):
            entry = _parse(item, kind, self.user_id)
            if entry is not None and entry.id == entry_id:
                break
        else:
            raise StorageError("That saved item no longer exists.")
        if not entry.supported:
            raise StorageError(
                "This saved item is from a newer Toolbox and can't be changed here."
            )
        changed = dataclasses.replace(
            entry,
            name=entry.name if name is None else _check_name(name),
            payload=entry.payload if payload is None else _check_payload(payload),
            modified=self._now(),
        )
        stored[index] = changed.to_json()
        self._write(kind, stored)
        return changed

    def delete(self, kind: str, entry_id: str) -> bool:
        """Remove one entry. False if it wasn't there."""
        stored = self._read(kind)
        kept = [
            item
            for item in stored
            if (entry := _parse(item, kind, self.user_id)) is None
            or entry.id != entry_id
        ]
        if len(kept) == len(stored):
            return False
        self._write(kind, kept)
        return True

    def _get(self, key: str) -> str | None:
        if self._storage is None:
            return None
        try:
            value = self._storage.getItem(key)
        except BrowserError:
            # Some browsers throw on every read when storage is blocked.
            return None
        # A missing key is JavaScript null, which Pyodide passes on as JsNull,
        # not None, so anything that isn't text counts as nothing saved.
        return value if isinstance(value, str) else None

    def _read(self, kind: str) -> list[Any]:
        """Everything stored for ``kind``, valid or not.

        Malformed items are returned too, so writes put them back untouched
        rather than dropping them. If nothing is saved under the current
        version, older versions' entries are upgraded in memory; they're
        written under the new key on the next save, and the old key is left
        for an older Toolbox to keep using.
        """
        raw = self._get(self.key(kind))
        if raw is None:
            return self._migrate(kind)
        return _load_list(raw)

    def _migrate(self, kind: str) -> list[Any]:
        for version in range(SCHEMA_VERSION - 1, 0, -1):
            raw = self._get(self.key(kind, version))
            if raw is None:
                continue
            upgraded = []
            for item in _load_list(raw):
                try:
                    for step in range(version, SCHEMA_VERSION):
                        item = MIGRATIONS[step](item)
                except (KeyError, TypeError, ValueError):
                    continue
                upgraded.append(item)
            return upgraded
        return []

    def _write(self, kind: str, stored: list[Any]) -> None:
        if self._storage is None:
            raise StorageError(
                "This browser isn't letting the Toolbox save anything, "
                "so nothing was saved."
            )
        try:
            self._storage.setItem(self.key(kind), json.dumps(stored))
        except BrowserError as error:
            raise StorageError(
                "Couldn't save: this site's browser storage may be full. "
                "Delete some saved items and try again. "
                "Nothing already saved was changed."
            ) from error


def open_store(user_id: str) -> SavedStore:
    """A store over this browser's LocalStorage. Only works under PyScript."""
    from pyscript import window

    try:
        storage = window.localStorage
    except BrowserError:
        # Reading localStorage itself throws when site data is blocked.
        storage = None
    return SavedStore(storage, user_id)


def _load_list(raw: str) -> list[Any]:
    try:
        stored = json.loads(raw)
    except ValueError:
        return []
    return stored if isinstance(stored, list) else []


def _parse(raw: Any, kind: str, user: str) -> Entry | None:
    """An Entry from stored JSON, or None if it's malformed or someone else's."""
    if not isinstance(raw, dict):
        return None
    try:
        entry = Entry(**raw)
    except TypeError:
        return None
    text = (entry.id, entry.name, entry.operation, entry.created, entry.modified)
    if not all(isinstance(value, str) and value for value in text):
        return None
    if not isinstance(entry.payload, dict):
        return None
    if (entry.kind, entry.user, entry.schema_version) != (kind, user, SCHEMA_VERSION):
        return None
    return entry


def _check_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Give it a name.")
    name = name.strip()
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Names can be at most {MAX_NAME_LENGTH} characters.")
    return name


def _check_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("Saved options must be a JSON object.")
    _check_keys(payload)
    try:
        text = json.dumps(payload)
    except (TypeError, ValueError) as error:
        raise TypeError("Saved options must be plain JSON.") from error
    if len(text.encode()) > MAX_PAYLOAD_BYTES:
        raise ValueError(
            "Those options are too large to save. Queries and job settings "
            "are saved, never files, reports or results."
        )
    # A copy, so later changes to the caller's dict don't leak into the entry.
    return json.loads(text)


def _check_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if any(part in str(key).lower() for part in FORBIDDEN_KEY_PARTS):
                raise ValueError(
                    f"Options can't include {key!r}: "
                    "credentials and tokens are never saved."
                )
            _check_keys(item)
    elif isinstance(value, list):
        for item in value:
            _check_keys(item)
