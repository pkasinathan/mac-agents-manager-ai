"""Tests for the Flask application routes and security."""



from unittest.mock import patch

from mac_agents_manager.app import (
    _execute_chat_action,
    _execute_rename_action,
    _find_pending_action,
    _resolve_action_service_id,
)
from mac_agents_manager.models import LaunchService


class TestChatActionHelpers:
    def test_find_pending_action_skips_already_completed_action_messages(self):
        messages = [
            {
                "role": "assistant",
                "content": "Action completed: Updated script",
                "action": {"action": "update_script", "service_id": "agent:user.test.app"},
            }
        ]
        assert _find_pending_action(messages) is None

    def test_find_pending_action_returns_latest_unresolved_action(self):
        older_action = {"action": "update_script", "service_id": "agent:user.test.older"}
        latest_action = {"action": "restart", "service_id": "agent:user.test.latest"}
        messages = [
            {"role": "assistant", "content": "Please confirm first change", "action": older_action},
            {"role": "assistant", "content": "Action completed: Updated first change", "action": older_action},
            {"role": "assistant", "content": "Please confirm restart", "action": latest_action},
        ]
        assert _find_pending_action(messages) == latest_action

    def test_find_pending_action_skips_completed_without_colon_variant(self):
        messages = [
            {
                "role": "assistant",
                "content": "Action completed successfully",
                "action": {"action": "restart", "service_id": "agent:user.test.app"},
            }
        ]
        assert _find_pending_action(messages) is None

    def test_find_pending_action_skips_us_spelling_canceled(self):
        messages = [
            {
                "role": "assistant",
                "content": "Action canceled by user",
                "action": {"action": "delete", "service_id": "agent:user.test.app"},
            }
        ]
        assert _find_pending_action(messages) is None

    def test_resolve_action_service_id_accepts_top_level_label_alias(self):
        action_data = {"action": "update_script", "label": "user.productivity.echo-hello"}
        assert _resolve_action_service_id(action_data, {}) == "agent:user.productivity.echo-hello"

    def test_resolve_action_service_id_prefers_explicit_service_id(self):
        action_data = {
            "action": "update_script",
            "service_id": "agent:user.productivity.echo-hello",
            "label": "user.productivity.other",
        }
        assert _resolve_action_service_id(action_data, {}) == "agent:user.productivity.echo-hello"

    def test_find_pending_action_ignores_non_assistant_and_non_dict_actions(self):
        pending = {"action": "restart", "service_id": "agent:user.test.pending"}
        messages = [
            {"role": "user", "content": "confirm", "action": pending},
            {"role": "assistant", "content": "noop", "action": "invalid"},
            {"role": "assistant", "content": "please confirm", "action": pending},
        ]
        assert _find_pending_action(messages) == pending

    def test_find_pending_action_marks_action_resolved_by_later_status(self):
        action = {"action": "restart", "service_id": "agent:user.test.pending"}
        messages = [
            {"role": "assistant", "content": "please confirm", "action": action},
            {"role": "assistant", "content": "Action failed due to timeout", "action": action},
        ]
        assert _find_pending_action(messages) is None

    def test_find_pending_action_covers_non_assistant_and_invalid_action_entries(self):
        # Covers skip branches for non-assistant and non-dict action messages.
        messages = [
            {"role": "user", "content": "confirm?"},
            {"role": "assistant", "content": "status update", "action": "not-a-dict"},
        ]
        assert _find_pending_action(messages) is None

    def test_find_pending_action_inner_loop_skips_non_assistant_messages(self):
        pending = {"action": "restart", "service_id": "agent:user.test.pending"}
        messages = [
            {"role": "assistant", "content": "please confirm restart", "action": pending},
            {"role": "user", "content": "thinking"},
        ]
        assert _find_pending_action(messages) == pending

    def test_resolve_action_service_id_accepts_params_service_aliases(self):
        action_data = {"action": "restart"}
        params = {"service": "user.productivity.echo-hello"}
        assert _resolve_action_service_id(action_data, params) == "agent:user.productivity.echo-hello"

    def test_find_pending_action_does_not_resolve_other_actions(self):
        action_a = {
            "action": "update_script",
            "service_id": "agent:user.productivity.service-a",
            "params": {"script_path": "/bin/echo A"},
        }
        action_b = {
            "action": "update_script",
            "service_id": "agent:user.productivity.service-b",
            "params": {"script_path": "/bin/echo B"},
        }
        messages = [
            {"role": "assistant", "content": "Please confirm change A", "action": action_a},
            {"role": "assistant", "content": "Please confirm change B", "action": action_b},
            {"role": "assistant", "content": "Action completed: Updated B", "action": action_b},
        ]
        # A remains unresolved and should be returned.
        assert _find_pending_action(messages) == action_a


