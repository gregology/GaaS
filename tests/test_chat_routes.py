"""Tests for chat API endpoints."""

from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient

from app.main import app
from app.chat import chat_service

client = TestClient(app)


class TestCreateConversation:
    def test_returns_conversation_id(self):
        resp = client.post("/api/chat/conversations")
        assert resp.status_code == 200
        data = resp.json()
        assert "conversation_id" in data
        assert len(data["conversation_id"]) == 36


class TestGetHistory:
    def test_returns_message_list(self):
        cid = chat_service.create_conversation()
        resp = client.get(f"/api/chat/conversations/{cid}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == cid
        assert data["messages"] == []

    def test_404_for_unknown_conversation(self):
        resp = client.get("/api/chat/conversations/nonexistent/history")
        assert resp.status_code == 404


class TestSendMessage:
    def test_chat_message_returns_task_id(self, queue_dir):
        cid = chat_service.create_conversation()
        with patch("app.chat.queue") as mock_queue:
            mock_queue.enqueue.return_value = "task-abc"
            resp = client.post(
                f"/api/chat/conversations/{cid}/messages",
                json={"content": "Hello"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "chat"
        assert data["task_id"] == "task-abc"

    def test_clear_command_returns_immediately(self):
        cid = chat_service.create_conversation()
        resp = client.post(
            f"/api/chat/conversations/{cid}/messages",
            json={"content": "/clear"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "command"
        assert data["message"]["content"] == "Conversation cleared."
        assert data["message"]["type"] == "command"

    def test_404_for_unknown_conversation(self):
        resp = client.post(
            "/api/chat/conversations/nonexistent/messages",
            json={"content": "Hello"},
        )
        assert resp.status_code == 404


class TestPollTask:
    def test_pending_status(self, queue_dir):
        task_id = "1_20260319T100000Z_abc123--def456--chat.message"
        pending_path = queue_dir / "pending" / f"{task_id}.yaml"
        pending_path.write_text(yaml.dump({"id": task_id, "status": "pending", "payload": {}}))

        resp = client.get(f"/api/chat/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json() == {"status": "pending"}

    def test_done_status(self, queue_dir):
        task_id = "1_20260319T100000Z_abc123--def456--chat.message"
        cid = chat_service.create_conversation()
        done_path = queue_dir / "done" / f"{task_id}.yaml"
        task_data = {
            "id": task_id,
            "status": "done",
            "result": {"content": "LLM response", "conversation_id": cid},
            "payload": {"type": "chat.message", "conversation_id": cid},
        }
        done_path.write_text(yaml.dump(task_data))

        resp = client.get(f"/api/chat/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "done"
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == "LLM response"
        assert data["message"]["type"] == "chat"

    def test_failed_status(self, queue_dir):
        task_id = "1_20260319T100000Z_abc123--def456--chat.message"
        cid = chat_service.create_conversation()
        failed_path = queue_dir / "failed" / f"{task_id}.yaml"
        task_data = {
            "id": task_id,
            "status": "failed",
            "error": "Connection refused",
            "payload": {"type": "chat.message", "conversation_id": cid},
        }
        failed_path.write_text(yaml.dump(task_data))

        resp = client.get(f"/api/chat/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["message"]["role"] == "system"
        assert "Connection refused" in data["message"]["content"]
        assert data["message"]["type"] == "system"

    def test_404_for_unknown_task(self, queue_dir):
        resp = client.get("/api/chat/tasks/nonexistent")
        assert resp.status_code == 404


class TestChatConfig:
    def test_chat_config_defaults(self):
        from app.config import ChatConfig
        cfg = ChatConfig()
        assert cfg.llm == "default"
        assert cfg.system_prompt is None

    def test_app_config_has_chat(self):
        from app.config import config
        assert hasattr(config, "chat")
        assert config.chat.llm == "default"


class TestChatReplyResultRoute:
    def test_chat_reply_handled_without_error(self):
        from app.result_routes import route_results
        result = {"content": "Hello from LLM", "conversation_id": "conv-1"}
        task = {
            "id": "1_20260319T100000Z_abc123--def456--chat.message",
            "payload": {
                "type": "chat.message",
                "on_result": [
                    {"type": "chat_reply", "conversation_id": "conv-1"},
                ],
            },
        }
        # Should not raise
        route_results(result, task)

    def test_chat_reply_logs_human_entry(self):
        from app.result_routes import route_results
        result = {"content": "Hello from LLM", "conversation_id": "conv-1"}
        task = {
            "id": "1_20260319T100000Z_abc123--def456--chat.message",
            "payload": {
                "type": "chat.message",
                "on_result": [
                    {"type": "chat_reply", "conversation_id": "conv-1"},
                ],
            },
        }
        with patch("app.result_routes.log") as mock_log:
            route_results(result, task)
        mock_log.human.assert_called_once()
        call_args = mock_log.human.call_args[0]
        assert "Chat reply" in call_args[0]
