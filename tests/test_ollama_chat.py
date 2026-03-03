"""Tests for the Ollama Chat Engine — prompt building, action parsing, etc."""

import json

import pytest

from mac_agents_manager.ollama_chat import (
    MUTATING_ACTIONS,
    VALID_ACTIONS,
    OllamaChatEngine,
    build_system_prompt,
    parse_action,
)


# ---------------------------------------------------------------------------
# Action parsing
# ---------------------------------------------------------------------------

class TestParseAction:
    """Tests for parse_action()."""

    def test_plain_text_returns_info(self):
        result = parse_action("Here are your services...")
        assert result["type"] == "info"
        assert result["action"] is None
        assert result["requires_confirmation"] is False
        assert "Here are your services" in result["message"]

    def test_valid_action_json_extracted(self):
        text = 'I will update the schedule.\n```json\n{"action": "update_schedule", "service_id": "agent:user.test.app", "params": {"schedule_type": "scheduled", "intervals": [{"Hour": 8, "Minute": 0}]}}\n```\nLet me know.'
        result = parse_action(text)
        assert result["type"] == "action"
        assert result["action"]["action"] == "update_schedule"
        assert result["action"]["service_id"] == "agent:user.test.app"
        assert result["requires_confirmation"] is True
        # JSON block should be removed from message
        assert "```json" not in result["message"]
        assert "I will update the schedule" in result["message"]

    def test_control_action_requires_confirmation(self):
        text = '```json\n{"action": "start", "service_id": "agent:user.test.app", "params": {}}\n```'
        result = parse_action(text)
        assert result["type"] == "action"
        assert result["action"]["action"] == "start"
        assert result["requires_confirmation"] is True

    def test_invalid_action_type_returns_info(self):
        text = '```json\n{"action": "hack_system", "params": {}}\n```'
        result = parse_action(text)
        assert result["type"] == "info"
        assert result["action"] is None

    def test_invalid_json_returns_info(self):
        text = '```json\n{broken json\n```'
        result = parse_action(text)
        assert result["type"] == "info"
        assert result["action"] is None

    def test_empty_string_returns_info(self):
        result = parse_action("")
        assert result["type"] == "info"
        assert result["message"] == ""

    def test_all_valid_actions_accepted(self):
        for action_name in VALID_ACTIONS:
            text = f'```json\n{{"action": "{action_name}", "service_id": "agent:user.test.app", "params": {{}}}}\n```'
            result = parse_action(text)
            assert result["type"] == "action", f"Action {action_name} was not parsed"

    def test_all_actions_are_mutating(self):
        """All current valid actions require confirmation."""
        assert VALID_ACTIONS == MUTATING_ACTIONS


# ---------------------------------------------------------------------------
# System prompt building
# ---------------------------------------------------------------------------

class TestBuildSystemPrompt:
    """Tests for build_system_prompt()."""

    def test_global_context_only(self):
        summary = {
            "total": 10,
            "running": 7,
            "stopped": 2,
            "not_loaded": 1,
            "keepalive_count": 6,
            "scheduled_count": 4,
            "namespaces": {"productivity": 5, "finance": 3, "automation": 2},
            "services": [],
        }
        prompt = build_system_prompt(summary)
        assert "Total agents: 10" in prompt
        assert "Running: 7" in prompt
        assert "KeepAlive: 6" in prompt
        assert "productivity (5)" in prompt
        assert "SELECTED SERVICE" not in prompt

    def test_selected_service_context(self):
        summary = {
            "total": 1,
            "running": 1,
            "stopped": 0,
            "not_loaded": 0,
            "keepalive_count": 1,
            "scheduled_count": 0,
            "namespaces": {"test": 1},
            "services": [],
        }
        selected = {
            "label": "user.test.myapp",
            "schedule_type": "keepalive",
            "schedule_times": [],
            "status": {"loaded": True, "running": True, "pid": "1234"},
            "program": "/bin/bash /path/to/script.sh",
            "working_directory": "/tmp",
            "environment": {"HOME": "/Users/test"},
            "log_paths": {"stdout": "/tmp/test.out", "stderr": "/tmp/test.err"},
            "plist_xml": "<plist>...</plist>",
            "logs": {"stdout": "line1\nline2", "stderr": ""},
        }
        prompt = build_system_prompt(summary, selected)
        assert "SELECTED SERVICE: user.test.myapp" in prompt
        assert "PID: 1234" in prompt
        assert "/bin/bash /path/to/script.sh" in prompt
        assert "HOME=/Users/test" in prompt

    def test_prompt_contains_rules(self):
        summary = {"total": 0, "running": 0, "stopped": 0, "not_loaded": 0, "keepalive_count": 0, "scheduled_count": 0, "namespaces": {}, "services": []}
        prompt = build_system_prompt(summary)
        assert "AVAILABLE ACTIONS" in prompt
        assert "VALID ACTION TYPES" in prompt
        assert "Never apply changes directly" in prompt


# ---------------------------------------------------------------------------
# Chat Engine initialization
# ---------------------------------------------------------------------------

class TestOllamaChatEngine:
    """Tests for OllamaChatEngine initialization and health check."""

    def test_default_config(self):
        engine = OllamaChatEngine()
        assert engine.model == "qwen3.5:4b"
        assert engine.base_url == "http://localhost:11434"
        assert engine.timeout == 120
        assert engine.max_context == 20

    def test_custom_config(self):
        engine = OllamaChatEngine(model="llama3:8b", base_url="http://myhost:11434", timeout=60, max_context=10)
        assert engine.model == "llama3:8b"
        assert engine.base_url == "http://myhost:11434"
        assert engine.timeout == 60
        assert engine.max_context == 10

    def test_health_check_returns_dict(self):
        engine = OllamaChatEngine()
        result = engine.health_check()
        assert "ollama_running" in result
        assert "model_available" in result
        assert "model_name" in result
        assert result["model_name"] == "qwen3.5:4b"
