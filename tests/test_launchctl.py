"""Tests for the LaunchCtlController."""
import subprocess
from unittest.mock import MagicMock, patch

from mac_agents_manager.launchctl import LaunchCtlController, classify_status, decorate_status


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
        result.stdout = '{\n\t"Label" = "user.test.app";\n\t"LastExitStatus" = 0;\n};'
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            status = LaunchCtlController.get_status("user.test.app")
        assert status["loaded"] is True
        assert status["running"] is False
        assert status["pid"] is None
        assert status["last_exit"] == 0

    def test_parses_nonzero_last_exit(self):
        result = MagicMock()
        result.returncode = 0
        result.stdout = '{\n\t"Label" = "user.test.app";\n\t"LastExitStatus" = 256;\n};'
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            status = LaunchCtlController.get_status("user.test.app")
        assert status["last_exit"] == 256

    def test_status_code_still_means_loaded(self):
        """status_code predates last_exit and must keep its original meaning."""
        loaded = MagicMock()
        loaded.returncode = 0
        loaded.stdout = '{\n\t"Label" = "user.test.app";\n\t"LastExitStatus" = 256;\n};'
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=loaded):
            assert LaunchCtlController.get_status("user.test.app")["status_code"] == "0"

        unloaded = MagicMock()
        unloaded.returncode = 113
        unloaded.stdout = ""
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=unloaded):
            assert LaunchCtlController.get_status("user.test.app")["status_code"] is None

    def test_not_loaded(self):
        result = MagicMock()
        result.returncode = 113
        result.stdout = ""
        with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
            status = LaunchCtlController.get_status("user.test.app")
        assert status["loaded"] is False
        assert status["running"] is False
        assert status["last_exit"] is None

    def test_timeout_returns_error_status(self):
        with patch(
            "mac_agents_manager.launchctl.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="launchctl", timeout=5),
        ):
            status = LaunchCtlController.get_status("user.test.app")
        assert status["loaded"] is False
        assert "error" in status

    def test_every_branch_returns_the_same_keys(self):
        """Callers index these keys directly, so the shape cannot vary."""
        expected = {"loaded", "running", "pid", "last_exit", "status_code"}

        loaded = MagicMock()
        loaded.returncode = 0
        loaded.stdout = '{\n\t"PID" = 12345;\n};'
        unloaded = MagicMock()
        unloaded.returncode = 113
        unloaded.stdout = ""

        for result in (loaded, unloaded):
            with patch("mac_agents_manager.launchctl.subprocess.run", return_value=result):
                assert expected <= set(LaunchCtlController.get_status("user.test.app"))

        with patch(
            "mac_agents_manager.launchctl.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="launchctl", timeout=5),
        ):
            assert expected <= set(LaunchCtlController.get_status("user.test.app"))


class TestClassifyStatus:
    def test_interval_success_is_idle(self):
        status = {"loaded": True, "running": False, "pid": None, "last_exit": 0}
        assert classify_status(status, "interval") == "idle"

    def test_scheduled_success_is_idle(self):
        status = {"loaded": True, "running": False, "pid": None, "last_exit": 0}
        assert classify_status(status, "scheduled") == "idle"

    def test_keepalive_without_pid_is_stopped(self):
        status = {"loaded": True, "running": False, "pid": None, "last_exit": 0}
        assert classify_status(status, "keepalive") == "stopped"

    def test_interval_failed_exit_is_stopped(self):
        status = {"loaded": True, "running": False, "pid": None, "last_exit": 256}
        assert classify_status(status, "interval") == "stopped"

    def test_running_wins(self):
        status = {"loaded": True, "running": True, "pid": "12", "last_exit": 0}
        assert classify_status(status, "interval") == "running"

    def test_decorate_sets_idle_flag(self):
        decorated = decorate_status(
            {"loaded": True, "running": False, "pid": None, "last_exit": 0},
            "interval",
        )
        assert decorated["state"] == "idle"
        assert decorated["idle"] is True


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
