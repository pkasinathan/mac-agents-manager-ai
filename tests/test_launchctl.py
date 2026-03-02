"""Tests for the LaunchCtlController."""
import subprocess
from unittest.mock import MagicMock, patch

from mac_agents_manager.launchctl import LaunchCtlController


class TestGetStatus:
    def test_loaded_and_running(self):
        result = MagicMock()
        result.returncode = 0
        result.stdout = '{\n\t"PID" = 12345;\n\t"Label" = "user.test.app";\n};'
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            status = LaunchCtlController.get_status("user.test.app")
        assert status["loaded"] is True
        assert status["running"] is True
        assert status["pid"] == "12345"

    def test_loaded_but_not_running(self):
        result = MagicMock()
        result.returncode = 0
        result.stdout = '{\n\t"Label" = "user.test.app";\n};'
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            status = LaunchCtlController.get_status("user.test.app")
        assert status["loaded"] is True
        assert status["running"] is False
        assert status["pid"] is None

    def test_not_loaded(self):
        result = MagicMock()
        result.returncode = 113
        result.stdout = ""
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            status = LaunchCtlController.get_status("user.test.app")
        assert status["loaded"] is False
        assert status["running"] is False

    def test_timeout_returns_error_status(self):
        with patch(
            "mac_agents_manager.launchctl.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="launchctl", timeout=5),
        ):
            status = LaunchCtlController.get_status("user.test.app")
        assert status["loaded"] is False
        assert "error" in status


class TestLoad:
    def test_success(self):
        result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            ok, msg = LaunchCtlController.load("user.test.app", "/tmp/test.plist")
        assert ok is True
        assert "Successfully loaded" in msg

    def test_failure(self):
        result = MagicMock(returncode=1, stdout="", stderr="already loaded")
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            ok, msg = LaunchCtlController.load("user.test.app", "/tmp/test.plist")
        assert ok is False
        assert "Failed to load" in msg


class TestUnload:
    def test_success(self):
        result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            ok, msg = LaunchCtlController.unload("user.test.app", "/tmp/test.plist")
        assert ok is True
        assert "Successfully unloaded" in msg

    def test_failure(self):
        result = MagicMock(returncode=1, stdout="", stderr="not loaded")
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            ok, msg = LaunchCtlController.unload("user.test.app", "/tmp/test.plist")
        assert ok is False


class TestStart:
    def test_success(self):
        result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            ok, msg = LaunchCtlController.start("user.test.app")
        assert ok is True

    def test_failure(self):
        result = MagicMock(returncode=1, stdout="", stderr="error")
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            ok, msg = LaunchCtlController.start("user.test.app")
        assert ok is False


class TestStop:
    def test_success(self):
        result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            ok, msg = LaunchCtlController.stop("user.test.app")
        assert ok is True

    def test_failure(self):
        result = MagicMock(returncode=1, stdout="", stderr="error")
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            ok, msg = LaunchCtlController.stop("user.test.app")
        assert ok is False


class TestRestart:
    def test_success(self):
        result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            ok, msg = LaunchCtlController.restart("user.test.app", "/tmp/test.plist")
        assert ok is True
        assert "Successfully restarted" in msg

    def test_start_fails(self):
        results = [
            MagicMock(returncode=0),  # stop succeeds
            MagicMock(returncode=1, stdout="", stderr="error"),  # start fails
        ]
        with patch(
            "mac_agents_manager.launchctl.subprocess.run", side_effect=results
        ):
            ok, msg = LaunchCtlController.restart("user.test.app", "/tmp/test.plist")
        assert ok is False


class TestKickstart:
    def test_success(self):
        id_result = MagicMock(stdout="501\n")
        kick_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch(
            "mac_agents_manager.launchctl.subprocess.run",
            side_effect=[id_result, kick_result],
        ):
            ok, msg = LaunchCtlController.kickstart("user.test.app")
        assert ok is True

    def test_unnecessary_treated_as_success(self):
        id_result = MagicMock(stdout="501\n")
        kick_result = MagicMock(returncode=1, stdout="", stderr="label: unnecessary")
        with patch(
            "mac_agents_manager.launchctl.subprocess.run",
            side_effect=[id_result, kick_result],
        ):
            ok, msg = LaunchCtlController.kickstart("user.test.app")
        assert ok is True


class TestBootout:
    def test_success(self):
        id_result = MagicMock(stdout="501\n")
        bootout_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch(
            "mac_agents_manager.launchctl.subprocess.run",
            side_effect=[id_result, bootout_result],
        ):
            ok, msg = LaunchCtlController.bootout("user.test.app")
        assert ok is True

    def test_failure(self):
        id_result = MagicMock(stdout="501\n")
        bootout_result = MagicMock(returncode=1, stdout="", stderr="not loaded")
        with patch(
            "mac_agents_manager.launchctl.subprocess.run",
            side_effect=[id_result, bootout_result],
        ):
            ok, msg = LaunchCtlController.bootout("user.test.app")
        assert ok is False
