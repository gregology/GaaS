"""Typed protocols for GitHub integration config access.

These protocols restore type safety at the boundary between the SDK's
dynamic Pydantic models and integration handler code.  ``cast()`` to
these types is a no-op at runtime — the dynamic models already have the
right fields, this just tells mypy about them.

See DECISIONS.md → "Typed Protocols for integration config access".
"""

from __future__ import annotations

from typing import Protocol

from gaas_sdk.models import AutomationConfig, ClassificationConfig


class GitHubConfig(Protocol):
    """Config shape for a GitHub integration instance."""

    orgs: list[str]
    repos: list[str]
    name: str
    llm: str


class GitHubPlatformConfig(Protocol):
    """Platform config shape for pull_requests and issues platforms."""

    classifications: dict[str, ClassificationConfig]
    automations: list[AutomationConfig]
    include_mentions: bool | None
