from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
import jwt

log = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 1  # seconds; sleeps 1, 2, 4 on retries

GITHUB_API_BASE = "https://api.github.com"


def _parse_search_item(item: dict[str, Any]) -> dict[str, Any]:
    """Parse an item from the GitHub search/issues endpoint into a standard dict."""
    repo_url = item.get("repository_url", "")
    segments = repo_url.rstrip("/").split("/")
    if len(segments) < 2:
        return {}
    return {
        "org": segments[-2],
        "repo": segments[-1],
        "number": item["number"],
        "title": item["title"],
        "author": item.get("user", {}).get("login", ""),
    }


def _generate_jwt(app_id: str, private_key: str) -> str:
    """Create a short-lived JWT for GitHub App authentication."""
    now = int(time.time())
    payload = {
        "iss": app_id,
        "iat": now - 60,
        "exp": now + 600,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def _fetch_installation_token(
    installation_id: str, app_jwt: str
) -> str:
    """Exchange a GitHub App JWT for an installation access token."""
    resp = httpx.post(
        f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["token"]


class GitHubClient:
    def __init__(
        self,
        app_id: str,
        installation_id: str,
        private_key: str,
        github_user: str,
    ) -> None:
        self._github_user = github_user
        app_jwt = _generate_jwt(app_id, private_key)
        token = _fetch_installation_token(installation_id, app_jwt)
        self._http = httpx.Client(
            base_url=GITHUB_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    def get_pr(self, org: str, repo: str, number: int) -> dict[str, Any]:
        result = self._request("GET", f"/repos/{org}/{repo}/pulls/{number}")
        merged = result.get("merged", False)
        state = result.get("state", "unknown")
        if merged:
            status = "merged"
        elif state == "closed":
            status = "closed"
        else:
            status = "open"
        return {
            "org": org,
            "repo": repo,
            "number": number,
            "title": result.get("title", ""),
            "author": result.get("user", {}).get("login", ""),
            "status": status,
        }

    def get_pr_detail(self, org: str, repo: str, number: int) -> dict[str, Any]:
        result = self._request("GET", f"/repos/{org}/{repo}/pulls/{number}")
        return {
            "title": result.get("title", ""),
            "body": result.get("body", "") or "",
            "author": result.get("user", {}).get("login", ""),
            "additions": result.get("additions", 0),
            "deletions": result.get("deletions", 0),
            "changed_files": result.get("changed_files", 0),
        }

    def get_pr_diff(self, org: str, repo: str, number: int) -> str:
        return self._request(
            "GET",
            f"/repos/{org}/{repo}/pulls/{number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
            raw=True,
        )

    def active_prs(self, integration: Any, platform: Any) -> list[dict[str, Any]]:
        """Fetch all open PRs currently requiring the user's attention."""
        user = self._github_user
        base_queries = [
            f"is:pr is:open assignee:{user}",
            f"is:pr is:open review-requested:{user}",
            f"is:pr is:open author:{user} draft:false",
        ]
        if getattr(platform, "include_mentions", False):
            base_queries.append(f"is:pr is:open mentions:{user}")

        results = self._search_entities(
            base_queries,
            integration,
            item_filter=None,
        )
        log.info("active_prs: found %d unique PRs across all queries", len(results))
        return results

    def get_issue(self, org: str, repo: str, number: int) -> dict[str, Any]:
        result = self._request("GET", f"/repos/{org}/{repo}/issues/{number}")
        return {
            "org": org,
            "repo": repo,
            "number": number,
            "title": result.get("title", ""),
            "author": result.get("user", {}).get("login", ""),
            "state": result.get("state", "unknown"),
            "labels": [label.get("name", "") for label in result.get("labels", [])],
        }

    def get_issue_detail(self, org: str, repo: str, number: int) -> dict[str, Any]:
        result = self._request("GET", f"/repos/{org}/{repo}/issues/{number}")
        return {
            "title": result.get("title", ""),
            "body": result.get("body", "") or "",
            "author": result.get("user", {}).get("login", ""),
            "state": result.get("state", "unknown"),
            "labels": [label.get("name", "") for label in result.get("labels", [])],
            "comment_count": result.get("comments", 0),
        }

    def active_issues(self, integration: Any, platform: Any) -> list[dict[str, Any]]:
        """Fetch all open issues currently requiring the user's attention."""
        user = self._github_user
        base_queries = [
            f"is:issue is:open assignee:{user}",
            f"is:issue is:open author:{user}",
        ]
        if getattr(platform, "include_mentions", False):
            base_queries.append(f"is:issue is:open mentions:{user}")

        results = self._search_entities(
            base_queries,
            integration,
            item_filter=lambda item: "pull_request" not in item,
        )
        log.info("active_issues: found %d unique issues across all queries", len(results))
        return results

    def _search_entities(
        self,
        base_queries: list[str],
        integration: Any,
        item_filter: Callable[[dict[str, Any]], bool] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute search queries and return deduplicated entity dicts.

        item_filter, when provided, is applied to each raw search result item
        before parsing (e.g., to exclude PRs from issue searches).
        """
        seen: set[tuple[str, str, int]] = set()
        results: list[dict[str, Any]] = []

        scopes = self._scope_qualifiers(integration)
        for base_query in base_queries:
            for scope in scopes:
                query = f"{base_query} {scope}".strip()
                for item in self._search_raw(query, item_filter):
                    key = (item["org"], item["repo"], item["number"])
                    if key not in seen:
                        seen.add(key)
                        results.append(item)
        return results

    def _search_raw(
        self,
        query: str,
        item_filter: Callable[[dict[str, Any]], bool] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a GitHub search/issues query and return parsed entity dicts."""
        result = self._request(
            "GET",
            "/search/issues",
            params={"q": query, "per_page": "100"},
        )
        entities = []
        for item in result.get("items", []):
            if item_filter is not None and not item_filter(item):
                continue
            parsed = _parse_search_item(item)
            if not parsed:
                log.warning(
                    "Cannot parse org/repo from repository_url: %s",
                    item.get("repository_url", ""),
                )
                continue
            entities.append(parsed)
        log.info("_search_raw(%r): found %d results", query, len(entities))
        return entities

    def create_issue(
        self,
        org: str,
        repo: str,
        title: str,
        body: str = "",
    ) -> dict[str, Any]:
        """Create an issue in a GitHub repository. Returns {number, url}."""
        result = self._request(
            "POST",
            f"/repos/{org}/{repo}/issues",
            json={"title": title, "body": body},
        )
        return {
            "number": result.get("number"),
            "url": result.get("html_url", ""),
        }

    def _scope_qualifiers(self, integration: Any) -> list[str]:
        """Build scope qualifiers from the integration's org/repo config."""
        qualifiers = []
        for org in integration.orgs or []:
            qualifiers.append(f"org:{org}")
        for repo in integration.repos or []:
            qualifiers.append(f"repo:{repo}")
        return qualifiers or [""]

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        raw: bool = False,
    ) -> Any:
        """Make an HTTP request with retry and exponential backoff."""
        last_err: RuntimeError | None = None
        for attempt in range(MAX_RETRIES + 1):
            log.info("github api: %s %s", method, url)
            resp = self._http.request(
                method,
                url,
                params=params,
                json=json,
                headers=headers,
            )
            if resp.is_success:
                return resp.text if raw else resp.json()
            last_err = RuntimeError(
                f"GitHub API failed (HTTP {resp.status_code}): {resp.text[:500]}"
            )
            if attempt < MAX_RETRIES:
                delay = BACKOFF_BASE * (2**attempt)
                log.warning(
                    "GitHub API failed (attempt %d/%d), retrying in %ds: HTTP %d",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    delay,
                    resp.status_code,
                )
                time.sleep(delay)
            else:
                log.error("GitHub API failed: HTTP %d %s", resp.status_code, resp.text[:500])
        assert last_err is not None
        raise last_err
