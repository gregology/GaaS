"""Review a GitHub pull request using a multi-stage Claude agent pipeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import click
from pydantic import BaseModel

from gaas_bot.core import agent, git, templates
from gaas_bot.core.github import (
    GitHubContext,
    build_github_context,
    fetch_pull_request,
    fetch_pull_request_diff,
    post_comment,
)
from gaas_bot.models.review import (
    AnalysisResult,
    ReviewComment,
    ReviewResult,
)


# ---------------------------------------------------------------------------
# Stage definition (same pattern as resolve.py)
# ---------------------------------------------------------------------------

@dataclass
class Stage:
    template: str
    session: str  # "new" | "resume:<stage_name>"
    output: type[BaseModel] | None
    tools: list[str]
    max_turns: int
    route: Callable[[dict], str | None]
    post: Callable[[str, dict, GitHubContext, Path], None] | None = None


# ---------------------------------------------------------------------------
# Pre-processing: flatten findings for the draft template
# ---------------------------------------------------------------------------

def prepare_draft_ctx(ctx: dict) -> None:
    """Unpack review findings into a flat list for the draft template."""
    review = ctx.get("review_findings")
    if review:
        ctx["findings"] = review.get("findings", [])
    else:
        ctx["findings"] = []


# ---------------------------------------------------------------------------
# Post-hooks
# ---------------------------------------------------------------------------

def post_review_comment(
    stage_name: str, ctx: dict, gh_ctx: GitHubContext, worktree_dir: Path,
) -> None:
    """Post the formatted review comment on the PR."""
    body = ctx[stage_name]["body"]
    if ctx.get("dry_run"):
        click.echo("\n--- dry run: review comment ---\n")
        click.echo(body)
        return
    url = post_comment(gh_ctx.gh, ctx["owner"], ctx["repo"], ctx["pr_number"], body)
    click.echo(f"Review comment posted: {url}")


# ---------------------------------------------------------------------------
# Pipeline definition
# ---------------------------------------------------------------------------

STAGES: dict[str, Stage] = {
    "analyze": Stage(
        template="review_analyze.md.j2",
        session="new",
        output=AnalysisResult,
        tools=["Read", "Glob", "Grep"],
        max_turns=20,
        route=lambda ctx: "review_findings",
    ),
    "review_findings": Stage(
        template="review_review.md.j2",
        session="resume:analyze",
        output=ReviewResult,
        tools=["Read", "Glob", "Grep"],
        max_turns=20,
        route=lambda ctx: "draft",
    ),
    "draft": Stage(
        template="review_draft.md.j2",
        session="resume:review_findings",
        output=ReviewComment,
        tools=[],
        max_turns=10,
        route=lambda ctx: None,
        post=post_review_comment,
    ),
}

FIRST_STAGE = "analyze"


# ---------------------------------------------------------------------------
# Stage runner (mirrors resolve.py)
# ---------------------------------------------------------------------------

async def run_stage(
    name: str,
    stage: Stage,
    ctx: dict,
    worktree_dir: Path,
    sessions: dict[str, str],
) -> tuple[dict[str, Any] | None, str | None]:
    """Run a single pipeline stage."""
    prompt = templates.render(stage.template, ctx)

    resume_id = None
    if stage.session.startswith("resume:"):
        ref = stage.session.split(":", 1)[1]
        resume_id = sessions.get(ref)
        if not resume_id:
            click.echo(f"Warning: no session '{ref}' to resume, starting new session", err=True)

    click.echo(f"\n--- {name}: starting Claude agent ---\n")

    result, session_id = await agent.run_agent(
        prompt,
        cwd=worktree_dir,
        allowed_tools=stage.tools,
        max_turns=stage.max_turns,
        output_model=stage.output,
        resume=resume_id,
    )

    click.echo(f"\n--- {name}: complete ---")
    return result, session_id


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def run_pipeline(gh_ctx: GitHubContext, initial_ctx: dict, worktree_dir: Path) -> None:
    """Execute the review pipeline from analysis to comment."""
    ctx = dict(initial_ctx)
    sessions: dict[str, str] = {}
    current: str | None = FIRST_STAGE

    while current is not None:
        stage = STAGES[current]

        # Prepare template context for the draft stage
        if current == "draft":
            prepare_draft_ctx(ctx)

        result, session_id = asyncio.run(
            run_stage(current, stage, ctx, worktree_dir, sessions)
        )

        if session_id:
            sessions[current] = session_id
        if result is not None:
            ctx[current] = result if isinstance(result, dict) else result
            # Alias analysis result for template access
            if current == "analyze":
                ctx["analysis"] = result

        if stage.post is not None:
            stage.post(current, ctx, gh_ctx, worktree_dir)

        next_stage = stage.route(ctx)
        if next_stage is not None and next_stage not in STAGES:
            click.echo(f"Unknown stage '{next_stage}' returned by route, stopping.", err=True)
            break
        current = next_stage


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------

@click.command()
@click.option("--pull-request", required=True, type=int, help="Pull request number to review")
@click.option("--owner", default="gregology", help="Repository owner")
@click.option("--repo", default="GaaS", help="Repository name")
@click.option("--dry-run", is_flag=True, help="Print review comment instead of posting it")
def review(pull_request: int, owner: str, repo: str, dry_run: bool) -> None:
    """Review a GitHub pull request using Claude Code."""
    gh_ctx = build_github_context()

    click.echo(f"Fetching PR #{pull_request}...")
    pr_data = fetch_pull_request(gh_ctx.gh, owner, repo, pull_request)
    diff = fetch_pull_request_diff(gh_ctx.gh, owner, repo, pull_request)

    worktree_dir = git.create_worktree(detach=True)

    try:
        initial_ctx = {
            "owner": owner,
            "repo": repo,
            "pr_number": pull_request,
            "pr_title": pr_data["title"],
            "pr_body": pr_data["body"],
            "pr_author": pr_data["author"],
            "pr_base": pr_data["base"],
            "pr_head": pr_data["head"],
            "changed_files": pr_data["changed_files"],
            "diff": diff,
            "dry_run": dry_run,
        }
        run_pipeline(gh_ctx, initial_ctx, worktree_dir)
    finally:
        git.remove_worktree(worktree_dir)
