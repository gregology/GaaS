from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestDashboard:
    def test_returns_html(self):
        response = client.get("/ui/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_contains_gaas(self):
        response = client.get("/ui/")
        assert "GaaS" in response.text


class TestConfigPage:
    def test_returns_html(self):
        response = client.get("/ui/config")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_shows_llm_profiles(self):
        response = client.get("/ui/config")
        assert "default" in response.text

    def test_shows_directories(self):
        response = client.get("/ui/config")
        assert "Directories" in response.text


class TestQueuePage:
    def test_returns_html(self):
        response = client.get("/ui/queue")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_shows_queue_dirs(self):
        response = client.get("/ui/queue")
        assert "pending" in response.text
        assert "done" in response.text


class TestLogsPage:
    def test_returns_html(self):
        response = client.get("/ui/logs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_log_detail_missing_date(self):
        response = client.get("/ui/logs/2099-01-01 Monday")
        assert response.status_code == 200
        assert "No log content found" in response.text


class TestSecretMasking:
    def test_no_secrets_in_config_page(self):
        from app.config import SECRETS_PATH

        if SECRETS_PATH.exists():
            import yaml

            raw = yaml.safe_load(SECRETS_PATH.read_text()) or {}
            secret_values = [str(v) for v in raw.values() if v is not None]
        else:
            secret_values = []

        if secret_values:
            response = client.get("/ui/config")
            for secret in secret_values:
                assert secret not in response.text, (
                    f"Secret value leaked in config page"
                )


class TestExistingEndpoints:
    def test_root_still_works(self):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_integrations_still_works(self):
        response = client.get("/integrations")
        assert response.status_code == 200
