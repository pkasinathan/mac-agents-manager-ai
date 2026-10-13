"""Tests for ChatHistory persistence."""

import json
import os

import pytest

from mac_agents_manager.chat_history import ChatHistory


@pytest.fixture
def chat_dir(tmp_path):
    """Provide a temporary chat directory."""
    d = tmp_path / "chat"
    d.mkdir()
    return str(d)


@pytest.fixture
def history(chat_dir):
    """Create a ChatHistory instance with a temp directory."""
    return ChatHistory(chat_dir=chat_dir)


class TestSessionLifecycle:
    """Tests for session create, read, clear."""

    def test_create_session(self, history):
        session = history.create_session("test_session_001")
        assert session["session_id"] == "test_session_001"
        assert session["messages"] == []
        assert "created_at" in session

    def test_get_session(self, history):
        history.create_session("test_session_002")
        session = history.get_session("test_session_002")
        assert session is not None
        assert session["session_id"] == "test_session_002"

    def test_get_nonexistent_session(self, history):
        assert history.get_session("does_not_exist") is None

    def test_clear_session(self, history):
        history.create_session("test_session_003")
        assert history.clear_session("test_session_003") is True
        assert history.get_session("test_session_003") is None

    def test_clear_nonexistent_session(self, history):
        assert history.clear_session("does_not_exist") is True

    def test_generate_session_id(self):
        sid = ChatHistory.generate_session_id()
        assert sid.startswith("chat_")
        assert len(sid) > 20


class TestMessages:
    """Tests for message append and retrieval."""

    def test_append_and_get_messages(self, history):
        history.append_message("sess1", "user", "Hello")
        history.append_message("sess1", "assistant", "Hi there!")

        messages = history.get_messages("sess1")
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hi there!"

    def test_append_creates_session_if_missing(self, history):
        history.append_message("auto_session", "user", "First message")
        session = history.get_session("auto_session")
        assert session is not None
        assert len(session["messages"]) == 1

    def test_message_with_action(self, history):
        action = {"action": "start", "service_id": "agent:user.test.app", "params": {}}
        history.append_message("sess2", "assistant", "Starting service", action=action)

        messages = history.get_messages("sess2")
        assert messages[0]["action"] == action

    def test_message_with_service_id(self, history):
        history.append_message("sess3", "user", "Show info", service_id="agent:user.test.app")
        messages = history.get_messages("sess3")
        assert messages[0]["service_id"] == "agent:user.test.app"

    def test_max_messages_trimming(self, chat_dir):
        history = ChatHistory(chat_dir=chat_dir, max_messages=5)
        for i in range(10):
            history.append_message("trim_test", "user", f"Message {i}")

        messages = history.get_messages("trim_test")
        assert len(messages) == 5
        assert messages[0]["content"] == "Message 5"  # Oldest kept
        assert messages[-1]["content"] == "Message 9"  # Newest

    def test_get_messages_empty_session(self, history):
        assert history.get_messages("nonexistent") == []


class TestConversationHistory:
    """Tests for get_conversation_history() (Ollama-formatted)."""

    def test_returns_role_content_only(self, history):
        history.append_message("conv1", "user", "Hello")
        history.append_message("conv1", "assistant", "Hi!")

        conv = history.get_conversation_history("conv1")
        assert len(conv) == 2
        assert conv[0] == {"role": "user", "content": "Hello"}
        assert conv[1] == {"role": "assistant", "content": "Hi!"}

    def test_respects_max_messages(self, history):
        for i in range(30):
            role = "user" if i % 2 == 0 else "assistant"
            history.append_message("conv2", role, f"Message {i}")

        conv = history.get_conversation_history("conv2", max_messages=10)
        assert len(conv) == 10


class TestListSessions:
    """Tests for list_sessions()."""

    def test_list_empty(self, history):
        assert history.list_sessions() == []

    def test_list_sessions(self, history):
        history.create_session("chat_20250101_100000_a1b2")
        history.create_session("chat_20250102_100000_c3d4")

        sessions = history.list_sessions()
        assert len(sessions) == 2
        assert sessions[0]["session_id"] == "chat_20250102_100000_c3d4"  # Most recent first


class TestSecurity:
    """Tests for path traversal prevention."""

    def test_path_traversal_rejected(self, history):
        with pytest.raises(ValueError):
            history._session_path("../../../etc/passwd")

    def test_special_chars_rejected(self, history):
        with pytest.raises(ValueError):
            history._session_path("session;rm -rf /")

    def test_valid_session_id_accepted(self, history):
        path = history._session_path("chat_20250101_100000_a1b2")
        assert "chat_20250101_100000_a1b2.json" in str(path)

    def test_file_permissions(self, history):
        history.create_session("perm_test")
        path = history._session_path("perm_test")
        mode = oct(os.stat(str(path)).st_mode)[-3:]
        assert mode == "600"


class TestCleanup:
    """Tests for cleanup_old_sessions()."""

    def test_cleanup_removes_old(self, chat_dir):
        history = ChatHistory(chat_dir=chat_dir, retention_days=0)
        history.create_session("chat_20200101_100000_old1")

        # Set mtime to the past
        path = history._session_path("chat_20200101_100000_old1")
        os.utime(str(path), (0, 0))

        removed = history.cleanup_old_sessions()
        assert removed == 1
        assert history.get_session("chat_20200101_100000_old1") is None

    def test_cleanup_keeps_recent(self, chat_dir):
        history = ChatHistory(chat_dir=chat_dir, retention_days=30)
        history.create_session("chat_20250101_100000_new1")

        removed = history.cleanup_old_sessions()
        assert removed == 0
        assert history.get_session("chat_20250101_100000_new1") is not None
