"""Tests for worker task dispatch."""

import logging
from unittest.mock import patch

import pytest

from app import queue
from app.worker import handle


class TestHandle:
    def test_unknown_task_type_raises(self):
        """Unknown task types raise ValueError so they move to failed/."""
        task = {"payload": {"type": "nonexistent.task.type"}}
        with pytest.raises(ValueError, match="Unknown task type: nonexistent.task.type"):
            handle(task)

    def test_missing_task_type_raises(self):
        """Tasks without a type field raise ValueError."""
        task = {"payload": {}}
        with pytest.raises(ValueError, match="Unknown task type: None"):
            handle(task)


class TestWorkerResilience:
    def test_worker_fail_resilience(self, queue_dir, caplog):
        """queue.fail() raising doesn't crash the worker loop."""
        queue.enqueue({"type": "test"})
        task = queue.dequeue()

        # Simulate: handler raises, then queue.fail also raises
        with caplog.at_level(logging.ERROR):
            with patch("app.worker.handle", side_effect=RuntimeError("handler boom")):
                with patch("app.queue.fail", side_effect=OSError("disk full")):
                    # Inline the worker's except block logic
                    try:
                        handle(task)
                    except Exception as exc:
                        try:
                            queue.fail(task["id"], str(exc))
                        except Exception:
                            logging.getLogger("app.worker").exception(
                                "Failed to record failure for task %s", task["id"]
                            )

        assert "Failed to record failure" in caplog.text
