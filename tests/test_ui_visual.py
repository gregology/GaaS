"""Targeted Playwright tests for interactive UI flows.

Tests the full browser stack (HTMX, Alpine.js, DaisyUI) for flows where
interactivity matters.  Focused on the config editor which writes to disk
— test rigor proportional to irreversibility.

Requires:
    playwright install chromium

Run only visual tests:
    pytest tests/test_ui_visual.py -m visual

Skip visual tests:
    pytest -m "not visual"

Note: These tests need network access to load CDN resources (DaisyUI,
HTMX, Alpine.js).  If CDN resources fail to load, interactive tests
will fail because Alpine.js / HTMX won't initialise.
"""

import pytest

pytestmark = pytest.mark.visual


# ---------------------------------------------------------------------------
# Smoke tests — pages render in a real browser
# ---------------------------------------------------------------------------


class TestPageLoads:
    """Verify each page renders with correct title and key elements."""

    def test_dashboard_title(self, page, live_server_url):
        page.goto(f"{live_server_url}/ui/")
        assert page.title() == "GaaS — Dashboard"

    def test_dashboard_nav_visible(self, page, live_server_url):
        page.goto(f"{live_server_url}/ui/")
        nav = page.locator(".navbar")
        assert nav.locator("a:text('Dashboard')").is_visible()
        assert nav.locator("a:text('Config')").is_visible()
        assert nav.locator("a:text('Queue')").is_visible()
        assert nav.locator("a:text('Logs')").is_visible()

    def test_dashboard_queue_stats(self, page, live_server_url):
        page.goto(f"{live_server_url}/ui/")
        assert page.locator(".stat-title:text('Pending')").is_visible()
        assert page.locator(".stat-title:text('Done')").is_visible()

    def test_config_title(self, page, live_server_url):
        page.goto(f"{live_server_url}/ui/config")
        assert page.title() == "GaaS — Config"

    def test_queue_title(self, page, live_server_url):
        page.goto(f"{live_server_url}/ui/queue")
        assert page.title() == "GaaS — Queue"

    def test_logs_title(self, page, live_server_url):
        page.goto(f"{live_server_url}/ui/logs")
        assert page.title() == "GaaS — Logs"


# ---------------------------------------------------------------------------
# Alpine.js — collapse / expand (DaisyUI collapse component)
# ---------------------------------------------------------------------------


class TestCollapseExpand:
    """DaisyUI collapse sections expand and contract on click."""

    def test_raw_yaml_editor_toggle(self, page, live_server_url):
        page.goto(f"{live_server_url}/ui/config")
        page.wait_for_load_state("networkidle")

        textarea = page.locator('textarea[name="yaml_content"]')
        # Initially collapsed — textarea hidden by DaisyUI
        assert not textarea.is_visible()

        # DaisyUI collapse uses a hidden checkbox that intercepts clicks
        # on the collapse-title. Click the checkbox directly to expand.
        yaml_collapse = page.locator('.collapse:has-text("Raw YAML Editor")')
        yaml_collapse.locator("input[type='checkbox']").check(force=True)
        textarea.wait_for(state="visible")
        assert textarea.is_visible()


# ---------------------------------------------------------------------------
# Alpine.js — edit form toggling (x-show / x-data)
# ---------------------------------------------------------------------------


class TestEditFormToggle:
    """Alpine.js x-show toggles for config edit forms."""

    def test_llm_edit_form_appears_on_click(self, page, live_server_url):
        """Clicking Edit shows the inline LLM profile edit form."""
        page.goto(f"{live_server_url}/ui/config")
        page.wait_for_load_state("networkidle")

        # Form row is hidden initially (x-cloak)
        edit_row = page.locator('tr[x-show*="editing"]').first
        assert not edit_row.is_visible()

        # Click Edit
        page.locator("#llm-section button:text('Edit')").first.click()
        edit_row.wait_for(state="visible")
        assert edit_row.is_visible()

        # Click Edit again to close
        page.locator("#llm-section button:text('Edit')").first.click()
        edit_row.wait_for(state="hidden")
        assert not edit_row.is_visible()

    def test_add_llm_form_appears_on_click(self, page, live_server_url):
        """Clicking '+ Add' shows the new-profile form."""
        page.goto(f"{live_server_url}/ui/config")
        page.wait_for_load_state("networkidle")

        name_input = page.locator('input[name="profile_name"]')
        assert not name_input.is_visible()

        page.locator("#llm-section button:text('+ Add')").click()
        name_input.wait_for(state="visible")
        assert name_input.is_visible()


# ---------------------------------------------------------------------------
# HTMX — form submission + partial swap
# ---------------------------------------------------------------------------


class TestHtmxPartialSwap:
    """HTMX form submissions swap section content without full page reload."""

    def test_llm_edit_swaps_section(self, page, live_server_url):
        """POST via HTMX replaces #llm-section innerHTML with the partial."""
        captured = []

        def mock_llm_post(route):
            captured.append(route.request.method)
            route.fulfill(
                content_type="text/html",
                body=(
                    '<div class="flex items-center gap-3 mb-4">'
                    '<h2 class="text-2xl font-bold">LLM Profiles</h2>'
                    "</div>"
                    '<p data-testid="swap-ok">Section updated via HTMX</p>'
                ),
            )

        page.route("**/ui/config/llms/**", mock_llm_post)
        page.goto(f"{live_server_url}/ui/config")
        page.wait_for_load_state("networkidle")

        # Open edit form for the "default" LLM profile
        page.locator("#llm-section button:text('Edit')").first.click()
        form = page.locator('form[hx-post="/ui/config/llms/default"]')
        form.wait_for(state="visible")

        # Fill model field and submit
        form.locator('input[name="model"]').fill("updated-model")
        form.locator('button[type="submit"]').click()

        # Verify HTMX made the request and swapped the content
        page.locator('[data-testid="swap-ok"]').wait_for(state="visible")
        assert len(captured) == 1
        assert captured[0] == "POST"


# ---------------------------------------------------------------------------
# Navigation — browser-level page transitions
# ---------------------------------------------------------------------------


class TestNavigation:
    """Click nav links and verify page transitions."""

    def test_dashboard_to_config(self, page, live_server_url):
        page.goto(f"{live_server_url}/ui/")
        page.locator(".navbar a:text('Config')").click()
        page.wait_for_url("**/ui/config")
        assert "Config" in page.title()

    def test_dashboard_to_queue(self, page, live_server_url):
        page.goto(f"{live_server_url}/ui/")
        page.locator(".navbar a:text('Queue')").click()
        page.wait_for_url("**/ui/queue")
        assert "Queue" in page.title()

    def test_dashboard_to_logs(self, page, live_server_url):
        page.goto(f"{live_server_url}/ui/")
        page.locator(".navbar a:text('Logs')").click()
        page.wait_for_url("**/ui/logs")
        assert "Logs" in page.title()
