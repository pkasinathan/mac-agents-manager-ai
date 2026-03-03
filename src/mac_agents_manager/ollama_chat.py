"""Ollama Chat Engine for Mac Agents Manager.

Provides AI chat interface powered by Ollama with auto-start,
crash recovery, model auto-pull, and structured action parsing.
Adapted from chronometry's llm_backends.py pattern.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT = 120
DEFAULT_MAX_CONTEXT = 20
DEFAULT_MAX_TOKENS = 2048
START_TIMEOUT = 30

# ---------------------------------------------------------------------------
# Ollama lifecycle management (ported from chronometry)
# ---------------------------------------------------------------------------


def _is_ollama_reachable(base_url: str, timeout: float = 2.0) -> bool:
    """Quick health check against the Ollama server."""
    try:
        resp = requests.get(base_url, timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def _find_ollama_bin() -> str | None:
    """Locate the ollama binary."""
    path = shutil.which("ollama")
    if path:
        return path
    for candidate in ("/opt/homebrew/bin/ollama", "/usr/local/bin/ollama"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _start_ollama(ollama_bin: str, base_url: str, start_timeout: int = START_TIMEOUT) -> bool:
    """Spawn ``ollama serve`` and wait for it to become reachable."""
    logger.info("Starting Ollama via %s serve ...", ollama_bin)
    try:
        subprocess.Popen(
            [ollama_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as exc:
        logger.error("Failed to start Ollama: %s", exc)
        return False

    deadline = time.monotonic() + start_timeout
    while time.monotonic() < deadline:
        if _is_ollama_reachable(base_url):
            logger.info("Ollama is now running")
            return True
        time.sleep(1)

    logger.warning("Ollama did not become reachable within %ds", start_timeout)
    return False


def ensure_ollama_running(base_url: str = DEFAULT_BASE_URL, start_timeout: int = START_TIMEOUT) -> bool:
    """Start Ollama if it is not already running. Returns True if reachable."""
    if _is_ollama_reachable(base_url):
        return True

    ollama_bin = _find_ollama_bin()
    if ollama_bin is None:
        logger.error("Ollama binary not found -- cannot auto-start the server")
        return False

    logger.info("Ollama not reachable at %s", base_url)
    return _start_ollama(ollama_bin, base_url, start_timeout)


def _restart_ollama(base_url: str = DEFAULT_BASE_URL, start_timeout: int = START_TIMEOUT) -> bool:
    """Kill the running Ollama server and start a fresh one (crash recovery)."""
    ollama_bin = _find_ollama_bin()
    if ollama_bin is None:
        logger.error("Ollama binary not found -- cannot restart")
        return False

    logger.info("Restarting Ollama to recover from server error ...")
    try:
        subprocess.run(["pkill", "-x", "ollama"], capture_output=True, timeout=5)
    except Exception:
        pass
    time.sleep(2)
    return _start_ollama(ollama_bin, base_url, start_timeout)


def _pull_model(base_url: str, model_name: str, timeout: int = 600) -> bool:
    """Pull an Ollama model via the API. Returns True on success."""
    logger.info("Auto-pulling Ollama model '%s' -- this may take several minutes ...", model_name)
    try:
        resp = requests.post(
            f"{base_url}/api/pull",
            json={"name": model_name, "stream": False},
            timeout=timeout,
        )
        if resp.ok:
            logger.info("Successfully pulled model '%s'", model_name)
            return True
        logger.error("Failed to pull model '%s': %s %s", model_name, resp.status_code, resp.text[:200])
    except requests.Timeout:
        logger.error("Timeout pulling model '%s' (>%ds)", model_name, timeout)
    except Exception as exc:
        logger.error("Error pulling model '%s': %s", model_name, exc)
    return False


def _handle_ollama_error(response: requests.Response, base_url: str) -> None:
    """Inspect Ollama HTTP response; restart on runner crashes, raise on errors."""
    if response.ok:
        return

    try:
        body = response.json()
        error_msg = body.get("error", response.text)
    except Exception:
        error_msg = response.text

    # Runner crash recovery
    if response.status_code == 500 and "no longer running" in error_msg:
        logger.warning("Ollama runner crashed: %s", error_msg)
        _restart_ollama(base_url)
        raise RuntimeError(f"Ollama runner crashed (restarted): {error_msg}")

    # Model not found - caller should attempt auto-pull
    if response.status_code == 404 and "not found" in error_msg.lower():
        raise ModelNotFoundError(error_msg)

    raise OllamaError(f"{response.status_code}: {error_msg}")


class OllamaError(RuntimeError):
    """General Ollama error."""


class ModelNotFoundError(OllamaError):
    """Raised when the requested model is not available."""


# ---------------------------------------------------------------------------
# System Prompt Builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """You are the AI assistant for Mac Agents Manager (MAM).
You help users manage macOS LaunchAgents through natural language.

