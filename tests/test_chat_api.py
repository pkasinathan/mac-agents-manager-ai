"""Tests for the AI Chat Flask API routes."""

from unittest.mock import MagicMock, patch


class TestChatHealthEndpoint:
    """Tests for /api/chat/health."""

    def test_health_returns_json(self, client):
        with patch("mac_agents_manager.app._get_chat_engine") as mock_engine:
            engine = MagicMock()
            engine.health_check.return_value = {
                "ollama_running": False,
                "model_available": False,
                "model_name": "qwen3.5:4b",
                "base_url": "http://localhost:11434",
            }
            mock_engine.return_value = engine

            resp = client.get("/api/chat/health")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "ollama_running" in data
            assert "model_name" in data


class TestChatSendEndpoint:
    """Tests for /api/chat/send."""

    def test_send_without_csrf_returns_403(self, client):
        resp = client.post("/api/chat/send", json={"message": "hello"})
        assert resp.status_code == 403

    def test_send_empty_message_returns_400(self, client, csrf_token):
        resp = client.post(
            "/api/chat/send",
            json={"message": ""},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 400

    def test_send_no_json_returns_400(self, client, csrf_token):
        resp = client.post(
            "/api/chat/send",
            data="not json",
            content_type="text/plain",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 400


class TestChatConfirmEndpoint:
    """Tests for /api/chat/confirm."""

    def test_confirm_without_csrf_returns_403(self, client):
        resp = client.post("/api/chat/confirm", json={"action": {}})
        assert resp.status_code == 403

    def test_confirm_no_action_returns_400(self, client, csrf_token):
        resp = client.post(
            "/api/chat/confirm",
            json={"session_id": "test"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 400


class TestChatHistoryEndpoint:
    """Tests for /api/chat/history."""

    def test_history_no_session_returns_400(self, client):
        resp = client.get("/api/chat/history")
        assert resp.status_code == 400

    def test_history_with_session(self, client):
        resp = client.get("/api/chat/history?session_id=test_session")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "messages" in data


class TestChatClearEndpoint:
    """Tests for /api/chat/clear."""

    def test_clear_without_csrf_returns_403(self, client):
        resp = client.post("/api/chat/clear", json={"session_id": "test"})
        assert resp.status_code == 403

    def test_clear_no_session_returns_400(self, client, csrf_token):
        resp = client.post(
            "/api/chat/clear",
            json={},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 400

    def test_clear_with_session(self, client, csrf_token):
        resp = client.post(
            "/api/chat/clear",
            json={"session_id": "test_session"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
