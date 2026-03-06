"""Typed protocols for email integration config access.

These protocols restore type safety at the boundary between the SDK's
dynamic Pydantic models and integration handler code.  ``cast()`` to
these types is a no-op at runtime — the dynamic models already have the
right fields, this just tells mypy about them.

See DECISIONS.md → "Typed Protocols for integration config access".
"""

from __future__ import annotations

from typing import Protocol

from gaas_sdk.models import AutomationConfig, ClassificationConfig


class EmailConfig(Protocol):
    """Config shape for an email integration instance."""

    imap_server: str
    imap_port: int
    username: str
    password: str
    name: str
    llm: str


class InboxPlatformConfig(Protocol):
    """Platform config shape for the inbox platform."""

    classifications: dict[str, ClassificationConfig]
    automations: list[AutomationConfig]
    limit: int | None
    window: str | None
