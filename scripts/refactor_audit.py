#!/usr/bin/env python3
"""Standalone refactoring audit script.

Runs code quality tools, then passes their output plus a refactor prompt
to a Claude agent that explores the codebase and writes refactoring
opportunity files to to_review/.

Operates in a temporary git worktree checked out from origin/main so it
can run independently of whatever branch you're working on.

Requirements:
    claude-agent-sdk

Usage:
    uv run python scripts/refactor_audit.py
"""

import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parent.parent

QUALITY_TOOLS = [
    {
        "name": "mypy",
        "cmd": ["uv", "run", "mypy", "app/", "packages/", "--ignore-missing-imports"],
    },
    {
        "name": "complexipy",
        "cmd": ["uv", "run", "complexipy", "app/", "packages/", "--max-complexity", "15"],
    },
    {
        "name": "radon",
        "cmd": ["uv", "run", "radon", "cc", "app/", "-a", "-nc"],
    },
    {
        "name": "vulture",
        "cmd": ["uv", "run", "vulture", "app/", "packages/", "--min-confidence", "80"],
    },
    {
        "name": "ruff",
        "cmd": ["uv", "run", "ruff", "check", "app/", "packages/", "tests/"],
    },
    {
        "name": "bandit",
        "cmd": ["uv", "run", "bandit", "-r", "app/", "-q"],
    },
]


def create_worktree() -> Path:
    """Create a temporary git worktree from origin/main."""
    subprocess.run(
        ["git", "fetch", "origin", "main"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    worktree_dir = Path(tempfile.mkdtemp(prefix="gaas-audit-"))
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree_dir), "origin/main"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    print(f"Created worktree at {worktree_dir}")
    return worktree_dir


def remove_worktree(worktree_dir: Path) -> None:
    """Remove the temporary worktree and its directory."""
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    if worktree_dir.exists():
        shutil.rmtree(worktree_dir)


def run_quality_tools(worktree_dir: Path) -> str:
    """Run each quality tool via subprocess, collect stdout+stderr."""
    sections = []
    for tool in QUALITY_TOOLS:
        name = tool["name"]
        print(f"Running {name}...")
        result = subprocess.run(
            tool["cmd"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (result.stdout + result.stderr).strip()
        sections.append(f"## {name}\n\n```\n{output}\n```")
    return "\n\n".join(sections)


def build_prompt(worktree_dir: Path, tool_output: str) -> str:
    """Combine the refactor prompt template with tool output."""
    env = Environment(
        loader=FileSystemLoader([worktree_dir / "scripts", worktree_dir]),
        keep_trailing_newline=True,
    )
    template = env.get_template("refactor_audit_prompt.md.j2")
    return template.render(tool_output=tool_output)


async def run_agent(prompt: str, worktree_dir: Path) -> None:
    """Run a Claude agent with the given prompt."""
    try:
        from claude_agent_sdk import (  # noqa: E501
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            ToolUseBlock,
            query,
        )
    except ImportError:
        print(
            "claude-agent-sdk is not installed.\n"
            "Install it with: pip install claude-agent-sdk",
            file=sys.stderr,
        )
        sys.exit(1)

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep", "Write"],
        permission_mode="bypassPermissions",
        cwd=str(worktree_dir),
        max_turns=30,
        setting_sources=["project"],
    )

    print("\nStarting Claude agent...\n")
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"  [{block.name}] {_summarize_tool_input(block.input)}")


def _summarize_tool_input(input_data: dict) -> str:
    """One-line summary of a tool call's input."""
    if "file_path" in input_data:
        return input_data["file_path"]
    if "pattern" in input_data:
        return input_data["pattern"]
    if "command" in input_data:
        cmd = input_data["command"]
        return cmd[:80] + "..." if len(cmd) > 80 else cmd
    return str(input_data)[:80]


def copy_results(worktree_dir: Path) -> None:
    """Copy to_review/ from the worktree back to the real repo."""
    src = worktree_dir / "to_review"
    if not src.exists():
        print("\nWarning: agent did not create to_review/ in the worktree.", file=sys.stderr)
        return
    dest = REPO_ROOT / "to_review"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    files = sorted(dest.glob("*.md"))
    print(f"\nDone. {len(files)} file(s) copied to to_review/:")
    for f in files:
        print(f"  {f.name}")


def main() -> None:
    worktree_dir = create_worktree()
    try:
        (worktree_dir / "to_review").mkdir(exist_ok=True)
        tool_output = run_quality_tools(worktree_dir)
        prompt = build_prompt(worktree_dir, tool_output)
        asyncio.run(run_agent(prompt, worktree_dir))
        copy_results(worktree_dir)
    finally:
        remove_worktree(worktree_dir)
        print("Worktree cleaned up.")


if __name__ == "__main__":
    main()