AVAILABLE ACTIONS:
- summarize: Get status summaries and statistics
- modify: Change schedule, script path, working directory, environment variables, label/name
- control: start, stop, restart, load, unload, delete
- create: Create new agents
- query: View plist XML, stdout/stderr logs

{state_block}

RULES:
1. For any modification or control action, output a JSON block with action type and parameters.
   Format: ```json
{{"action": "ACTION_TYPE", "service_id": "SERVICE_ID", "params": {{...}}}}
```
2. Never apply changes directly. Always present what you'll change and wait for user confirmation.
3. For read-only queries (summarize, logs, plist, statistics), respond directly with the information.
4. Be concise and technical. This user is an expert.
5. Use the service data provided - do not guess or hallucinate service names/labels.
6. Do NOT use markdown headers (##). Use plain text with bold (**text**) for emphasis.
7. When listing services, use bullet points.
8. For schedule changes, always show current vs proposed side by side.

VALID ACTION TYPES:
- update_schedule: Change cron schedule (params: schedule_type, intervals)
- update_script: Change ProgramArguments (params: script_path)
- update_working_dir: Change WorkingDirectory (params: working_directory)
- update_environment: Change EnvironmentVariables (params: environment)
- rename: Rename agent (params: new_name, new_category)
- start: Start the service (params: {{}})
- stop: Stop the service (params: {{}})
- restart: Restart the service (params: {{}})
- load: Load into launchd (params: {{}})
- unload: Unload from launchd (params: {{}})
- delete: Delete the agent (params: {{}})
- create: Create new agent (params: name, category, script_path, schedule_type, schedule_hour_0, schedule_minute_0, ...)
- convert_schedule_type: Convert keepalive<->scheduled (params: to)
- start_all_keepalive: Start all stopped KeepAlive agents (params: {{}})"""


def build_system_prompt(services_summary: dict[str, Any], selected_service: dict[str, Any] | None = None) -> str:
    """Build a system prompt with current MAM state."""
    state_lines = []

    # Global state
    total = services_summary.get("total", 0)
    running = services_summary.get("running", 0)
    stopped = services_summary.get("stopped", 0)
    not_loaded = services_summary.get("not_loaded", 0)
    keepalive_count = services_summary.get("keepalive_count", 0)
    scheduled_count = services_summary.get("scheduled_count", 0)

    state_lines.append("CURRENT STATE:")
    state_lines.append(f"Total agents: {total}")
    state_lines.append(f"Running: {running}, Stopped: {stopped}, Not Loaded: {not_loaded}")
    state_lines.append(f"KeepAlive: {keepalive_count}, Scheduled: {scheduled_count}")

    # Namespace summary
    namespaces = services_summary.get("namespaces", {})
    if namespaces:
        ns_parts = [f"{ns} ({count})" for ns, count in sorted(namespaces.items())]
        state_lines.append(f"Namespaces: {', '.join(ns_parts)}")

    # Services list
    services_list = services_summary.get("services", [])
    if services_list:
        state_lines.append("")
        state_lines.append("Services list:")
        for svc in services_list:
            label = svc.get("label", "unknown")
            stype = svc.get("schedule_type", "unknown")
            status_parts = []
            if stype == "keepalive":
                status_parts.append("KeepAlive")
            else:
                times = svc.get("schedule_times", [])
                if times:
                    time_strs = [f"{t.get('Hour', 0):02d}:{t.get('Minute', 0):02d}" for t in times]
                    status_parts.append(f"Scheduled {', '.join(time_strs)}")
                else:
                    status_parts.append("Scheduled")

            svc_status = svc.get("status", {})
            if svc_status.get("running"):
                pid = svc_status.get("pid", "?")
                status_parts.append(f"Running, PID: {pid}")
            elif svc_status.get("loaded"):
                status_parts.append("Loaded, Stopped")
            else:
                status_parts.append("Not Loaded")

            state_lines.append(f"- {label} [{', '.join(status_parts)}]")

    # Selected service context
    if selected_service:
        state_lines.append("")
        state_lines.append(f"SELECTED SERVICE: {selected_service.get('label', 'unknown')}")
        state_lines.append(f"Label: {selected_service.get('label', '')}")
        state_lines.append(f"Type: {selected_service.get('schedule_type', '')}")

        times = selected_service.get("schedule_times", [])
        if times:
            time_strs = [f"Hour={t.get('Hour', 0)}, Minute={t.get('Minute', 0)}" for t in times]
            state_lines.append(f"Schedule: {'; '.join(time_strs)}")

        svc_status = selected_service.get("status", {})
        status_str = "Running" if svc_status.get("running") else ("Loaded, Not Running" if svc_status.get("loaded") else "Not Loaded")
        state_lines.append(f"Status: {status_str}")
        if svc_status.get("pid"):
            state_lines.append(f"PID: {svc_status['pid']}")

        state_lines.append(f"Script: {selected_service.get('program', '')}")
        state_lines.append(f"Working Dir: {selected_service.get('working_directory', '')}")

        env = selected_service.get("environment", {})
        if env:
            env_str = ", ".join(f"{k}={v}" for k, v in env.items())
            state_lines.append(f"Env Vars: {env_str}")

        log_paths = selected_service.get("log_paths", {})
        state_lines.append(f"Stdout Path: {log_paths.get('stdout', '')}")
        state_lines.append(f"Stderr Path: {log_paths.get('stderr', '')}")

        plist_xml = selected_service.get("plist_xml", "")
        if plist_xml:
            state_lines.append(f"Plist XML:\n{plist_xml}")

        # Include log tails if present
        logs = selected_service.get("logs", {})
        stdout_log = logs.get("stdout", "")
        stderr_log = logs.get("stderr", "")
        if stdout_log:
            # Trim to last 10 lines
            stdout_lines = stdout_log.strip().split("\n")[-10:]
            state_lines.append(f"Stdout (last {len(stdout_lines)} lines):")
            for line in stdout_lines:
                state_lines.append(f"  {line}")
        if stderr_log:
            stderr_lines = stderr_log.strip().split("\n")[-10:]
            state_lines.append(f"Stderr (last {len(stderr_lines)} lines):")
            for line in stderr_lines:
                state_lines.append(f"  {line}")

    state_block = "\n".join(state_lines)
    return SYSTEM_PROMPT_TEMPLATE.format(state_block=state_block)


# ---------------------------------------------------------------------------
# Action parsing
# ---------------------------------------------------------------------------

_ACTION_JSON_PATTERN = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

VALID_ACTIONS = frozenset({
    "update_schedule",
    "update_script",
    "update_working_dir",
    "update_environment",
    "rename",
    "start",
    "stop",
    "restart",
    "load",
    "unload",
    "delete",
    "create",
    "convert_schedule_type",
    "start_all_keepalive",
})

MUTATING_ACTIONS = frozenset({
    "update_schedule",
    "update_script",
    "update_working_dir",
    "update_environment",
    "rename",
    "delete",
    "create",
    "convert_schedule_type",
    "start",
    "stop",
    "restart",
    "load",
    "unload",
    "start_all_keepalive",
})


def parse_action(response_text: str) -> dict[str, Any]:
    """Extract structured action JSON from AI response.

    Returns:
        {
            "type": "action" | "info",
            "message": str,           # AI text with JSON block removed
            "action": dict | None,    # parsed action if present
            "requires_confirmation": bool
        }
    """
    match = _ACTION_JSON_PATTERN.search(response_text)
    if not match:
        return {
            "type": "info",
            "message": response_text.strip(),
            "action": None,
            "requires_confirmation": False,
        }

    try:
        action_data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {
            "type": "info",
            "message": response_text.strip(),
            "action": None,
            "requires_confirmation": False,
        }

    action_type = action_data.get("action", "")
    if action_type not in VALID_ACTIONS:
        return {
            "type": "info",
            "message": response_text.strip(),
            "action": None,
            "requires_confirmation": False,
        }

    # Remove JSON block from the display message
    clean_message = _ACTION_JSON_PATTERN.sub("", response_text).strip()

    return {
        "type": "action",
        "message": clean_message,
        "action": action_data,
        "requires_confirmation": action_type in MUTATING_ACTIONS,
    }


# ---------------------------------------------------------------------------
# Chat Engine
# ---------------------------------------------------------------------------


class OllamaChatEngine:
    """Manages Ollama lifecycle and chat conversations."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        max_context: int | None = None,
        max_tokens: int | None = None,
    ):
        self.model = model or os.environ.get("MAM_OLLAMA_MODEL", DEFAULT_MODEL)
        self.base_url = base_url or os.environ.get("MAM_OLLAMA_BASE_URL", DEFAULT_BASE_URL)
        self.timeout = timeout or int(os.environ.get("MAM_OLLAMA_TIMEOUT", str(DEFAULT_TIMEOUT)))
        self.max_context = max_context or int(os.environ.get("MAM_CHAT_MAX_CONTEXT", str(DEFAULT_MAX_CONTEXT)))
        self.max_tokens = max_tokens or DEFAULT_MAX_TOKENS

    def health_check(self) -> dict[str, Any]:
        """Check Ollama connectivity and model availability."""
        ollama_running = _is_ollama_reachable(self.base_url)
        model_available = False

        if ollama_running:
            try:
                resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
                if resp.ok:
                    models = resp.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    # Check both exact and without tag
                    model_available = any(
                        self.model in name or name.startswith(self.model.split(":")[0])
                        for name in model_names
                    )
            except Exception:
                pass

        return {
            "ollama_running": ollama_running,
            "model_available": model_available,
            "model_name": self.model,
            "base_url": self.base_url,
        }

    def send_message(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]],
        services_summary: dict[str, Any],
        selected_service: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a message to Ollama and return the parsed response.

        Args:
            user_message: The user's message
            conversation_history: Previous messages (role/content dicts)
            services_summary: Current MAM state summary
            selected_service: Currently selected service data (if any)

        Returns:
            {
                "response": str,       # AI text response
                "action": dict | None, # parsed action if present
                "requires_confirmation": bool,
                "error": str | None
            }
        """
        # Ensure Ollama is running
        if not ensure_ollama_running(self.base_url):
            return {
                "response": "Ollama is not running and could not be started. Please install Ollama: https://ollama.com",
                "action": None,
                "requires_confirmation": False,
                "error": "ollama_unavailable",
            }

        # Build system prompt
        system_prompt = build_system_prompt(services_summary, selected_service)

        # Build messages array
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history (limited to max_context)
        if conversation_history:
            recent = conversation_history[-self.max_context:]
            messages.extend(recent)

        # Add the new user message
        messages.append({"role": "user", "content": user_message})

        # Call Ollama
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "num_predict": self.max_tokens,
            },
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )

            try:
                _handle_ollama_error(response, self.base_url)
            except ModelNotFoundError:
                # Auto-pull the model
                if _pull_model(self.base_url, self.model):
                    response = requests.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                        timeout=self.timeout,
                    )
                    _handle_ollama_error(response, self.base_url)
                else:
                    return {
                        "response": f"Model '{self.model}' is not available and auto-pull failed. "
                                    f"Run: `ollama pull {self.model}`",
                        "action": None,
                        "requires_confirmation": False,
                        "error": "model_not_found",
                    }

            data = response.json()
            ai_text = data.get("message", {}).get("content", "")

            if not ai_text:
                return {
                    "response": "The AI returned an empty response. Please try again.",
                    "action": None,
                    "requires_confirmation": False,
                    "error": "empty_response",
                }

            # Parse for structured actions
            parsed = parse_action(ai_text)

            return {
                "response": parsed["message"],
                "action": parsed["action"],
                "requires_confirmation": parsed["requires_confirmation"],
                "error": None,
            }

        except (requests.Timeout, requests.ConnectionError) as exc:
            logger.error("Ollama request failed: %s", exc)
            return {
                "response": "Request to Ollama timed out. The model may still be loading. Please try again in a moment.",
                "action": None,
                "requires_confirmation": False,
                "error": "timeout",
            }
        except OllamaError as exc:
            logger.error("Ollama error: %s", exc)
            return {
                "response": f"Ollama error: {exc}",
                "action": None,
                "requires_confirmation": False,
                "error": "ollama_error",
            }
        except Exception as exc:
            logger.exception("Unexpected error in chat")
            return {
                "response": f"An unexpected error occurred: {exc}",
                "action": None,
                "requires_confirmation": False,
                "error": "unexpected",
            }
