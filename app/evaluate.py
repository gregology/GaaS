"""Shared automation evaluation engine — re-exports from gaas_sdk."""

from gaas_sdk.evaluate import (  # noqa: F401
    MISSING,
    check_condition,
    check_deterministic_condition,
    conditions_match,
    eval_now_operator,
    eval_operator,
    evaluate_automations,
    resolve_action_provenance,
    unwrap_actions,
)
