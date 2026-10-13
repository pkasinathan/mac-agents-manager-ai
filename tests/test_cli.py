"""Tests for CLI argument parsing and subcommands."""
import plistlib
import subprocess
import sys
from pathlib import Path

from mac_agents_manager import __version__, cli


class TestVersionFlag:
    def test_version_output(self):
        result = subprocess.run(
            [sys.executable, "-m", "mac_agents_manager.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert __version__ in result.stdout
        assert result.returncode == 0


class TestHelpFlag:
    def test_help_output(self):
        result = subprocess.run(
            [sys.executable, "-m", "mac_agents_manager.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "Mac Agents Manager" in result.stdout

    def test_subcommand_help(self):
        for subcmd in ["serve", "list", "show", "create", "load", "unload",
                        "start", "stop", "restart", "delete", "start-all",
                        "logs", "open"]:
            result = subprocess.run(
                [sys.executable, "-m", "mac_agents_manager.cli", subcmd, "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0, f"{subcmd} --help failed"


class TestArgParsing:
    """Verify argument parsing without actually executing commands."""

    def test_serve_defaults(self):
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        p_serve = subparsers.add_parser("serve")
        p_serve.add_argument("-p", "--port", type=int, default=8081)
        p_serve.add_argument("--host", default="127.0.0.1")
        p_serve.add_argument("--debug", action="store_true", default=False)

        args = parser.parse_args(["serve"])
        assert args.port == 8081
        assert args.host == "127.0.0.1"
        assert args.debug is False

    def test_create_requires_category_and_script(self):
        result = subprocess.run(
            [sys.executable, "-m", "mac_agents_manager.cli", "create", "myapp"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
        assert "required" in result.stderr.lower()


class TestLaunchctlParsing:
    def test_is_loaded_matches_exact_label_not_substring(self, monkeypatch):
        class FakeResult:
            def __init__(self, stdout):
                self.stdout = stdout

        output = (
            "PID Status Label\n"
            "111 0 user.productivity.mac_agents_manager-helper\n"
            "222 0 user.productivity.other\n"
        )

        monkeypatch.setattr(
            cli.subprocess,
            "run",
            lambda *args, **kwargs: FakeResult(output),
        )

        assert cli._is_loaded("user.productivity.mac_agents_manager") is False

    def test_is_loaded_accepts_whitespace_separated_output(self, monkeypatch):
        class FakeResult:
            def __init__(self, stdout):
                self.stdout = stdout

        output = (
            "PID Status Label\n"
            "58657    0    user.productivity.mac_agents_manager\n"
        )

        monkeypatch.setattr(
            cli.subprocess,
            "run",
            lambda *args, **kwargs: FakeResult(output),
        )

        assert cli._is_loaded("user.productivity.mac_agents_manager") is True


class TestGeneratePlist:
    def test_generate_plist_sets_localhost_host_and_valid_xml(self, tmp_path, monkeypatch):
        launch_agents_dir = tmp_path / "LaunchAgents"
        logs_dir = tmp_path / "logs"
        plist_path = launch_agents_dir / "user.productivity.mac_agents_manager.plist"

        monkeypatch.setattr(cli, "LAUNCH_AGENTS_DIR", launch_agents_dir)
        monkeypatch.setattr(cli, "MAM_LOG_DIR", logs_dir)
        monkeypatch.setattr(cli, "MAM_PLIST", plist_path)
        monkeypatch.setenv("MAM_PORT", "9090")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USER", "tester")

        cli._generate_plist()

        assert plist_path.exists()
        with open(plist_path, "rb") as f:
            data = plistlib.load(f)

        args = data["ProgramArguments"]
        assert "--host" in args
        assert "127.0.0.1" in args
        assert "--port" in args
        assert "9090" in args
        assert Path(data["StandardOutPath"]).name == "webserver.log"
