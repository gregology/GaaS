from app.integrations.email.mail import (
    _clean_header,
    _parse_auth_results,
    _parse_received_date,
    _parse_unsubscribe_url,
)


# ---------------------------------------------------------------------------
# _parse_auth_results
# ---------------------------------------------------------------------------


class TestParseAuthResults:
    def test_all_pass(self):
        headers = {
            "authentication-results": (
                "mx.example.com; spf=pass; dkim=pass; dmarc=pass",
            )
        }
        spf, dkim, dmarc = _parse_auth_results(headers)
        assert spf is True
        assert dkim is True
        assert dmarc is True

    def test_all_fail(self):
        headers = {
            "authentication-results": (
                "mx.example.com; spf=fail; dkim=fail; dmarc=fail",
            )
        }
        spf, dkim, dmarc = _parse_auth_results(headers)
        assert spf is False
        assert dkim is False
        assert dmarc is False

    def test_partial_pass(self):
        headers = {
            "authentication-results": (
                "mx.example.com; spf=pass; dkim=fail; dmarc=pass",
            )
        }
        spf, dkim, dmarc = _parse_auth_results(headers)
        assert spf is True
        assert dkim is False
        assert dmarc is True

    def test_empty_headers(self):
        spf, dkim, dmarc = _parse_auth_results({})
        assert spf is False
        assert dkim is False
        assert dmarc is False


# ---------------------------------------------------------------------------
# _parse_unsubscribe_url
# ---------------------------------------------------------------------------


class TestParseUnsubscribeUrl:
    def test_extracts_http_url(self):
        headers = {
            "list-unsubscribe": ("<https://example.com/unsubscribe?id=123>",)
        }
        url = _parse_unsubscribe_url(headers)
        assert url == "https://example.com/unsubscribe?id=123"

    def test_extracts_from_multiple_options(self):
        headers = {
            "list-unsubscribe": (
                "<mailto:unsub@example.com>, <https://example.com/unsub>",
            )
        }
        url = _parse_unsubscribe_url(headers)
        assert url == "https://example.com/unsub"

    def test_returns_none_when_missing(self):
        assert _parse_unsubscribe_url({}) is None

    def test_returns_none_when_no_http_url(self):
        headers = {"list-unsubscribe": ("<mailto:unsub@example.com>",)}
        assert _parse_unsubscribe_url(headers) is None


# ---------------------------------------------------------------------------
# _parse_received_date
# ---------------------------------------------------------------------------


class TestParseReceivedDate:
    def test_parses_valid_date(self):
        headers = {
            "received": (
                "from mail.example.com by mx.google.com; Tue, 15 Feb 2025 10:30:00 +0000",
            )
        }
        dt = _parse_received_date(headers)
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 2
        assert dt.day == 15

    def test_returns_none_when_missing(self):
        assert _parse_received_date({}) is None

    def test_returns_none_on_malformed(self):
        headers = {"received": ("completely garbage data without semicolon",)}
        # No semicolon means no date part to parse
        assert _parse_received_date(headers) is None


# ---------------------------------------------------------------------------
# _clean_header
# ---------------------------------------------------------------------------


class TestCleanHeader:
    def test_collapses_whitespace(self):
        assert _clean_header("  hello   world  ") == "hello world"

    def test_handles_newlines_and_tabs(self):
        assert _clean_header("hello\n\tworld") == "hello world"

    def test_empty_string(self):
        assert _clean_header("") == ""
