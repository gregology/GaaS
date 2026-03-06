"""HTML snapshot tests for all UI pages.

Uses syrupy to snapshot the full server-rendered HTML for each page.
Catches template regressions: broken Jinja2 logic, missing sections,
wrong attributes.  Does NOT test CSS, JavaScript, or interactive behavior
— see test_ui_visual.py for those.

First run / update baselines:
    pytest tests/test_ui_snapshots.py --snapshot-update
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# UI pages (HTML)
# ---------------------------------------------------------------------------


class TestDashboardSnapshot:
    def test_snapshot(self, snapshot):
        response = client.get("/ui/")
        assert response.status_code == 200
        assert response.text == snapshot


class TestConfigSnapshot:
    def test_snapshot(self, snapshot):
        response = client.get("/ui/config")
        assert response.status_code == 200
        assert response.text == snapshot


class TestQueueSnapshot:
    def test_snapshot(self, snapshot):
        response = client.get("/ui/queue")
        assert response.status_code == 200
        assert response.text == snapshot


class TestLogsSnapshot:
    def test_snapshot(self, snapshot):
        response = client.get("/ui/logs")
        assert response.status_code == 200
        assert response.text == snapshot


class TestLogDetailSnapshot:
    def test_missing_date(self, snapshot):
        response = client.get("/ui/logs/2099-01-01")
        assert response.status_code == 200
        assert response.text == snapshot


# ---------------------------------------------------------------------------
# JSON endpoints (structural regression baselines)
# ---------------------------------------------------------------------------


class TestRootSnapshot:
    def test_snapshot(self, snapshot):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == snapshot


class TestIntegrationsSnapshot:
    def test_snapshot(self, snapshot):
        response = client.get("/integrations")
        assert response.status_code == 200
        assert response.json() == snapshot
