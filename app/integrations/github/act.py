"""Stub for github.act — Phase 4 will implement PR actions.

This handler logs what actions would be taken without executing them.
The SIMPLE_ACTIONS allowlist and reversibility tiers will be defined
here in Phase 4 alongside the actual action implementations.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def handle(task: dict):
    org = task["payload"]["org"]
    repo = task["payload"]["repo"]
    number = task["payload"]["number"]
    actions = task["payload"].get("actions", [])
    provenance = task.get("provenance", "unknown")

    log.info(
        "github.act: %s/%s#%d — actions=%s provenance=%s (not yet implemented)",
        org, repo, number, actions, provenance,
    )
