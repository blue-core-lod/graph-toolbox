"""Tests for the LocalStorage adapter for saved searches and settings.

The adapter runs in the browser under PyScript, so it isn't importable as part
of the package. It's loaded from its file, with a dict standing in for
``window.localStorage``.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from bluecore_graph_toolbox.plugin import STATIC_DIR

SAVED_PY = STATIC_DIR / "py" / "saved.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("saved", SAVED_PY)
    module = importlib.util.module_from_spec(spec)
    # dataclasses looks the module up in sys.modules while building Entry.
    sys.modules["saved"] = module
    spec.loader.exec_module(module)
    return module


saved = _load()


class FakeStorage(dict):
    """``window.localStorage``, with switches for the ways a browser fails."""

    def __init__(self) -> None:
        super().__init__()
        self.blocked = False
        self.full = False

    def getItem(self, key: str) -> str | None:
        if self.blocked:
            raise OSError("SecurityError")
        return self.get(key)

    def setItem(self, key: str, value: str) -> None:
        if self.blocked or self.full:
            raise OSError("QuotaExceededError")
        self[key] = value


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


def _store(storage: FakeStorage | None, user: str = "user-1") -> saved.SavedStore:
    # Timestamps a second apart, so "most recent first" is predictable.
    ticks = itertools.count()
    ids = itertools.count(1)
    return saved.SavedStore(
        storage,
        user,
        now=lambda: f"2026-11-19T00:00:{next(ticks):02d}+00:00",
        new_id=lambda: f"id-{next(ids)}",
    )


@pytest.fixture
def store(storage: FakeStorage) -> saved.SavedStore:
    return _store(storage)


# Round trips


def test_create_get_list_update_delete_round_trip(store: saved.SavedStore) -> None:
    entry = store.create(saved.SEARCH, "Recent works", "sparql", {"query": "SELECT"})

    assert entry.kind == saved.SEARCH
    assert entry.user == "user-1"
    assert entry.schema_version == saved.SCHEMA_VERSION
    assert entry.created == entry.modified
    assert store.get(saved.SEARCH, entry.id) == entry
    assert store.list(saved.SEARCH) == [entry]

    changed = store.update(saved.SEARCH, entry.id, name="Older works")

    assert changed.name == "Older works"
    assert changed.payload == {"query": "SELECT"}
    assert changed.created == entry.created
    assert changed.modified > entry.modified
    assert store.get(saved.SEARCH, entry.id) == changed

    assert store.delete(saved.SEARCH, entry.id) is True
    assert store.list(saved.SEARCH) == []
    assert store.get(saved.SEARCH, entry.id) is None


def test_settings_round_trip_restores_the_job_options(store: saved.SavedStore) -> None:
    options = {"dry_run": True, "on_match": "replace", "duplicates_report": True}
    entry = store.create(saved.SETTING, "Weekly load", "marc-to-bibframe", options)

    store.update(saved.SETTING, entry.id, payload={**options, "dry_run": False})

    restored = store.get(saved.SETTING, entry.id)
    assert restored.payload == {**options, "dry_run": False}
    assert restored.supported is True


def test_searches_and_settings_are_kept_apart(store: saved.SavedStore) -> None:
    store.create(saved.SEARCH, "A search", "sparql", {"q": "maps"})

    assert store.list(saved.SETTING) == []


def test_list_is_most_recently_changed_first(store: saved.SavedStore) -> None:
    first = store.create(saved.SEARCH, "First", "sparql", {})
    second = store.create(saved.SEARCH, "Second", "sparql", {})
    store.update(saved.SEARCH, first.id, name="First, renamed")

    assert [e.id for e in store.list(saved.SEARCH)] == [first.id, second.id]


def test_a_missing_key_read_as_javascript_null_is_empty(
    storage: FakeStorage,
) -> None:
    # In the browser, getItem for a missing key gives Pyodide's JsNull, not None.
    class JsNull:
        pass

    storage.getItem = lambda key: JsNull()
    store = _store(storage)

    assert store.list(saved.SEARCH) == []
    assert store.list(saved.SETTING) == []


def test_entries_survive_a_reload(storage: FakeStorage) -> None:
    entry = _store(storage).create(saved.SEARCH, "Pinned", "sparql", {"q": "x"})

    # A reload or browser restart is a new store over the same storage.
    assert _store(storage).list(saved.SEARCH) == [entry]


def test_update_of_a_missing_entry_says_so(store: saved.SavedStore) -> None:
    with pytest.raises(saved.StorageError, match="no longer exists"):
        store.update(saved.SEARCH, "gone", name="x")


def test_delete_of_a_missing_entry_is_false(store: saved.SavedStore) -> None:
    store.create(saved.SEARCH, "Keep", "sparql", {})

    assert store.delete(saved.SEARCH, "gone") is False
    assert len(store.list(saved.SEARCH)) == 1


# Namespacing and users


def test_keys_name_the_app_version_user_and_kind(store: saved.SavedStore) -> None:
    assert store.key(saved.SEARCH) == "bluecore:graph-toolbox:v1:user-1:searches"
    assert store.key(saved.SETTING) == "bluecore:graph-toolbox:v1:user-1:settings"


def test_user_ids_cannot_reach_into_another_key(storage: FakeStorage) -> None:
    key = _store(storage, "a:b/c").key(saved.SEARCH)

    assert key == "bluecore:graph-toolbox:v1:a%3Ab%2Fc:searches"


def test_switching_users_hides_the_previous_users_entries(
    storage: FakeStorage,
) -> None:
    _store(storage, "user-1").create(saved.SEARCH, "Mine", "sparql", {})

    other = _store(storage, "user-2")

    assert other.list(saved.SEARCH) == []
    assert other.delete(saved.SEARCH, "id-1") is False
    assert len(_store(storage, "user-1").list(saved.SEARCH)) == 1


def test_entries_naming_another_user_are_not_shown(storage: FakeStorage) -> None:
    mine = _store(storage, "user-1").create(saved.SEARCH, "Mine", "sparql", {})
    # Someone copies user-1's entries under user-2's key by hand.
    storage[_store(storage, "user-2").key(saved.SEARCH)] = json.dumps([mine.to_json()])

    assert _store(storage, "user-2").list(saved.SEARCH) == []


def test_a_store_needs_a_user(storage: FakeStorage) -> None:
    for user in ("", None):
        with pytest.raises(ValueError, match="user"):
            saved.SavedStore(storage, user)


def test_unknown_kinds_are_refused(store: saved.SavedStore) -> None:
    with pytest.raises(ValueError, match="kind"):
        store.list("report")


# Validation


def test_names_are_trimmed(store: saved.SavedStore) -> None:
    assert store.create(saved.SEARCH, "  Spaced  ", "sparql", {}).name == "Spaced"


@pytest.mark.parametrize("name", ["", "   ", None, "x" * 201])
def test_bad_names_are_refused(store: saved.SavedStore, name: object) -> None:
    with pytest.raises(ValueError):
        store.create(saved.SEARCH, name, "sparql", {})


def test_operations_must_fit_the_kind(store: saved.SavedStore) -> None:
    with pytest.raises(ValueError, match="can't be saved"):
        store.create(saved.SEARCH, "Wrong", "marc-to-bibframe", {})


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "x"},
        {"Authorization": "Bearer x"},
        {"options": {"access_token": "x"}},
        {"steps": [{"client_secret": "x"}]},
        {"apiKey": "x"},
    ],
)
def test_credentials_are_never_saved(store: saved.SavedStore, payload: dict) -> None:
    with pytest.raises(ValueError, match="never saved"):
        store.create(saved.SEARCH, "Leaky", "sparql", payload)

    assert store.list(saved.SEARCH) == []


def test_large_payloads_are_refused(store: saved.SavedStore) -> None:
    marc_file = "x" * (saved.MAX_PAYLOAD_BYTES + 1)

    with pytest.raises(ValueError, match="too large"):
        store.create(saved.SETTING, "Big", "marc-to-bibframe", {"file": marc_file})


def test_later_changes_to_the_callers_dict_are_not_saved(
    store: saved.SavedStore,
) -> None:
    payload = {"query": "SELECT"}
    entry = store.create(saved.SEARCH, "Copy", "sparql", payload)
    payload["query"] = "DROP"

    assert store.get(saved.SEARCH, entry.id).payload == {"query": "SELECT"}


# Unsupported entries


def _from_a_newer_toolbox(store: saved.SavedStore, storage: FakeStorage) -> str:
    entry = store.create(saved.SETTING, "Mine", "marc-to-bibframe", {})
    newer = {**entry.to_json(), "id": "newer", "operation": "spreadsheet-to-bibframe"}
    key = store.key(saved.SETTING)
    storage[key] = json.dumps([*json.loads(storage[key]), newer])
    return "newer"


def test_unknown_operations_are_listed_as_unsupported(
    store: saved.SavedStore, storage: FakeStorage
) -> None:
    entry_id = _from_a_newer_toolbox(store, storage)

    entry = store.get(saved.SETTING, entry_id)

    assert entry.supported is False
    assert len(store.list(saved.SETTING)) == 2


def test_unsupported_entries_cannot_be_changed_but_can_be_deleted(
    store: saved.SavedStore, storage: FakeStorage
) -> None:
    entry_id = _from_a_newer_toolbox(store, storage)

    with pytest.raises(saved.StorageError, match="newer Toolbox"):
        store.update(saved.SETTING, entry_id, name="Renamed")

    assert store.delete(saved.SETTING, entry_id) is True
    assert [e.name for e in store.list(saved.SETTING)] == ["Mine"]


# Malformed data


@pytest.mark.parametrize("raw", ["{not json", '{"entries": []}', "null", '"text"'])
def test_unreadable_saved_data_reads_as_nothing_saved(
    store: saved.SavedStore, storage: FakeStorage, raw: str
) -> None:
    storage[store.key(saved.SEARCH)] = raw

    assert store.list(saved.SEARCH) == []
    # The page can still save; the unreadable value is replaced.
    entry = store.create(saved.SEARCH, "Fresh", "sparql", {})
    assert store.list(saved.SEARCH) == [entry]


@pytest.mark.parametrize(
    "bad",
    [
        "a string",
        {"id": "partial"},
        {"unexpected": "fields"},
        {
            "id": "",
            "kind": "search",
            "name": "Blank id",
            "operation": "sparql",
            "payload": {},
            "created": "2026-01-01",
            "modified": "2026-01-01",
            "user": "user-1",
            "schema_version": 1,
        },
        {
            "id": "p",
            "kind": "search",
            "name": "Bad payload",
            "operation": "sparql",
            "payload": "SELECT",
            "created": "2026-01-01",
            "modified": "2026-01-01",
            "user": "user-1",
            "schema_version": 1,
        },
    ],
)
def test_malformed_entries_are_skipped_but_kept(
    store: saved.SavedStore, storage: FakeStorage, bad: object
) -> None:
    good = store.create(saved.SEARCH, "Good", "sparql", {})
    key = store.key(saved.SEARCH)
    storage[key] = json.dumps([bad, good.to_json()])

    assert store.list(saved.SEARCH) == [good]

    store.create(saved.SEARCH, "Another", "sparql", {})
    store.delete(saved.SEARCH, good.id)

    # Writes put back what they couldn't read rather than dropping it.
    assert bad in json.loads(storage[key])


# Storage failures


def test_without_storage_nothing_is_saved_and_the_page_still_works() -> None:
    store = _store(None)

    assert store.available is False
    assert store.list(saved.SEARCH) == []
    assert store.get(saved.SEARCH, "id-1") is None
    with pytest.raises(saved.StorageError, match="isn't letting"):
        store.create(saved.SEARCH, "Nowhere", "sparql", {})


def test_blocked_storage_reads_as_nothing_saved(
    store: saved.SavedStore, storage: FakeStorage
) -> None:
    store.create(saved.SEARCH, "Saved", "sparql", {})
    storage.blocked = True

    assert store.list(saved.SEARCH) == []
    with pytest.raises(saved.StorageError):
        store.create(saved.SEARCH, "Blocked", "sparql", {})


def test_a_full_storage_keeps_what_was_already_saved(
    store: saved.SavedStore, storage: FakeStorage
) -> None:
    entry = store.create(saved.SEARCH, "Saved", "sparql", {"q": "x"})
    before = dict(storage)
    storage.full = True

    with pytest.raises(saved.StorageError, match="may be full") as error:
        store.create(saved.SEARCH, "One too many", "sparql", {})
    with pytest.raises(saved.StorageError):
        store.update(saved.SEARCH, entry.id, name="Renamed")
    with pytest.raises(saved.StorageError):
        store.delete(saved.SEARCH, entry.id)

    assert dict(storage) == before
    assert store.list(saved.SEARCH) == [entry]
    # The message is written for people, not a stack trace.
    assert "QuotaExceededError" not in str(error.value)


# Schema migration


@pytest.fixture
def version_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend the schema has moved to version 2, which adds payload["v2"]."""

    def upgrade(entry: dict) -> dict:
        return {**entry, "schema_version": 2, "payload": {**entry["payload"], "v2": 1}}

    monkeypatch.setattr(saved, "SCHEMA_VERSION", 2)
    monkeypatch.setattr(saved, "MIGRATIONS", {1: upgrade})


