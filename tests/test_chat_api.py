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

    def test_send_confirm_executes_pending_action_without_llm(self, client, csrf_token):
        with patch("mac_agents_manager.app._get_chat_engine") as mock_engine, \
                patch("mac_agents_manager.app._get_chat_history") as mock_history, \
                patch("mac_agents_manager.app._execute_chat_action") as mock_exec:
            engine = MagicMock()
            engine.max_context = 20
            mock_engine.return_value = engine

            history = MagicMock()
            history.get_messages.return_value = [
                {
                    "role": "assistant",
                    "content": "Please confirm this change.",
                    "action": {
                        "action": "update_script",
                        "service_id": "agent:user.productivity.echo-hello",
                        "params": {"script_path": "/bin/echo Hello"},
                    },
                }
            ]
            mock_history.return_value = history

            mock_exec.return_value = {"success": True, "message": "Updated script"}

            resp = client.post(
                "/api/chat/send",
                json={"message": "confirm", "session_id": "chat_abc"},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["response"].startswith("Action completed:")
            mock_exec.assert_called_once()
            engine.send_message.assert_not_called()

    def test_send_confirm_without_pending_action_blocks_fake_completion(self, client, csrf_token):
        with patch("mac_agents_manager.app._get_chat_engine") as mock_engine, \
                patch("mac_agents_manager.app._get_chat_history") as mock_history:
            engine = MagicMock()
            engine.max_context = 20
            engine.send_message.return_value = {
                "response": "Action Completed: Updated script for user.productivity.echo-hello",
                "action": None,
                "requires_confirmation": False,
            }
            mock_engine.return_value = engine

            history = MagicMock()
            history.get_messages.return_value = []
            history.get_conversation_history.return_value = []
            mock_history.return_value = history

            resp = client.post(
                "/api/chat/send",
                json={"message": "confirme", "session_id": "chat_abc"},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "No pending action was found to confirm" in data["response"]

    def test_send_generates_session_id_when_missing(self, client, csrf_token):
        with patch("mac_agents_manager.app._get_chat_engine") as mock_engine, \
                patch("mac_agents_manager.app._get_chat_history") as mock_history:
            engine = MagicMock()
            engine.max_context = 20
            engine.send_message.return_value = {
                "response": "Hi there",
                "action": None,
                "requires_confirmation": False,
            }
            mock_engine.return_value = engine

            history = MagicMock()
            history.generate_session_id.return_value = "chat_generated"
            history.get_conversation_history.return_value = []
            mock_history.return_value = history

            resp = client.post(
                "/api/chat/send",
                json={"message": "hello"},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["session_id"] == "chat_generated"
            history.generate_session_id.assert_called_once()

    def test_send_strips_last_user_message_from_conversation(self, client, csrf_token):
        with patch("mac_agents_manager.app._get_chat_engine") as mock_engine, \
                patch("mac_agents_manager.app._get_chat_history") as mock_history:
            engine = MagicMock()
            engine.max_context = 20
            engine.send_message.return_value = {
                "response": "ok",
                "action": None,
                "requires_confirmation": False,
            }
            mock_engine.return_value = engine

            history = MagicMock()
            history.get_conversation_history.return_value = [
                {"role": "assistant", "content": "prev"},
                {"role": "user", "content": "latest user"},
            ]
            mock_history.return_value = history

            resp = client.post(
                "/api/chat/send",
                json={"message": "latest user", "session_id": "chat_abc"},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            sent_conversation = engine.send_message.call_args[0][1]
            assert sent_conversation == [{"role": "assistant", "content": "prev"}]

    def test_send_mutation_request_without_action_rewrites_fake_execution(self, client, csrf_token):
        with patch("mac_agents_manager.app._get_chat_engine") as mock_engine, \
                patch("mac_agents_manager.app._get_chat_history") as mock_history:
            engine = MagicMock()
            engine.max_context = 20
            engine.send_message.return_value = {
                "response": "Restarted user.productivity.echo-hello",
                "action": None,
                "requires_confirmation": False,
            }
            mock_engine.return_value = engine

            history = MagicMock()
            history.get_messages.return_value = []
            history.get_conversation_history.return_value = []
            mock_history.return_value = history

            resp = client.post(
                "/api/chat/send",
                json={"message": "restart my agent", "session_id": "chat_abc"},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "I couldn't execute that yet because no structured action was produced." in data["response"]

    def test_send_readonly_query_not_blocked_by_safety_guard(self, client, csrf_token):
        """Read-only queries containing mutation-like words must not be blocked."""
        with patch("mac_agents_manager.app._get_chat_engine") as mock_engine, \
                patch("mac_agents_manager.app._get_chat_history") as mock_history:
            engine = MagicMock()
            engine.max_context = 20
            engine.send_message.return_value = {
                "response": "This agent is currently running on port 8050. Schedule: daily at 10:00.",
                "action": None,
                "requires_confirmation": False,
            }
            mock_engine.return_value = engine

            history = MagicMock()
            history.get_messages.return_value = []
            history.get_conversation_history.return_value = []
            mock_history.return_value = history

            resp = client.post(
                "/api/chat/send",
                json={"message": "Summarize this service: show label, status, schedule, script, and recent logs.", "session_id": "chat_abc"},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "running on port 8050" in data["response"]
            assert "I couldn't execute" not in data["response"]

    def test_send_confirm_does_not_reexecute_already_completed_action(self, client, csrf_token):
        with patch("mac_agents_manager.app._get_chat_engine") as mock_engine, \
                patch("mac_agents_manager.app._get_chat_history") as mock_history, \
                patch("mac_agents_manager.app._execute_chat_action") as mock_exec:
            engine = MagicMock()
            engine.max_context = 20
            engine.send_message.return_value = {
                "response": "No pending updates to apply.",
                "action": None,
                "requires_confirmation": False,
            }
            mock_engine.return_value = engine

            history = MagicMock()
            history.get_messages.return_value = [
                {
                    "role": "assistant",
                    "content": "Action completed: Updated script",
                    "action": {
                        "action": "update_script",
                        "service_id": "agent:user.productivity.echo-hello",
                        "params": {"script_path": "/bin/echo Hello"},
                    },
                }
            ]
            history.get_conversation_history.return_value = []
            mock_history.return_value = history

            resp = client.post(
                "/api/chat/send",
                json={"message": "confirm", "session_id": "chat_abc"},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            mock_exec.assert_not_called()
            engine.send_message.assert_called_once()

    def test_send_confirm_does_not_reexecute_completed_variant_text(self, client, csrf_token):
        with patch("mac_agents_manager.app._get_chat_engine") as mock_engine, \
                patch("mac_agents_manager.app._get_chat_history") as mock_history, \
                patch("mac_agents_manager.app._execute_chat_action") as mock_exec:
            engine = MagicMock()
            engine.max_context = 20
            engine.send_message.return_value = {
                "response": "No pending action found.",
                "action": None,
                "requires_confirmation": False,
            }
            mock_engine.return_value = engine

            history = MagicMock()
            history.get_messages.return_value = [
                {
                    "role": "assistant",
                    "content": "Action completed successfully",
                    "action": {
                        "action": "update_script",
                        "service_id": "agent:user.productivity.echo-hello",
                        "params": {"script_path": "/bin/echo Hello"},
                    },
                }
            ]
            history.get_conversation_history.return_value = []
            mock_history.return_value = history

            resp = client.post(
                "/api/chat/send",
                json={"message": "confirm", "session_id": "chat_abc"},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            mock_exec.assert_not_called()
            engine.send_message.assert_called_once()


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

    def test_confirm_create_with_top_level_fields_uses_payload_params(self, client, csrf_token):
        with patch("mac_agents_manager.app._execute_create_action") as mock_create:
            mock_create.return_value = {"success": True, "message": "ok"}
            resp = client.post(
                "/api/chat/confirm",
                json={
                    "action": {
                        "action": "create",
                        "name": "echo-hello",
                        "category": "productivity",
                        "script_path": "/bin/echo",
                        "schedule_type": "scheduled",
                        "schedule_hour_0": 12,
                        "schedule_minute_0": 0,
                    }
                },
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            sent_params = mock_create.call_args[0][0]
            assert sent_params["name"] == "echo-hello"
            assert sent_params["category"] == "productivity"

    def test_confirm_update_accepts_label_without_service_id(self, client, csrf_token):
        with patch("mac_agents_manager.app._execute_update_action") as mock_update:
            mock_update.return_value = {"success": True, "message": "ok"}
            resp = client.post(
                "/api/chat/confirm",
                json={
                    "action": {
                        "action": "update_script",
                        "params": {
                            "label": "user.productivity.echo-hello",
                            "script_path": "/bin/echo Hello",
                        },
                    }
                },
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            sent_action, sent_service_id, sent_params = mock_update.call_args[0]
            assert sent_action == "update_script"
            assert sent_service_id == "agent:user.productivity.echo-hello"
            assert sent_params["script_path"] == "/bin/echo Hello"

    def test_confirm_update_normalizes_top_level_service_id_label(self, client, csrf_token):
        with patch("mac_agents_manager.app._execute_update_action") as mock_update:
            mock_update.return_value = {"success": True, "message": "ok"}
            resp = client.post(
                "/api/chat/confirm",
                json={
                    "action": {
                        "action": "update_script",
                        "service_id": "user.productivity.echo-hello",
                        "params": {"script_path": "/bin/echo Hello"},
                    }
                },
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            sent_action, sent_service_id, _sent_params = mock_update.call_args[0]
            assert sent_action == "update_script"
            assert sent_service_id == "agent:user.productivity.echo-hello"

    def test_confirm_update_accepts_top_level_label_with_params(self, client, csrf_token):
        with patch("mac_agents_manager.app._execute_update_action") as mock_update:
            mock_update.return_value = {"success": True, "message": "ok"}
            resp = client.post(
                "/api/chat/confirm",
                json={
                    "action": {
                        "action": "update_script",
                        "label": "user.productivity.echo-hello",
                        "params": {"script_path": "/bin/echo Hello"},
                    }
                },
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            sent_action, sent_service_id, sent_params = mock_update.call_args[0]
            assert sent_action == "update_script"
            assert sent_service_id == "agent:user.productivity.echo-hello"
            assert sent_params["script_path"] == "/bin/echo Hello"

    def test_confirm_create_accepts_agent_prefixed_label(self, client, csrf_token):
        with patch("mac_agents_manager.app._execute_create_action") as mock_create:
            mock_create.return_value = {"success": True, "message": "ok"}
            resp = client.post(
                "/api/chat/confirm",
                json={
                    "action": {
                        "action": "create",
                        "label": "agent:user.productivity.echo-hello",
                        "script_path": "/bin/echo",
                    }
                },
                headers={"X-CSRF-Token": csrf_token},
            )
            assert resp.status_code == 200
            sent_params = mock_create.call_args[0][0]
            assert sent_params["label"] == "agent:user.productivity.echo-hello"


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


class TestChatSessionsEndpoint:
    """Tests for /api/chat/sessions."""

    def test_sessions_returns_list(self, client):
        with patch("mac_agents_manager.app._get_chat_history") as mock_history:
            history = MagicMock()
            history.list_sessions.return_value = [
                {"session_id": "chat_abc", "message_count": 3},
            ]
            mock_history.return_value = history

            resp = client.get("/api/chat/sessions")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "sessions" in data
            assert len(data["sessions"]) == 1
            assert data["sessions"][0]["session_id"] == "chat_abc"


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
