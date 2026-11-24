"""Tests for MARC to BIBFRAME job options."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bluecore_graph_toolbox.marc_bibframe_operations.options import (
    MarcJobRequest,
    MarcJobSettings,
)

SETTINGS = {
    "duplicate_policy": "skip_report",
    "duplicate_report": True,
    "export_to_lsp": False,
    "dry_run": True,
}
REQUEST = {**SETTINGS, "upload_id": "0" * 32, "confirmed_policy": "skip_report"}


@pytest.mark.parametrize(
    "policy", ["create_new", "export_only", "replace", "skip_report"]
)
def test_each_policy_is_accepted(policy: str) -> None:
    job = MarcJobRequest(
        **{
            **REQUEST,
            "duplicate_policy": policy,
            "confirmed_policy": policy,
            "export_to_lsp": True,
        }
    )

    assert job.duplicate_policy == policy


def test_unknown_policies_are_refused() -> None:
    with pytest.raises(ValidationError):
        MarcJobSettings(**{**SETTINGS, "duplicate_policy": "merge"})


def test_export_only_needs_export_to_lsp() -> None:
    with pytest.raises(ValidationError, match="export_to_lsp"):
        MarcJobSettings(
            **{**SETTINGS, "duplicate_policy": "export_only", "export_to_lsp": False}
        )


def test_the_confirmed_policy_must_be_the_one_asked_for() -> None:
    with pytest.raises(ValidationError, match="confirmed_policy"):
        MarcJobRequest(**{**REQUEST, "confirmed_policy": "replace"})


@pytest.mark.parametrize("missing", sorted(SETTINGS))
def test_every_setting_must_be_given(missing: str) -> None:
    settings = {k: v for k, v in SETTINGS.items() if k != missing}

    with pytest.raises(ValidationError):
        MarcJobSettings(**settings)


def test_unknown_fields_are_refused() -> None:
    # A saved entry from a newer Toolbox, or a typo, mustn't be ignored silently.
    with pytest.raises(ValidationError):
        MarcJobSettings(**SETTINGS, ingest=True)


def test_options_are_not_coerced_from_strings() -> None:
    with pytest.raises(ValidationError):
        MarcJobSettings(**{**SETTINGS, "dry_run": "true"})


def test_settings_are_the_request_without_upload_or_confirmation() -> None:
    assert MarcJobRequest(**REQUEST).settings() == MarcJobSettings(**SETTINGS)
