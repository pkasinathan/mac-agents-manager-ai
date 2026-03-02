"""Tests for the Flask application routes and security."""



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
