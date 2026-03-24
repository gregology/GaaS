"""Tests for assistant_github.client — GitHub API client parsing and search logic.

Tests focus on deterministic parsing and search deduplication, not HTTP
calls (which require valid GitHub App credentials).
"""

from unittest.mock import MagicMock, patch

import jwt
import pytest

from assistant_github.client import GitHubClient, _parse_search_item


def _make_client(**overrides):
    """Create a GitHubClient with mocked auth so no real HTTP calls are made."""
    with (
        patch("assistant_github.client._generate_jwt", return_value="fake-jwt"),
        patch("assistant_github.client._fetch_installation_token", return_value="fake-token"),
    ):
        return GitHubClient(
            app_id=overrides.get("app_id", "123"),
            installation_id=overrides.get("installation_id", "456"),
            private_key=overrides.get("private_key", "fake-key"),
            github_user=overrides.get("github_user", "testuser"),
        )


# ---------------------------------------------------------------------------
# _parse_search_item
# ---------------------------------------------------------------------------


class TestParseSearchItem:
    def test_parses_org_and_repo(self):
        item = {
            "repository_url": "https://api.github.com/repos/myorg/myrepo",
            "number": 42,
            "title": "Fix bug",
            "user": {"login": "alice"},
        }
        result = _parse_search_item(item)
        assert result["org"] == "myorg"
        assert result["repo"] == "myrepo"
        assert result["number"] == 42
        assert result["title"] == "Fix bug"
        assert result["author"] == "alice"

    def test_trailing_slash_stripped(self):
        item = {
            "repository_url": "https://api.github.com/repos/org/repo/",
            "number": 1,
            "title": "T",
            "user": {"login": "bob"},
        }
        result = _parse_search_item(item)
        assert result["org"] == "org"
        assert result["repo"] == "repo"

    def test_missing_user_defaults_empty(self):
        item = {
            "repository_url": "https://api.github.com/repos/o/r",
            "number": 1,
            "title": "T",
        }
        result = _parse_search_item(item)
        assert result["author"] == ""

    def test_invalid_url_returns_empty(self):
        item = {
            "repository_url": "",
            "number": 1,
            "title": "T",
        }
        result = _parse_search_item(item)
        assert result == {}

    def test_single_segment_url_returns_empty(self):
        item = {
            "repository_url": "x",
            "number": 1,
            "title": "T",
        }
        result = _parse_search_item(item)
        assert result == {}


# ---------------------------------------------------------------------------
# GitHubClient.get_pr — status derivation
# ---------------------------------------------------------------------------


