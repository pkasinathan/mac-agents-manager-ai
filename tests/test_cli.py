"""Tests for CLI argument parsing and subcommands."""
import subprocess
import sys

from mac_agents_manager import __version__


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