# An entry as version 1 of the Toolbox saved it.
OLD = {
    "id": "old",
    "kind": "search",
    "name": "Old",
    "operation": "sparql",
    "payload": {"q": "x"},
    "created": "2026-01-01T00:00:00+00:00",
    "modified": "2026-01-01T00:00:00+00:00",
    "user": "user-1",
    "schema_version": 1,
}


def _saved_by_version_1(storage: FakeStorage, *items: object) -> str:
    key = _store(storage).key(saved.SEARCH, 1)
    storage[key] = json.dumps(list(items))
    return key


@pytest.mark.usefixtures("version_2")
def test_older_entries_are_upgraded_when_read(storage: FakeStorage) -> None:
    old_key = _saved_by_version_1(storage, OLD)
    store = _store(storage)

    [entry] = store.list(saved.SEARCH)

    assert entry.id == "old"
    assert entry.schema_version == 2
    assert entry.payload == {"q": "x", "v2": 1}
    # Reading doesn't write: nothing under the new key yet.
    assert store.key(saved.SEARCH) not in storage
    assert storage[old_key] == json.dumps([OLD])


@pytest.mark.usefixtures("version_2")
def test_the_next_save_writes_upgraded_entries_and_leaves_the_old_key(
    storage: FakeStorage,
) -> None:
    old_key = _saved_by_version_1(storage, OLD)
    store = _store(storage)

    store.create(saved.SEARCH, "New", "sparql", {})

    new_key = store.key(saved.SEARCH)
    assert new_key == "bluecore:graph-toolbox:v2:user-1:searches"
    assert {e["name"] for e in json.loads(storage[new_key])} == {"Old", "New"}
    # Left for an older Toolbox still in use.
    assert storage[old_key] == json.dumps([OLD])


@pytest.mark.usefixtures("version_2")
def test_entries_that_cannot_be_upgraded_are_skipped(storage: FakeStorage) -> None:
    _saved_by_version_1(storage, {"no": "payload"}, OLD)

    assert [e.id for e in _store(storage).list(saved.SEARCH)] == ["old"]


# Opening the browser's storage


def test_open_store_uses_the_browsers_local_storage(
    storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = SimpleNamespace(localStorage=storage)
    monkeypatch.setitem(sys.modules, "pyscript", SimpleNamespace(window=window))

    store = saved.open_store("user-1")
    store.create(saved.SEARCH, "Pinned", "sparql", {})

    assert store.available is True
    assert store.key(saved.SEARCH) in storage


def test_open_store_copes_when_site_data_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BlockedWindow:
        @property
        def localStorage(self) -> FakeStorage:
            raise OSError("SecurityError")

    monkeypatch.setitem(
        sys.modules, "pyscript", SimpleNamespace(window=BlockedWindow())
    )

    store = saved.open_store("user-1")

    assert store.available is False
    assert store.list(saved.SEARCH) == []
