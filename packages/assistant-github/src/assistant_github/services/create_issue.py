"""Service handler for creating GitHub issues."""

from __future__ import annotations

import logging
from typing import Any

from assistant_sdk import runtime
from assistant_sdk.task import TaskRecord

from assistant_github.client import GitHubClient

log = logging.getLogger(__name__)


def _get_field(entry: Any, key: str) -> str:
    """Read *key* from a dict or object, defaulting to empty string."""
    if isinstance(entry, dict):
        return str(entry.get(key, ""))
    return str(getattr(entry, key, ""))


def build_chat_context(instances: list[Any]) -> list[dict[str, str]]:
    """Build chat context entries from GitHub integration config instances.

    Extracts repos with non-empty context descriptions and returns them
    as generic {label, description} pairs for the chat system prompt.
    """
    entries: list[dict[str, str]] = []
    for instance in instances:
        for repo_entry in getattr(instance, "repos", None) or []:
            if isinstance(repo_entry, str):
                continue
            repo = _get_field(repo_entry, "repo")
            context = _get_field(repo_entry, "context")
            if repo and context:
                entries.append({"label": repo, "description": context})
    return entries


def handle(task: TaskRecord) -> dict[str, Any]:
    """Handle a service.github.create_issue queue task.

    Payload fields:
        integration: str — integration ID (e.g. "github.my_repos")
        inputs:
            repo: str   — repository in "org/repo" format
            title: str  — issue title
            body: str   — issue body (optional)
    """
    inputs = task["payload"].get("inputs", {})
    repo = inputs.get("repo", "")
    title = inputs.get("title", "")
    body = inputs.get("body", "")

    if not repo or not title:
        log.warning("create_issue: missing repo or title")
        return {"text": "Missing required fields: repo and title."}

    parts = repo.split("/", 1)
    if len(parts) != 2:
        return {"text": f"Invalid repo format: {repo}. Expected org/repo."}

    integration_id = task["payload"]["integration"]
    integration = runtime.get_integration(integration_id)
    org, repo_name = parts
    client = GitHubClient(
        app_id=integration.app_id,  # type: ignore[attr-defined]
        installation_id=integration.installation_id,  # type: ignore[attr-defined]
        private_key=integration.private_key,  # type: ignore[attr-defined]
        github_user=integration.github_user,  # type: ignore[attr-defined]
    )
    result = client.create_issue(org, repo_name, title, body)

    url = result.get("url", "")
    number = result.get("number", "")
    log.info("Created issue #%s in %s/%s", number, org, repo_name)

    return {
        "text": f"Issue #{number} created: {url}",
        "org": org,
        "repo": repo_name,
        "number": number,
        "url": url,
    }
