"""The options a MARC to BIBFRAME job runs with, and which ones go together.

``MarcJobSettings`` is what a user saves and restores through the browser's
LocalStorage adapter (``static/py/saved.py``, operation ``marc-to-bibframe``).
``MarcJobRequest`` adds what only a submission has: the upload, and the
duplicate policy the user confirmed. Settings restored from LocalStorage come
back through these models, so a saved entry is checked like any other input.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

# What the DAG does with a record that matches an entity already in Blue Core:
# - create_new: create a new entity anyway, with a new URI
# - export_only: don't change Blue Core; export the matched entity to the LSP
# - replace: replace the matched entity's data, keeping its URI
# - skip_report: leave it alone, and list it in the import report
# A record that matches more than one entity fails, whatever the policy.
DuplicatePolicy = Literal["create_new", "export_only", "replace", "skip_report"]


class MarcJobSettings(BaseModel):
    """A job's options, as saved in LocalStorage."""

    model_config = ConfigDict(extra="forbid", strict=True)

    duplicate_policy: DuplicatePolicy
    # Write a duplicate report beside the import report, which is always written.
    duplicate_report: bool
    export_to_lsp: bool
    # Convert and look up, but save nothing to Blue Core and export nothing.
    dry_run: bool

    @model_validator(mode="after")
    def options_go_together(self) -> Self:
        if self.duplicate_policy == "export_only" and not self.export_to_lsp:
            raise ValueError("duplicate_policy export_only needs export_to_lsp")
        return self


class MarcJobRequest(MarcJobSettings):
    """A job submission: settings, the upload, and the confirmed policy."""

    upload_id: str
    # The policy the user agreed to in the confirmation dialog. A submission
    # whose confirmation doesn't match what it asks for is refused.
    confirmed_policy: DuplicatePolicy

    @model_validator(mode="after")
    def policy_was_confirmed(self) -> Self:
        if self.confirmed_policy != self.duplicate_policy:
            raise ValueError("confirmed_policy does not match duplicate_policy")
        return self

    def settings(self) -> MarcJobSettings:
        return MarcJobSettings(
            **self.model_dump(include=set(MarcJobSettings.model_fields))
        )
