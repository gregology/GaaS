"""Tests for the review command pipeline logic."""

from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from gaas_bot.commands.review import (
    STAGES,
    FIRST_STAGE,
    prepare_draft_ctx,
    post_review_comment,
)


# ---------------------------------------------------------------------------
# Pipeline structure
# ---------------------------------------------------------------------------

def test_stages_defined():
    assert "analyze" in STAGES
    assert "review_findings" in STAGES
    assert "draft" in STAGES


def test_first_stage():
    assert FIRST_STAGE == "analyze"


def test_stage_chain():
    ctx: dict = {}
    assert STAGES["analyze"].route(ctx) == "review_findings"
    assert STAGES["review_findings"].route(ctx) == "draft"
    assert STAGES["draft"].route(ctx) is None


def test_analyze_is_read_only():
    stage = STAGES["analyze"]
    assert "Write" not in stage.tools
    assert "Edit" not in stage.tools
    assert "Bash" not in stage.tools


def test_review_findings_is_read_only():
    stage = STAGES["review_findings"]
    assert "Write" not in stage.tools
    assert "Edit" not in stage.tools
    assert "Bash" not in stage.tools


def test_draft_has_no_tools():
    stage = STAGES["draft"]
    assert stage.tools == []


def test_session_continuity():
    assert STAGES["analyze"].session == "new"
    assert STAGES["review_findings"].session == "resume:analyze"
    assert STAGES["draft"].session == "resume:review_findings"


# ---------------------------------------------------------------------------
# prepare_draft_ctx
# ---------------------------------------------------------------------------

def test_prepare_draft_ctx_with_findings():
    ctx = {
        "review_findings": {
            "findings": [
                {"severity": "note", "category": "naming", "file": "a.py",
                 "line": 1, "description": "d", "suggestion": "s"},
            ],
        },
    }
    prepare_draft_ctx(ctx)
    assert len(ctx["findings"]) == 1
    assert ctx["findings"][0]["file"] == "a.py"


def test_prepare_draft_ctx_empty():
    ctx = {"review_findings": {"findings": []}}
    prepare_draft_ctx(ctx)
    assert ctx["findings"] == []


def test_prepare_draft_ctx_missing_review():
    ctx = {}
    prepare_draft_ctx(ctx)
    assert ctx["findings"] == []


# ---------------------------------------------------------------------------
# post_review_comment
# ---------------------------------------------------------------------------

def test_post_review_comment_dry_run():
    ctx = {
        "draft": {"body": "## Review\n\nLooks good."},
        "owner": "testowner",
        "repo": "testrepo",
        "pr_number": 42,
        "dry_run": True,
    }
    gh_ctx = MagicMock()

    @click.command()
    def cmd():
        from pathlib import Path
        post_review_comment("draft", ctx, gh_ctx, Path("/tmp"))

    runner = CliRunner()
    result = runner.invoke(cmd, [])
    assert "dry run" in result.output
    assert "## Review" in result.output


def test_post_review_comment_posts():
    ctx = {
        "draft": {"body": "Review body"},
        "owner": "testowner",
        "repo": "testrepo",
        "pr_number": 42,
        "dry_run": False,
    }
    mock_gh_ctx = MagicMock()

    with patch("gaas_bot.commands.review.post_comment", return_value="https://github.com/test/1") as mock_post:
        @click.command()
        def cmd():
            from pathlib import Path
            post_review_comment("draft", ctx, mock_gh_ctx, Path("/tmp"))

        runner = CliRunner()
        result = runner.invoke(cmd, [])

    mock_post.assert_called_once_with(
        mock_gh_ctx.gh, "testowner", "testrepo", 42, "Review body",
    )
    assert "Review comment posted" in result.output