class TestExecuteChatActionDispatch:
    def test_control_action_requires_service_id(self):
        result = _execute_chat_action({"action": "start", "params": {}})
        assert result["success"] is False
        assert "Missing service_id for control action" in result["message"]

    def test_delete_action_requires_service_id(self):
        result = _execute_chat_action({"action": "delete", "params": {}})
        assert result["success"] is False
        assert "Missing service_id for delete action" in result["message"]

    def test_update_action_requires_service_id(self):
        result = _execute_chat_action({"action": "update_script", "params": {"script_path": "/bin/echo hi"}})
        assert result["success"] is False
        assert "Missing service_id for update action" in result["message"]

    def test_rename_action_requires_service_id(self):
        result = _execute_chat_action({"action": "rename", "params": {"new_name": "renamed"}})
        assert result["success"] is False
        assert "Missing service_id for rename action" in result["message"]

    def test_convert_action_requires_service_id(self):
        result = _execute_chat_action({"action": "convert_schedule_type", "params": {"schedule_type": "scheduled"}})
        assert result["success"] is False
        assert "Missing service_id for convert action" in result["message"]

    def test_unknown_action_returns_error(self):
        result = _execute_chat_action({"action": "nonexistent_action", "params": {}})
        assert result["success"] is False
        assert "Unknown action type" in result["message"]

    def test_start_all_keepalive_dispatch(self):
        with patch("mac_agents_manager.app._execute_start_all_keepalive") as mock_start_all:
            mock_start_all.return_value = {"success": True, "message": "started"}
            result = _execute_chat_action({"action": "start_all_keepalive", "params": {}})
            assert result["success"] is True
            mock_start_all.assert_called_once()

    def test_create_action_uses_top_level_fields_when_params_missing(self):
        with patch("mac_agents_manager.app._execute_create_action") as mock_create:
            mock_create.return_value = {"success": True, "message": "created"}
            payload = {
                "action": "create",
                "name": "echo-hello",
                "category": "productivity",
                "script_path": "/bin/echo",
            }
            result = _execute_chat_action(payload)
            assert result["success"] is True
            sent_params = mock_create.call_args[0][0]
            assert sent_params["name"] == "echo-hello"
            assert sent_params["category"] == "productivity"

    def test_delete_dispatches_when_service_id_present(self):
        with patch("mac_agents_manager.app._execute_delete_action") as mock_delete:
            mock_delete.return_value = {"success": True, "message": "deleted"}
            result = _execute_chat_action({"action": "delete", "service_id": "agent:user.test.app", "params": {}})
            assert result["success"] is True
            mock_delete.assert_called_once_with("agent:user.test.app")

    def test_rename_dispatches_when_service_id_present(self):
        with patch("mac_agents_manager.app._execute_rename_action") as mock_rename:
            mock_rename.return_value = {"success": True, "message": "renamed"}
            result = _execute_chat_action(
                {
                    "action": "rename",
                    "service_id": "agent:user.test.app",
                    "params": {"new_name": "new-app"},
                }
            )
            assert result["success"] is True
            mock_rename.assert_called_once()

    def test_convert_dispatches_when_service_id_present(self):
        with patch("mac_agents_manager.app._execute_convert_action") as mock_convert:
            mock_convert.return_value = {"success": True, "message": "converted"}
            result = _execute_chat_action(
                {
                    "action": "convert_schedule_type",
                    "service_id": "agent:user.test.app",
                    "params": {"schedule_type": "scheduled"},
                }
            )
            assert result["success"] is True
            mock_convert.assert_called_once()

    def test_execute_chat_action_returns_error_on_exception(self):
        with patch("mac_agents_manager.app._execute_control_action", side_effect=RuntimeError("boom")):
            result = _execute_chat_action({"action": "start", "service_id": "agent:user.test.app", "params": {}})
            assert result["success"] is False
            assert "Error: boom" in result["message"]