class TestGetPrStatus:
    def test_merged_pr(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {
                "merged": True,
                "state": "closed",
                "title": "Feature",
                "user": {"login": "alice"},
            }
            result = client.get_pr("org", "repo", 1)
            assert result["status"] == "merged"

    def test_closed_pr(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {
                "merged": False,
                "state": "closed",
                "title": "Old PR",
                "user": {"login": "bob"},
            }
            result = client.get_pr("org", "repo", 2)
            assert result["status"] == "closed"

    def test_open_pr(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {
                "merged": False,
                "state": "open",
                "title": "WIP",
                "user": {"login": "carol"},
            }
            result = client.get_pr("org", "repo", 3)
            assert result["status"] == "open"

    def test_missing_fields_default(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {}
            result = client.get_pr("org", "repo", 4)
            assert result["status"] == "open"
            assert result["title"] == ""
            assert result["author"] == ""


# ---------------------------------------------------------------------------
# GitHubClient.get_pr_detail
# ---------------------------------------------------------------------------


class TestGetPrDetail:
    def test_parses_fields(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {
                "title": "Add feature",
                "body": "Description here",
                "user": {"login": "alice"},
                "additions": 50,
                "deletions": 10,
                "changed_files": 3,
            }
            result = client.get_pr_detail("org", "repo", 1)
            assert result["title"] == "Add feature"
            assert result["body"] == "Description here"
            assert result["author"] == "alice"
            assert result["additions"] == 50
            assert result["deletions"] == 10
            assert result["changed_files"] == 3

    def test_null_body_becomes_empty_string(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {"body": None, "user": {"login": "x"}}
            result = client.get_pr_detail("org", "repo", 1)
            assert result["body"] == ""


# ---------------------------------------------------------------------------
# GitHubClient.get_pr_diff
# ---------------------------------------------------------------------------


class TestGetPrDiff:
    def test_returns_raw_text(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = "diff --git a/file.py b/file.py\n+new line"
            result = client.get_pr_diff("org", "repo", 1)
        assert result == "diff --git a/file.py b/file.py\n+new line"
        mock.assert_called_once_with(
            "GET",
            "/repos/org/repo/pulls/1",
            headers={"Accept": "application/vnd.github.v3.diff"},
            raw=True,
        )


# ---------------------------------------------------------------------------
# GitHubClient.get_issue
# ---------------------------------------------------------------------------


class TestGetIssue:
    def test_parses_fields(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {
                "title": "Bug report",
                "user": {"login": "alice"},
                "state": "open",
                "labels": [{"name": "bug"}, {"name": "urgent"}],
            }
            result = client.get_issue("org", "repo", 1)
            assert result["title"] == "Bug report"
            assert result["state"] == "open"
            assert result["labels"] == ["bug", "urgent"]

    def test_empty_labels(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {
                "title": "T",
                "user": {"login": "x"},
                "state": "open",
            }
            result = client.get_issue("org", "repo", 1)
            assert result["labels"] == []


# ---------------------------------------------------------------------------
# GitHubClient.get_issue_detail
# ---------------------------------------------------------------------------


class TestGetIssueDetail:
    def test_parses_fields(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {
                "title": "Bug report",
                "body": "Steps to repro",
                "user": {"login": "alice"},
                "state": "open",
                "labels": [{"name": "bug"}],
                "comments": 5,
            }
            result = client.get_issue_detail("org", "repo", 1)
            assert result["comment_count"] == 5
            assert result["labels"] == ["bug"]

    def test_null_body(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {"body": None, "user": {"login": "x"}}
            result = client.get_issue_detail("org", "repo", 1)
            assert result["body"] == ""


# ---------------------------------------------------------------------------
# GitHubClient.create_issue
# ---------------------------------------------------------------------------


class TestCreateIssue:
    def test_returns_number_and_url(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {
                "number": 42,
                "html_url": "https://github.com/org/repo/issues/42",
            }
            result = client.create_issue("org", "repo", "Bug title", "Bug body")
        assert result["number"] == 42
        assert result["url"] == "https://github.com/org/repo/issues/42"

    def test_sends_json_body(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {"number": 1, "html_url": ""}
            client.create_issue("myorg", "myrepo", "The title", "The body")
        mock.assert_called_once_with(
            "POST",
            "/repos/myorg/myrepo/issues",
            json={"title": "The title", "body": "The body"},
        )

    def test_empty_body(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {"number": 1, "html_url": ""}
            result = client.create_issue("org", "repo", "Title")
        assert result["number"] == 1
        mock.assert_called_once_with(
            "POST",
            "/repos/org/repo/issues",
            json={"title": "Title", "body": ""},
        )

    def test_missing_fields_default(self):
        client = _make_client()
        with patch.object(client, "_request") as mock:
            mock.return_value = {}
            result = client.create_issue("org", "repo", "T")
        assert result["number"] is None
        assert result["url"] == ""


# ---------------------------------------------------------------------------
# GitHubClient._scope_qualifiers
# ---------------------------------------------------------------------------


class TestScopeQualifiers:
    def test_orgs_only(self):
        client = _make_client()
        integration = MagicMock()
        integration.orgs = ["myorg", "otherorg"]
        integration.repos = None
        qualifiers = client._scope_qualifiers(integration)
        assert qualifiers == ["org:myorg", "org:otherorg"]

    def test_repos_only(self):
        client = _make_client()
        integration = MagicMock()
        integration.orgs = None
        integration.repos = ["myorg/myrepo"]
        qualifiers = client._scope_qualifiers(integration)
        assert qualifiers == ["repo:myorg/myrepo"]

    def test_both_orgs_and_repos(self):
        client = _make_client()
        integration = MagicMock()
        integration.orgs = ["myorg"]
        integration.repos = ["other/repo"]
        qualifiers = client._scope_qualifiers(integration)
        assert "org:myorg" in qualifiers
        assert "repo:other/repo" in qualifiers

    def test_no_scope_returns_empty_string(self):
        client = _make_client()
        integration = MagicMock()
        integration.orgs = None
        integration.repos = None
        qualifiers = client._scope_qualifiers(integration)
        assert qualifiers == [""]

    def test_empty_lists_returns_empty_string(self):
        client = _make_client()
        integration = MagicMock()
        integration.orgs = []
        integration.repos = []
        qualifiers = client._scope_qualifiers(integration)
        assert qualifiers == [""]


# ---------------------------------------------------------------------------
# GitHubClient._search_entities — deduplication
# ---------------------------------------------------------------------------


class TestSearchDeduplication:
    def test_deduplicates_by_org_repo_number(self):
        client = _make_client()
        integration = MagicMock()
        integration.orgs = None
        integration.repos = None

        # _search_raw returns parsed entity dicts (not raw API items)
        parsed_results = [
            {"org": "o", "repo": "r", "number": 1, "title": "T", "author": "a"},
        ]

        with patch.object(client, "_search_raw", return_value=parsed_results):
            results = client._search_entities(
                ["query1", "query2"],
                integration,
                item_filter=None,
            )
            # Should only appear once despite being returned from two queries
            assert len(results) == 1
            assert results[0]["number"] == 1

    def test_different_entities_not_deduped(self):
        client = _make_client()
        integration = MagicMock()
        integration.orgs = None
        integration.repos = None

        results_q1 = [
            {"org": "o", "repo": "r", "number": 1, "title": "PR1", "author": "a"},
        ]
        results_q2 = [
            {"org": "o", "repo": "r", "number": 2, "title": "PR2", "author": "b"},
        ]

        call_count = [0]

        def fake_search_raw(query, item_filter=None):
            call_count[0] += 1
            return results_q1 if call_count[0] == 1 else results_q2

        with patch.object(client, "_search_raw", side_effect=fake_search_raw):
            results = client._search_entities(
                ["query1", "query2"],
                integration,
                item_filter=None,
            )
            assert len(results) == 2


# ---------------------------------------------------------------------------
# github_user substitution in search queries
# ---------------------------------------------------------------------------


class TestGithubUserSubstitution:
    def test_active_prs_uses_github_user(self):
        client = _make_client(github_user="gregsterin")
        integration = MagicMock()
        integration.orgs = None
        integration.repos = None
        platform = MagicMock()
        platform.include_mentions = True

        with patch.object(client, "_search_entities") as mock:
            mock.return_value = []
            client.active_prs(integration, platform)

        queries = mock.call_args[0][0]
        for q in queries:
            assert "@me" not in q
            assert "gregsterin" in q
        assert any("mentions:gregsterin" in q for q in queries)

    def test_active_issues_uses_github_user(self):
        client = _make_client(github_user="gregsterin")
        integration = MagicMock()
        integration.orgs = None
        integration.repos = None
        platform = MagicMock()
        platform.include_mentions = True

        with patch.object(client, "_search_entities") as mock:
            mock.return_value = []
            client.active_issues(integration, platform)

        queries = mock.call_args[0][0]
        for q in queries:
            assert "@me" not in q
            assert "gregsterin" in q
        assert any("mentions:gregsterin" in q for q in queries)

    def test_active_prs_without_mentions(self):
        client = _make_client(github_user="someuser")
        integration = MagicMock()
        integration.orgs = None
        integration.repos = None
        platform = MagicMock()
        platform.include_mentions = False

        with patch.object(client, "_search_entities") as mock:
            mock.return_value = []
            client.active_prs(integration, platform)

        queries = mock.call_args[0][0]
        assert len(queries) == 3
        assert not any("mentions:" in q for q in queries)


# ---------------------------------------------------------------------------
# JWT generation
# ---------------------------------------------------------------------------


class TestGenerateJwt:
    def test_produces_valid_jwt(self):
        from assistant_github.client import _generate_jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        token = _generate_jwt("12345", pem)
        decoded = jwt.decode(token, private_key.public_key(), algorithms=["RS256"])
        assert decoded["iss"] == "12345"
        assert "iat" in decoded
        assert "exp" in decoded


# ---------------------------------------------------------------------------
# _request retry logic
# ---------------------------------------------------------------------------


class TestRequestRetry:
    def test_retries_on_failure_then_succeeds(self):
        client = _make_client()
        call_count = [0]

        def fake_request(method, url, **kwargs):
            call_count[0] += 1
            resp = MagicMock()
            if call_count[0] < 3:
                resp.is_success = False
                resp.status_code = 500
                resp.text = "server error"
            else:
                resp.is_success = True
                resp.json.return_value = {"ok": True}
            return resp

        with (
            patch.object(client._http, "request", side_effect=fake_request),
            patch("assistant_github.client.time.sleep"),
        ):
            result = client._request("GET", "/test")
        assert result == {"ok": True}
        assert call_count[0] == 3

    def test_raises_after_max_retries(self):
        client = _make_client()

        def always_fail(method, url, **kwargs):
            resp = MagicMock()
            resp.is_success = False
            resp.status_code = 502
            resp.text = "bad gateway"
            return resp

        with (
            patch.object(client._http, "request", side_effect=always_fail),
            patch("assistant_github.client.time.sleep"),
            pytest.raises(RuntimeError, match="GitHub API failed"),
        ):
            client._request("GET", "/test")
