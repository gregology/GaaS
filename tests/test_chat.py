"""Tests for ChatService and chat_message_handler."""

from unittest.mock import patch, MagicMock

import pytest

from app.chat import ChatService, ChatMessage, chat_message_handler


class TestChatServiceCreateConversation:
    def test_returns_uuid_string(self):
        svc = ChatService()
        cid = svc.create_conversation()
        assert isinstance(cid, str)
        assert len(cid) == 36  # UUID format

    def test_initializes_empty_history(self):
        svc = ChatService()
        cid = svc.create_conversation()
        assert svc.get_history(cid) == []


class TestChatServiceGetHistory:
    def test_returns_messages_in_order(self):
        svc = ChatService()
        cid = svc.create_conversation()
        with patch("app.chat.queue") as mock_queue:
            mock_queue.enqueue.return_value = "task-1"
            svc.handle_message(cid, "hello")
            svc.handle_message(cid, "world")
        history = svc.get_history(cid)
        assert len(history) == 2
        assert history[0].content == "hello"
        assert history[1].content == "world"

    def test_unknown_conversation_raises_keyerror(self):
        svc = ChatService()
        with pytest.raises(KeyError):
            svc.get_history("nonexistent")


class TestChatServiceHandleMessage:
    def test_chat_message_stores_user_message_and_enqueues(self, queue_dir):
        svc = ChatService()
        cid = svc.create_conversation()
        with patch("app.chat.queue") as mock_queue:
            mock_queue.enqueue.return_value = "task-123"
            result = svc.handle_message(cid, "Hello LLM")

        assert result["type"] == "chat"
        assert result["task_id"] == "task-123"

        # Verify enqueue was called with priority 1
        mock_queue.enqueue.assert_called_once()
        call_args = mock_queue.enqueue.call_args
        payload = call_args[0][0]
        assert payload["type"] == "chat.message"
        assert payload["conversation_id"] == cid
        assert payload["llm_profile"] == "default"
        assert call_args[1]["priority"] == 1

        # User message stored in history
        history = svc.get_history(cid)
        assert len(history) == 1
        assert history[0].role == "user"
        assert history[0].content == "Hello LLM"
        assert history[0].type == "chat"

    def test_clear_command_returns_command_response(self):
        svc = ChatService()
        cid = svc.create_conversation()
        with patch("app.chat.queue") as mock_queue:
            mock_queue.enqueue.return_value = "task-1"
            svc.handle_message(cid, "Hello")
            result = svc.handle_message(cid, "/clear")

        assert result["type"] == "command"
        assert isinstance(result["message"], ChatMessage)
        assert result["message"].content == "Conversation cleared."
        assert result["message"].type == "command"

        # History should be cleared
        assert svc.get_history(cid) == []

        # No additional enqueue for the command
        assert mock_queue.enqueue.call_count == 1  # only the "Hello" message

    def test_unknown_command_returns_system_message(self):
        svc = ChatService()
        cid = svc.create_conversation()
        with patch("app.chat.queue"):
            result = svc.handle_message(cid, "/foo")

        assert result["type"] == "command"
        assert "Unknown command" in result["message"].content
        assert "/clear" in result["message"].content
        assert result["message"].type == "command"

    def test_command_parsing_is_case_sensitive(self):
        svc = ChatService()
        cid = svc.create_conversation()
        with patch("app.chat.queue"):
            result = svc.handle_message(cid, "/CLEAR")
        assert result["type"] == "command"
        assert "Unknown command" in result["message"].content

    def test_unknown_conversation_raises_keyerror(self):
        svc = ChatService()
        with pytest.raises(KeyError):
            svc.handle_message("nonexistent", "hello")

    def test_task_payload_structure(self):
        svc = ChatService()
        cid = svc.create_conversation()
        with patch("app.chat.queue") as mock_queue, \
             patch("app.chat.config") as mock_config:
            mock_config.chat.llm = "default"
            mock_config.chat.system_prompt = "Be helpful."
            mock_queue.enqueue.return_value = "task-1"
            svc.handle_message(cid, "Hello")

        payload = mock_queue.enqueue.call_args[0][0]
        assert payload["type"] == "chat.message"
        assert payload["conversation_id"] == cid
        assert payload["llm_profile"] == "default"
        assert isinstance(payload["messages"], list)
        assert payload["on_result"] == [
            {"type": "chat_reply", "conversation_id": cid},
        ]


