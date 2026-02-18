from app.config import AutomationConfig, ClassificationConfig
from app.integrations.email.classify import (
    _build_schema,
    _check_condition,
    _conditions_match,
    _eval_operator,
    _evaluate_automations,
)

# ---------------------------------------------------------------------------
# Shared classification configs
# ---------------------------------------------------------------------------

CONFIDENCE_CLS = ClassificationConfig(prompt="test confidence")
BOOLEAN_CLS = ClassificationConfig(prompt="test boolean", type="boolean")
ENUM_CLS = ClassificationConfig(
    prompt="test enum", type="enum", values=["low", "medium", "high", "critical"]
)

CLASSIFICATIONS = {
    "human": CONFIDENCE_CLS,
    "requires_response": BOOLEAN_CLS,
    "priority": ENUM_CLS,
}


# ---------------------------------------------------------------------------
# _eval_operator
# ---------------------------------------------------------------------------


class TestEvalOperator:
    def test_ge(self):
        assert _eval_operator(0.8, ">=0.8") is True
        assert _eval_operator(0.7, ">=0.8") is False

    def test_gt(self):
        assert _eval_operator(0.9, ">0.8") is True
        assert _eval_operator(0.8, ">0.8") is False

    def test_le(self):
        assert _eval_operator(0.5, "<=0.5") is True
        assert _eval_operator(0.6, "<=0.5") is False

    def test_lt(self):
        assert _eval_operator(0.4, "<0.5") is True
        assert _eval_operator(0.5, "<0.5") is False

    def test_eq(self):
        assert _eval_operator(1.0, "==1.0") is True
        assert _eval_operator(0.9, "==1.0") is False

    def test_whitespace_tolerance(self):
        assert _eval_operator(0.8, " >= 0.8 ") is True

    def test_invalid_operator_returns_false(self):
        assert _eval_operator(0.5, "!=0.5") is False

    def test_malformed_expression_returns_false(self):
        assert _eval_operator(0.5, "not a number") is False
        assert _eval_operator(0.5, "") is False


# ---------------------------------------------------------------------------
# _check_condition
# ---------------------------------------------------------------------------


class TestCheckCondition:
    # Boolean
    def test_boolean_true_match(self):
        assert _check_condition(True, True, BOOLEAN_CLS) is True

    def test_boolean_false_match(self):
        assert _check_condition(False, False, BOOLEAN_CLS) is True

    def test_boolean_mismatch(self):
        assert _check_condition(True, False, BOOLEAN_CLS) is False
        assert _check_condition(False, True, BOOLEAN_CLS) is False

    # Confidence with numeric threshold
    def test_confidence_meets_threshold(self):
        assert _check_condition(0.9, 0.8, CONFIDENCE_CLS) is True

    def test_confidence_below_threshold(self):
        assert _check_condition(0.7, 0.8, CONFIDENCE_CLS) is False

    def test_confidence_exact_threshold(self):
        assert _check_condition(0.8, 0.8, CONFIDENCE_CLS) is True

    # Confidence with string operator
    def test_confidence_string_operator(self):
        assert _check_condition(0.9, ">0.8", CONFIDENCE_CLS) is True
        assert _check_condition(0.8, ">0.8", CONFIDENCE_CLS) is False
        assert _check_condition(0.3, "<0.5", CONFIDENCE_CLS) is True

    # Confidence with unsupported condition type
    def test_confidence_unsupported_type_returns_false(self):
        assert _check_condition(0.9, [0.8], CONFIDENCE_CLS) is False

    # Enum exact match
    def test_enum_exact_match(self):
        assert _check_condition("high", "high", ENUM_CLS) is True

    def test_enum_mismatch(self):
        assert _check_condition("low", "high", ENUM_CLS) is False

    # Enum list (any-of)
    def test_enum_list_any_match(self):
        assert _check_condition("high", ["high", "critical"], ENUM_CLS) is True
        assert _check_condition("critical", ["high", "critical"], ENUM_CLS) is True

    def test_enum_list_no_match(self):
        assert _check_condition("low", ["high", "critical"], ENUM_CLS) is False


# ---------------------------------------------------------------------------
# _conditions_match
# ---------------------------------------------------------------------------


class TestConditionsMatch:
    def test_all_conditions_must_match(self):
        result = {"human": 0.9, "requires_response": True, "priority": "high"}
        when = {"human": 0.8, "requires_response": True}
        assert _conditions_match(when, result, CLASSIFICATIONS) is True

        when_fail = {"human": 0.8, "requires_response": False}
        assert _conditions_match(when_fail, result, CLASSIFICATIONS) is False

    def test_missing_classification_key_returns_false(self):
        result = {"human": 0.9}
        when = {"human": 0.8, "nonexistent_key": True}
        assert _conditions_match(when, result, CLASSIFICATIONS) is False

    def test_missing_result_key_returns_false(self):
        result = {}
        when = {"human": 0.8}
        assert _conditions_match(when, result, CLASSIFICATIONS) is False

    def test_empty_when_matches_everything(self):
        result = {"human": 0.5, "requires_response": False, "priority": "low"}
        assert _conditions_match({}, result, CLASSIFICATIONS) is True


# ---------------------------------------------------------------------------
# _evaluate_automations
# ---------------------------------------------------------------------------


class TestEvaluateAutomations:
    def test_matching_automation_returns_actions(self):
        automations = [
            AutomationConfig(when={"human": 0.8}, then=["archive"]),
        ]
        result = {"human": 0.9, "requires_response": False, "priority": "low"}
        actions = _evaluate_automations(automations, result, CLASSIFICATIONS)
        assert actions == ["archive"]

    def test_non_matching_automation_returns_empty(self):
        automations = [
            AutomationConfig(when={"human": 0.8}, then=["archive"]),
        ]
        result = {"human": 0.3, "requires_response": False, "priority": "low"}
        actions = _evaluate_automations(automations, result, CLASSIFICATIONS)
        assert actions == []

    def test_multiple_matching_automations_combine_actions(self):
        automations = [
            AutomationConfig(when={"human": 0.5}, then=["archive"]),
            AutomationConfig(
                when={"requires_response": True},
                then=[{"draft_reply": "noted"}],
            ),
        ]
        result = {"human": 0.9, "requires_response": True, "priority": "low"}
        actions = _evaluate_automations(automations, result, CLASSIFICATIONS)
        assert "archive" in actions
        assert {"draft_reply": "noted"} in actions

    def test_no_automations_returns_empty(self):
        result = {"human": 0.9, "requires_response": True, "priority": "high"}
        actions = _evaluate_automations([], result, CLASSIFICATIONS)
        assert actions == []


# ---------------------------------------------------------------------------
# _build_schema
# ---------------------------------------------------------------------------


class TestBuildSchema:
    def test_confidence_schema(self):
        cls = {"human": CONFIDENCE_CLS}
        schema = _build_schema(cls)
        assert schema["properties"]["human"] == {"type": "number"}
        assert "human" in schema["required"]

    def test_boolean_schema(self):
        cls = {"flag": BOOLEAN_CLS}
        schema = _build_schema(cls)
        assert schema["properties"]["flag"] == {"type": "boolean"}

    def test_enum_schema(self):
        cls = {"priority": ENUM_CLS}
        schema = _build_schema(cls)
        assert schema["properties"]["priority"] == {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        }

    def test_mixed_schema(self):
        schema = _build_schema(CLASSIFICATIONS)
        assert len(schema["properties"]) == 3
        assert len(schema["required"]) == 3
