import socket
import threading
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure a minimal config.yaml exists before any app modules are imported.
# config.py loads eagerly at import time, so this must happen at module level.
# config.yaml is gitignored so this won't affect the repo.
# ---------------------------------------------------------------------------

_project_root = Path(__file__).parent.parent
_config_path = _project_root / "config.yaml"

if not _config_path.exists():
    _config_path.write_text(
        "llms:\n"
        "  default:\n"
        "    model: test-model\n"
    )

from app import queue
from app.runtime_init import register_runtime

register_runtime()


@pytest.fixture
def queue_dir(tmp_path, monkeypatch):
    """Isolated queue directory with all subdirectories created."""
    for d in queue.DIRS:
        (tmp_path / d).mkdir()
    monkeypatch.setattr(queue, "BASE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def notes_dir(tmp_path):
    """Isolated directory for NoteStore operations."""
    return tmp_path


# ---------------------------------------------------------------------------
# Auto-skip visual (Playwright) tests when playwright is not installed
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items):
    try:
        import playwright  # noqa: F401
    except ImportError:
        skip = pytest.mark.skip(
            reason="playwright not installed (pip install pytest-playwright && playwright install chromium)"
        )
        for item in items:
            if "visual" in item.keywords:
                item.add_marker(skip)


# ---------------------------------------------------------------------------
# Live server fixture for Playwright tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def live_server_url():
    """Start the FastAPI app on a random port for browser-based tests."""
    import uvicorn

    from app.main import app

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    server_config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(server_config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