class TestChatServiceReceiveReply:
    def test_adds_assistant_message_to_history(self):
        svc = ChatService()
        cid = svc.create_conversation()
        msg = svc.receive_reply(cid, "Hello from LLM")
        assert msg.role == "assistant"
        assert msg.content == "Hello from LLM"
        assert msg.type == "chat"
        history = svc.get_history(cid)
        assert len(history) == 1
        assert history[0].content == "Hello from LLM"


class TestBuildLLMMessages:
    def test_includes_system_prompt_and_chat_messages(self):
        svc = ChatService()
        cid = svc.create_conversation()
        with patch("app.chat.config") as mock_config, \
             patch("app.chat.queue") as mock_queue:
            mock_config.chat.system_prompt = "Be helpful."
            mock_config.chat.llm = "default"
            mock_queue.enqueue.return_value = "task-1"
            svc.handle_message(cid, "Hello")

        # Check the messages in the enqueued payload
        payload = mock_queue.enqueue.call_args[0][0]
        messages = payload["messages"]
        assert messages[0] == {"role": "system", "content": "Be helpful."}
        assert messages[1] == {"role": "user", "content": "Hello"}

    def test_excludes_commands_from_llm_messages(self):
        svc = ChatService()
        cid = svc.create_conversation()
        with patch("app.chat.config") as mock_config, \
             patch("app.chat.queue") as mock_queue:
            mock_config.chat.system_prompt = None
            mock_config.chat.llm = "default"
            mock_queue.enqueue.return_value = "task-1"
            svc.handle_message(cid, "Hello")
            svc.handle_message(cid, "/foo")  # unknown command, stored in history
            svc.handle_message(cid, "World")

        # Third call to enqueue (for "World")
        payload = mock_queue.enqueue.call_args[0][0]
        messages = payload["messages"]
        # Should have Hello and World, not the /foo command
        assert len(messages) == 2
        assert messages[0]["content"] == "Hello"
        assert messages[1]["content"] == "World"

    def test_no_system_prompt(self):
        svc = ChatService()
        cid = svc.create_conversation()
        with patch("app.chat.config") as mock_config, \
             patch("app.chat.queue") as mock_queue:
            mock_config.chat.system_prompt = None
            mock_config.chat.llm = "default"
            mock_queue.enqueue.return_value = "task-1"
            svc.handle_message(cid, "Hello")

        payload = mock_queue.enqueue.call_args[0][0]
        messages = payload["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"


class TestMultipleConversations:
    def test_conversations_are_independent(self):
        svc = ChatService()
        cid1 = svc.create_conversation()
        cid2 = svc.create_conversation()
        with patch("app.chat.queue") as mock_queue:
            mock_queue.enqueue.return_value = "task-1"
            svc.handle_message(cid1, "Hello from 1")
            svc.handle_message(cid2, "Hello from 2")

        assert len(svc.get_history(cid1)) == 1
        assert len(svc.get_history(cid2)) == 1
        assert svc.get_history(cid1)[0].content == "Hello from 1"
        assert svc.get_history(cid2)[0].content == "Hello from 2"


class TestChatMessageHandler:
    def test_calls_backend_and_returns_content(self):
        mock_response = MagicMock()
        mock_response.content = "LLM says hello"

        task = {
            "id": "1_20260319T100000Z_abc123--def456--chat.message",
            "payload": {
                "type": "chat.message",
                "conversation_id": "conv-1",
                "llm_profile": "default",
                "messages": [
                    {"role": "user", "content": "Hello"},
                ],
            },
        }

        with patch("app.chat.ChatCompletionsBackend") as MockBackend:
            MockBackend.return_value.chat.return_value = mock_response
            result = chat_message_handler(task)

        assert result == {"content": "LLM says hello", "conversation_id": "conv-1"}
        MockBackend.return_value.chat.assert_called_once()

    def test_propagates_llm_errors(self):
        task = {
            "id": "1_20260319T100000Z_abc123--def456--chat.message",
            "payload": {
                "type": "chat.message",
                "conversation_id": "conv-1",
                "llm_profile": "default",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        }

        with patch("app.chat.ChatCompletionsBackend") as MockBackend:
            MockBackend.return_value.chat.side_effect = ConnectionError("refused")
            with pytest.raises(ConnectionError):
                chat_message_handler(task)
