"""Config-driven queue policy enforcement: dedup + rate limiting.

Wraps queue.enqueue() with checks driven by config.yaml queue_policies.
Manual API triggers bypass this layer — only scheduled and automation-driven
enqueues go through policy_enqueue().
"""

from __future__ import annotations

import logging
import re

from app import queue
from app.config import config, TaskPolicyConfig

log = logging.getLogger(__name__)


def _parse_duration_seconds(duration: str) -> int:
    """Convert a duration string like '30m', '1h', '1d' to seconds."""
    match = re.fullmatch(r"(\d+)\s*([mhd])", duration.strip().lower())
    if not match:
        raise ValueError(f"Invalid duration format: {duration!r} (expected e.g. '30m', '1h', '1d')")

    value, unit = int(match.group(1)), match.group(2)

    if unit == "m":
        return value * 60
    if unit == "h":
        return value * 3600
    if unit == "d":
        return value * 86400

    raise ValueError(f"Unknown unit: {unit}")


def resolve_policy(task_type: str) -> TaskPolicyConfig:
    """Look up the effective policy for a task type (override or default)."""
    policies = config.queue_policies
    if task_type in policies.overrides:
        # Merge: override inherits defaults for fields not explicitly set
        override = policies.overrides[task_type]
        return TaskPolicyConfig(
            deduplicate_pending=(
                override.deduplicate_pending
                if override.deduplicate_pending != policies.defaults.deduplicate_pending
                else policies.defaults.deduplicate_pending
            ),
            rate_limit=override.rate_limit if override.rate_limit is not None else policies.defaults.rate_limit,
        )
    return policies.defaults


def policy_enqueue(
    payload: dict,
    priority: int = 5,
    provenance: str | None = None,
) -> str | None:
    """Enqueue with policy checks. Returns task_id or None if rejected."""
    fp = queue.fingerprint(payload)
    task_type = queue.task_type_from_payload(payload)
    policy = resolve_policy(task_type)

    # Dedup check
    if policy.deduplicate_pending:
        if queue.has_pending_duplicate(fp, task_type):
            log.info(
                "Dedup: skipping %s (fingerprint %s already pending)", task_type, fp,
            )
            return None

    # Rate limit check
    if policy.rate_limit is not None:
        seconds = _parse_duration_seconds(policy.rate_limit.per)
        recent = queue.count_recent(task_type, seconds)
        if recent >= policy.rate_limit.max:
            log.info(
                "Rate limit: skipping %s (%d/%d in last %s)",
                task_type, recent, policy.rate_limit.max, policy.rate_limit.per,
            )
            return None

    return queue.enqueue(payload, priority=priority, provenance=provenance)