class TestRenameFeatureValidation:
    def _create_existing_service(self, mock_agents_dir):
        svc = LaunchService.create_from_form(
            {
                "name": "echo_hello",
                "category": "productivity",
                "script_path": "/bin/echo hi",
                "schedule_type": "keepalive",
            }
        )
        assert svc.save() is True
        return svc

    def test_rename_rejects_invalid_new_name_without_side_effects(self, mock_agents_dir):
        svc = self._create_existing_service(mock_agents_dir)
        with patch("mac_agents_manager.app.LaunchCtlController.unload") as mock_unload, \
                patch("mac_agents_manager.app.LaunchCtlController.load") as mock_load:
            result = _execute_rename_action(svc.service_id, {"new_name": "bad;name"})

        assert result["success"] is False
        assert "invalid" in result["message"].lower()
        assert svc.file_path.exists() is True
        assert (mock_agents_dir / "user.productivity.bad;name.plist").exists() is False
        mock_unload.assert_not_called()
        mock_load.assert_not_called()

    def test_rename_rejects_invalid_new_category_without_side_effects(self, mock_agents_dir):
        svc = self._create_existing_service(mock_agents_dir)
        with patch("mac_agents_manager.app.LaunchCtlController.unload") as mock_unload, \
                patch("mac_agents_manager.app.LaunchCtlController.load") as mock_load:
            result = _execute_rename_action(
                svc.service_id,
                {"new_name": "renamed", "new_category": "bad/category"},
            )

        assert result["success"] is False
        assert "invalid" in result["message"].lower()
        assert svc.file_path.exists() is True
        assert (mock_agents_dir / "user.bad/category.renamed.plist").exists() is False
        mock_unload.assert_not_called()
        mock_load.assert_not_called()

    def test_rename_to_same_label_is_safe_noop(self, mock_agents_dir):
        svc = self._create_existing_service(mock_agents_dir)
        original_path = svc.file_path
        assert original_path.exists() is True

        with patch("mac_agents_manager.app.LaunchCtlController.unload") as mock_unload, \
                patch("mac_agents_manager.app.LaunchCtlController.load") as mock_load:
            result = _execute_rename_action(
                svc.service_id,
                {"new_name": "echo_hello", "new_category": "productivity"},
            )

        assert result["success"] is True
        assert result.get("service_id") == svc.service_id
        assert original_path.exists() is True
        mock_unload.assert_not_called()
        mock_load.assert_not_called()


class TestSecurityHeaders:
    def test_x_frame_options(self, client):
        resp = client.get("/")
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_x_content_type_options(self, client):
        resp = client.get("/")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    def test_referrer_policy(self, client):
        resp = client.get("/")
        assert resp.headers["Referrer-Policy"] == "no-referrer"

    def test_csp(self, client):
        resp = client.get("/")
        assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]

    def test_permissions_policy(self, client):
        resp = client.get("/")
        assert "camera=()" in resp.headers["Permissions-Policy"]


class TestCSRF:
    def test_save_without_csrf_returns_403(self, client):
        resp = client.post("/api/save/new", json={"name": "test"})
        assert resp.status_code == 403

    def test_save_with_wrong_csrf_returns_403(self, client):
        resp = client.post(
            "/api/save/new",
            json={"name": "test"},
            headers={"X-CSRF-Token": "wrong-token"},
        )
        assert resp.status_code == 403

    def test_save_with_valid_csrf(self, client, csrf_token, mock_agents_dir):
        """Save with valid CSRF succeeds (writes to temp dir, not real AGENTS_DIR)."""
        resp = client.post(
            "/api/save/new",
            json={
                "name": "testapp",
                "category": "testing",
                "script_path": "/bin/true",
                "schedule_type": "keepalive",
            },
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert (mock_agents_dir / "user.testing.testapp.plist").exists()

    def test_delete_without_csrf_returns_403(self, client):
        resp = client.post("/delete/agent:user.test.app")
        assert resp.status_code == 403

    def test_control_without_csrf_returns_403(self, client):
        resp = client.post("/control/agent:user.test.app/start")
        assert resp.status_code == 403


class TestIndexRoute:
    def test_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_contains_title(self, client):
        resp = client.get("/")
        assert b"Mac Agents Manager" in resp.data

    def test_contains_csrf_meta(self, client):
        resp = client.get("/")
        assert b'name="csrf-token"' in resp.data


class TestServicesAPI:
    def test_returns_json(self, client, mock_agents_dir):
        resp = client.get("/api/services")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "scheduled" in data
        assert "keepalive" in data


class TestDefaultEnvAPI:
    def test_returns_env_vars(self, client):
        resp = client.get("/api/default-env")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "HOME" in data
        assert "PATH" in data
        assert "USER" in data


class TestServiceDetailAPI:
    def test_invalid_service_id_returns_400(self, client):
        resp = client.get("/api/service/agent:bad;label")
        assert resp.status_code == 400

    def test_missing_service_returns_404(self, client, mock_agents_dir):
        resp = client.get("/api/service/agent:user.test.nonexistent99")
        assert resp.status_code == 404


class TestControlRoute:
    def test_invalid_action_returns_error(self, client, csrf_token, mock_agents_dir):
        resp = client.post(
            "/control/agent:user.test.app/invalid_action",
            headers={
                "Accept": "application/json",
                "X-CSRF-Token": csrf_token,
            },
        )
        assert resp.status_code in (400, 404)


class TestSaveValidation:
    def test_empty_name_rejected(self, client, csrf_token):
        resp = client.post(
            "/api/save/new",
            json={
                "name": "",
                "category": "test",
                "script_path": "/bin/true",
                "schedule_type": "keepalive",
            },
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 400

    def test_invalid_json_rejected(self, client, csrf_token):
        resp = client.post(
            "/api/save/new",
            data="not json",
            content_type="text/plain",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 400
