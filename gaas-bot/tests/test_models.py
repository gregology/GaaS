"""Tests for structured output models."""

from gaas_bot.models.audit import AuditFinding, AuditReport
from gaas_bot.models.resolve import (
    CommentResult,
    EvalDecision,
    EvalResult,
    PRResult,
    TriageDecision,
    TriageResult,
)
from gaas_bot.models.review import (
    AnalysisResult,
    FindingSeverity,
    ReviewComment,
    ReviewFinding,
    ReviewResult,
)


# ---------------------------------------------------------------------------
# Resolve models
# ---------------------------------------------------------------------------

def test_triage_result_roundtrip():
    data = {"decision": "ask", "reasoning": "unclear", "detail": "need more info"}
    result = TriageResult.model_validate(data)
    assert result.decision == TriageDecision.ASK
    assert result.model_dump()["decision"] == "ask"


def test_eval_result_roundtrip():
    data = {"decision": "pass", "feedback": "looks good"}
    result = EvalResult.model_validate(data)
    assert result.decision == EvalDecision.PASS


def test_pr_result_roundtrip():
    data = {"pr_body": "body", "commit_message": "fix thing", "branch_name": "fix-thing"}
    result = PRResult.model_validate(data)
    assert result.branch_name == "fix-thing"


def test_comment_result():
    data = {"comment": "some markdown"}
    result = CommentResult.model_validate(data)
    assert result.comment == "some markdown"


# ---------------------------------------------------------------------------
# Audit models
# ---------------------------------------------------------------------------

def test_audit_finding_roundtrip():
    data = {
        "title": "Config docs list wrong default port",
        "body": "**File**: `CLAUDE.md`\n\n**What the docs say**: port 8080\n**What the code does**: port 6767",
        "labels": ["Docs"],
    }
    finding = AuditFinding.model_validate(data)
    assert finding.title == "Config docs list wrong default port"
    assert finding.labels == ["Docs"]


def test_audit_report_empty():
    report = AuditReport.model_validate({"findings": []})
    assert report.findings == []


def test_audit_report_multiple_findings():
    data = {
        "findings": [
            {"title": "Finding 1", "body": "Body 1", "labels": ["Docs"]},
            {"title": "Finding 2", "body": "Body 2", "labels": ["Tests", "Safety"]},
        ],
    }
    report = AuditReport.model_validate(data)
    assert len(report.findings) == 2
    assert report.findings[1].labels == ["Tests", "Safety"]


def test_audit_finding_preserves_markdown_body():
    body = "## Summary\n\nSome **bold** text.\n\n```python\nprint('hello')\n```"
    finding = AuditFinding.model_validate({"title": "t", "body": body, "labels": ["Tech debt"]})
    assert "```python" in finding.body


# ---------------------------------------------------------------------------
# Review models
# ---------------------------------------------------------------------------

def test_analysis_result_roundtrip():
    data = {
        "summary": "Adds a new endpoint",
        "risk_areas": ["auth bypass", "missing validation"],
        "affected_subsystems": ["api", "auth"],
    }
    result = AnalysisResult.model_validate(data)
    assert result.summary == "Adds a new endpoint"
    assert len(result.risk_areas) == 2
    assert result.affected_subsystems == ["api", "auth"]


def test_review_finding_roundtrip():
    data = {
        "severity": "critical",
        "category": "bug",
        "file": "app/main.py",
        "line": 42,
        "description": "Off-by-one error",
        "suggestion": "Use >= instead of >",
    }
    finding = ReviewFinding.model_validate(data)
    assert finding.severity == FindingSeverity.CRITICAL
    assert finding.model_dump()["severity"] == "critical"
    assert finding.line == 42


def test_review_finding_null_line():
    data = {
        "severity": "note",
        "category": "naming",
        "file": "app/config.py",
        "line": None,
        "description": "Confusing variable name",
        "suggestion": "Rename to something clearer",
    }
    finding = ReviewFinding.model_validate(data)
    assert finding.line is None


def test_review_result_empty():
    result = ReviewResult.model_validate({"findings": []})
    assert result.findings == []


def test_review_result_multiple_findings():
    data = {
        "findings": [
            {
                "severity": "critical",
                "category": "bug",
                "file": "a.py",
                "line": 1,
                "description": "d1",
                "suggestion": "s1",
            },
            {
                "severity": "warning",
                "category": "design",
                "file": "b.py",
                "line": None,
                "description": "d2",
                "suggestion": "s2",
            },
        ],
    }
    result = ReviewResult.model_validate(data)
    assert len(result.findings) == 2
    assert result.findings[0].severity == FindingSeverity.CRITICAL
    assert result.findings[1].severity == FindingSeverity.WARNING


def test_review_comment_roundtrip():
    data = {"body": "## Review\n\nLooks good overall."}
    result = ReviewComment.model_validate(data)
    assert "## Review" in result.body
