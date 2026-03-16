"""Flask application for managing macOS LaunchAgents."""
import hashlib
import hmac
import os
import re
from collections import deque
from pathlib import Path

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for

from mac_agents_manager.constants import MAM_LABEL
from mac_agents_manager.launchctl import LaunchCtlController
from mac_agents_manager.models import ALLOWED_LOG_DIRS, LaunchService

_pkg_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
            template_folder=os.path.join(_pkg_dir, 'templates'),
            static_folder=os.path.join(_pkg_dir, 'static'))
app.secret_key = os.urandom(24)

_csrf_token = hashlib.sha256(os.urandom(32)).hexdigest()

# ---------------------------------------------------------------------------
# AI Chat engine & history (lazy-init to avoid import overhead on every request)
# ---------------------------------------------------------------------------
_chat_engine = None
_chat_history = None


def _get_chat_engine():
    global _chat_engine
    if _chat_engine is None:
        from mac_agents_manager.ollama_chat import OllamaChatEngine
        _chat_engine = OllamaChatEngine()
    return _chat_engine


def _get_chat_history():
    global _chat_history
    if _chat_history is None:
        from mac_agents_manager.chat_history import ChatHistory
        _chat_history = ChatHistory()
        # Cleanup old sessions on first access
        _chat_history.cleanup_old_sessions()
    return _chat_history


@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    port = os.environ.get('MAM_PORT', '8081')
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'"
    )
    response.headers['Content-Security-Policy'] = csp
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    allowed_origins = {f'http://localhost:{port}', f'http://127.0.0.1:{port}'}
    origin = request.headers.get('Origin', '')
    if origin and origin not in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = ''
    response.headers.pop("Server", None)
    return response


def _check_csrf():
    """Validate CSRF token on state-changing requests."""
    token = request.headers.get('X-CSRF-Token', '')
    if not hmac.compare_digest(token, _csrf_token):
        abort(403)


@app.route('/')
def index():
    """IDE-style dashboard."""
    port = int(os.environ.get('MAM_PORT', '8081'))
    return render_template('index.html', port=port, csrf_token=_csrf_token)


@app.route('/api/default-env')
def api_default_env():
    """API endpoint to get default environment variables."""
    username = os.environ.get('USER', 'user')
    home_dir = os.environ.get('HOME', f'/Users/{username}')

    # Check if pyenv shims exist
    pyenv_shims = f"{home_dir}/.pyenv/shims"
    path_components = [
        '/usr/local/bin',
        '/usr/bin',
        '/bin',
        '/opt/homebrew/bin'
    ]
    if os.path.exists(pyenv_shims):
        path_components.append(pyenv_shims)

    default_env = {
        'HOME': home_dir,
        'PATH': ':'.join(path_components),
        'USER': username
    }

    return jsonify(default_env)


@app.route('/api/services')
def api_services():
    """API endpoint to get all services in tree structure."""
    tree = LaunchService.get_services_tree()

    # Convert services to dictionaries and add status
    result = {
        'scheduled': {},
        'keepalive': {}
    }

    for namespace, services in tree['scheduled'].items():
        result['scheduled'][namespace] = []
        for service in services:
            status = LaunchCtlController.get_status(service.label)
            result['scheduled'][namespace].append({
                **service.to_dict(),
                'status': status
            })

    for namespace, services in tree['keepalive'].items():
        result['keepalive'][namespace] = []
        for service in services:
            status = LaunchCtlController.get_status(service.label)
            result['keepalive'][namespace].append({
                **service.to_dict(),
                'status': status
            })

    return jsonify(result)


@app.route('/api/service/<path:service_id>')
def api_service(service_id):
    """API endpoint to get a single service details."""
    try:
        service = LaunchService.from_service_id(service_id)
    except ValueError:
        abort(400)

    if not service.file_path.exists():
        return jsonify({'error': 'Service not found'}), 404

    service = LaunchService.from_file(service.file_path)
    if service is None:
        return jsonify({'error': 'Failed to load service plist'}), 500
    status = LaunchCtlController.get_status(service.label)

    # Read logs
    log_paths = service.get_log_paths()
    logs = {
        'stdout': read_log_file(log_paths.get('stdout', ''), tail=100),
        'stderr': read_log_file(log_paths.get('stderr', ''), tail=100)
    }

    return jsonify({
        **service.to_dict(),
        'status': status,
        'logs': logs
    })


@app.route('/api/save/<path:service_id>', methods=['POST'])
def api_save(service_id):
    """API endpoint to save service changes."""
    _check_csrf()
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'success': False, 'message': 'Request body must be valid JSON'}), 400

        if service_id == 'new':
            service = LaunchService.create_from_form(data)
        else:
            service = LaunchService.from_service_id(service_id)
            if not service.file_path.exists():
                return jsonify({'success': False, 'message': 'Service not found'}), 404

            service = LaunchService.from_file(service.file_path)
            if service is None:
                return jsonify({'success': False, 'message': 'Failed to load service plist'}), 500
            service.update_from_form(data)

        if service.save():
            return jsonify({
                'success': True,
                'message': f'Service {service.name} saved successfully',
                'service_id': service.service_id
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to save service. Check file permissions.'
            }), 500
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception:
        app.logger.exception("Error saving service")
        return jsonify({
            'success': False,
            'message': 'An internal error occurred while saving the service.'
        }), 500


@app.route('/delete/<path:service_id>', methods=['POST'])
def delete(service_id):
    """Delete a service."""
    _check_csrf()
    try:
        service = LaunchService.from_service_id(service_id)
    except ValueError:
        abort(400)

    try:
        if service.file_path.exists():
            LaunchCtlController.unload(service.label, str(service.file_path))

        if service.delete():
            flash(f'Service {service.label} deleted successfully!', 'success')
        else:
            flash('Failed to delete service file.', 'error')
    except Exception:
        app.logger.exception("Error deleting service")
        flash('An internal error occurred while deleting the service.', 'error')

    return redirect(url_for('index'))


_VALID_ACTIONS = frozenset({'load', 'unload', 'start', 'stop', 'restart'})


@app.route('/control/<path:service_id>/<action>', methods=['POST'])
def control(service_id, action):
    """Control a service (load, unload, start, stop, restart)."""
    _check_csrf()

    if action not in _VALID_ACTIONS:
        return jsonify({'success': False, 'message': 'Invalid action'}), 400

    try:
        service = LaunchService.from_service_id(service_id)
    except ValueError:
        abort(400)

    if not service.file_path.exists():
        return jsonify({'success': False, 'message': 'Service not found'}), 404

    controller = LaunchCtlController()
    plist_path = str(service.file_path)

    if action == 'load':
        success, message = controller.load(service.label, plist_path)
    elif action == 'unload':
        if service.label == MAM_LABEL:
            return jsonify({'success': False, 'message': 'Unload disabled for Mac Agents Manager. Use reload.'}), 400
        success, message = controller.unload(service.label, plist_path)
    elif action == 'start':
        success, message = controller.start(service.label)
    elif action == 'stop':
        success, message = controller.stop(service.label)
    elif action == 'restart':
        if service.label == MAM_LABEL:
            success, message = controller.kickstart(service.label)
        else:
            success, message = controller.restart(service.label, plist_path)

    response = {
        'success': success,
        'message': message
    }

    # For web requests (not AJAX), use flash and redirect to index
    if request.headers.get('Accept') != 'application/json':
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        return redirect(url_for('index'))

    # For AJAX requests, return JSON
    return jsonify(response)


@app.route('/api/start-all-keepalive', methods=['POST'])
def api_start_all_keepalive():
    """Start all KeepAlive services that are not running."""
    _check_csrf()
    try:
        services = LaunchService.list_user_services()
        results = []

        for service in services:
            if service.get_schedule_type() != 'keepalive':
                continue

            status = LaunchCtlController.get_status(service.label)

            if not status.get('running') and status.get('loaded'):
                success, message = LaunchCtlController.start(service.label)
                results.append({
                    'service_id': service.service_id,
                    'name': service.name,
                    'label': service.label,
                    'success': success,
                    'message': message
                })
            elif not status.get('loaded'):
                plist_path = str(service.file_path)
                success, message = LaunchCtlController.load(service.label, plist_path)
                results.append({
                    'service_id': service.service_id,
                    'name': service.name,
                    'label': service.label,
                    'success': success,
                    'message': message
                })

        return jsonify({
            'success': True,
            'count': len(results),
            'results': results
        })
    except Exception:
        app.logger.exception("Error starting keepalive services")
        return jsonify({
            'success': False,
            'message': 'An internal error occurred while starting services.'
        }), 500


# ---------------------------------------------------------------------------
# AI Chat API endpoints
# ---------------------------------------------------------------------------


def _build_services_summary() -> dict:
    """Build a summary of all services for the AI system prompt."""
    tree = LaunchService.get_services_tree()
    all_services = []
    namespaces = {}
    running = 0
    stopped = 0
    not_loaded = 0
    keepalive_count = 0
    scheduled_count = 0

    for schedule_type in ('scheduled', 'keepalive'):
        for namespace, services in tree[schedule_type].items():
            for service in services:
                status = LaunchCtlController.get_status(service.label)
                svc_dict = {**service.to_dict(), 'status': status}
                all_services.append(svc_dict)

                # Count by namespace
                namespaces[namespace] = namespaces.get(namespace, 0) + 1

                # Count by status
                if status.get('running'):
                    running += 1
                elif status.get('loaded'):
                    stopped += 1
                else:
                    not_loaded += 1

                # Count by type
                if schedule_type == 'keepalive':
                    keepalive_count += 1
                else:
                    scheduled_count += 1

    return {
        'total': len(all_services),
        'running': running,
        'stopped': stopped,
        'not_loaded': not_loaded,
        'keepalive_count': keepalive_count,
        'scheduled_count': scheduled_count,
        'namespaces': namespaces,
        'services': all_services,
    }


def _get_selected_service_data(service_id: str) -> dict | None:
    """Get full service data for a selected service."""
    if not service_id:
        return None
    try:
        service = LaunchService.from_service_id(service_id)
        if not service.file_path.exists():
            return None
        service = LaunchService.from_file(service.file_path)
        if service is None:
            return None
        status = LaunchCtlController.get_status(service.label)
        log_paths = service.get_log_paths()
        logs = {
            'stdout': read_log_file(log_paths.get('stdout', ''), tail=50),
            'stderr': read_log_file(log_paths.get('stderr', ''), tail=50)
        }
        return {**service.to_dict(), 'status': status, 'logs': logs}
    except (ValueError, Exception):
        return None


def _resolve_action_service_id(action_data: dict, params: dict) -> str:
    """Resolve service_id from action payload variants."""
    def _normalize(candidate: str) -> str:
        candidate = str(candidate or "").strip().strip("\"'`")
        if not candidate:
            return ""
        if ":" in candidate:
            return candidate
        return f"agent:{candidate}"

    service_id = _normalize(action_data.get("service_id", ""))
    if service_id:
        return service_id

    candidate = (
        action_data.get("service")
        or action_data.get("serviceId")
        or action_data.get("label")
        or action_data.get("service_label")
        or params.get("service_id")
        or params.get("service")
        or params.get("serviceId")
        or params.get("label")
        or params.get("service_label")
    )
    return _normalize(candidate)


def _is_confirmation_message(text: str) -> bool:
    """Detect explicit user confirmation messages."""
    normalized = re.sub(r'\s+', ' ', (text or '').strip().lower())
    normalized = re.sub(r'[.!?]+$', '', normalized)
    confirmations = {
        "yes", "y", "ok", "okay", "confirm", "confirmed", "apply", "proceed", "do it",
    }
    if normalized in confirmations:
        return True
    # Accept variants like "confirme", "confirm now", "confirm it".
    return normalized.startswith("confirm")


def _find_pending_action(messages: list[dict]) -> dict | None:
    """Return latest unresolved assistant action from chat history."""
    def _is_terminal_action_status(content: str) -> bool:
        text = str(content or "").strip().lower()
        return (
            text.startswith("action completed")
            or text.startswith("action failed")
            or "action cancelled" in text
            or "action canceled" in text
        )

    for idx in range(len(messages) - 1, -1, -1):
        msg = messages[idx]
        if msg.get("role") != "assistant":
            continue
        action = msg.get("action")
        if not isinstance(action, dict):
            continue
        own_content = str(msg.get("content", "")).strip().lower()
        if _is_terminal_action_status(own_content):
            continue

        resolved = False
        for later in messages[idx + 1:]:
            if later.get("role") != "assistant":
                continue
            content = str(later.get("content", "")).strip().lower()
            if _is_terminal_action_status(content):
                later_action = later.get("action")
                # Resolve only matching actions when payload is available.
                if isinstance(later_action, dict):
                    if later_action == action:
                        resolved = True
                        break
                    continue
                # Backward compatibility: terminal messages without action payload
                # are treated as resolving the most recent prior action.
                resolved = True
                break
        if not resolved:
            return action
    return None


_READ_ONLY_PREFIXES = (
    "show", "summarize", "summary", "what", "list", "get", "describe",
    "tell me", "how", "why", "which", "display", "view", "check",
    "status", "info", "details", "explain", "is ", "are ", "does ",
    "can you show", "can you list", "can you summarize",
)


def _looks_like_mutation_request(text: str) -> bool:
    """Best-effort detection for user requests that should produce an action."""
    normalized = re.sub(r'\s+', ' ', (text or '').strip().lower())
    normalized = re.sub(r'[.!?]+$', '', normalized)
    if any(normalized.startswith(p) for p in _READ_ONLY_PREFIXES):
        return False
    mutation_patterns = (
        r'\bstart\b', r'\bstop\b', r'\brestart\b', r'\breload\b',
        r'\bload\b', r'\bunload\b', r'\bdelete\b', r'\bremove\b',
        r'\bcreate\b', r'\brename\b', r'\bupdate\b', r'\bchange\b',
        r'\bset\b', r'\bconvert\b',
        r'\brun once\b', r'\brun now\b', r'\bscript should\b',
        r'\bchange\s+(?:the\s+)?schedule\b',
    )
    return any(re.search(p, normalized) for p in mutation_patterns)


def _response_claims_execution_without_action(text: str) -> bool:
    """Detect assistant text that claims execution while no action payload exists."""
    normalized = re.sub(r'\s+', ' ', (text or '').strip().lower())
    suspicious_prefixes = (
        "action completed", "action failed", "action in progress", "action:",
    )
    if normalized.startswith(suspicious_prefixes):
        return True
    suspicious_phrases = (
        "updated script", "created and loaded",
        "restarted ", "executed once", "deleted ",
    )
    return any(p in normalized for p in suspicious_phrases)


def _execute_chat_action(action_data: dict) -> dict:
    """Execute a confirmed chat action by calling existing MAM backend functions.

    Returns:
        {"success": bool, "message": str}
    """
    action_type = action_data.get("action", "")
    params = action_data.get("params")
    if not isinstance(params, dict):
        params = {}

    # Some LLM outputs place create/update fields at top-level instead of params.
    if not params:
        params = {
            k: v for k, v in action_data.items()
            if k not in {"action", "service_id", "params"}
        }
    service_id = _resolve_action_service_id(action_data, params)

    try:
        if action_type in ("start", "stop", "restart", "load", "unload"):
            if not service_id:
                return {"success": False, "message": "Missing service_id for control action"}
            return _execute_control_action(action_type, service_id)

        if action_type == "delete":
            if not service_id:
                return {"success": False, "message": "Missing service_id for delete action"}
            return _execute_delete_action(service_id)

        if action_type == "create":
            return _execute_create_action(params)

        if action_type in ("update_schedule", "update_script", "update_working_dir", "update_environment"):
            if not service_id:
                return {"success": False, "message": "Missing service_id for update action"}
            return _execute_update_action(action_type, service_id, params)

        if action_type == "rename":
            if not service_id:
                return {"success": False, "message": "Missing service_id for rename action"}
            return _execute_rename_action(service_id, params)

        if action_type == "convert_schedule_type":
            if not service_id:
                return {"success": False, "message": "Missing service_id for convert action"}
            return _execute_convert_action(service_id, params)

        if action_type == "start_all_keepalive":
            return _execute_start_all_keepalive()

        return {"success": False, "message": f"Unknown action type: {action_type}"}

    except Exception as exc:
        app.logger.exception("Error executing chat action: %s", action_type)
        return {"success": False, "message": f"Error: {exc}"}


def _execute_control_action(action_type: str, service_id: str) -> dict:
    """Execute start/stop/restart/load/unload."""
    service = LaunchService.from_service_id(service_id)
    if not service.file_path.exists():
        return {"success": False, "message": "Service not found"}

    plist_path = str(service.file_path)
    controller = LaunchCtlController()

    if action_type == "start":
        success, message = controller.start(service.label)
    elif action_type == "stop":
        success, message = controller.stop(service.label)
    elif action_type == "restart":
        success, message = controller.restart(service.label, plist_path)
    elif action_type == "load":
        success, message = controller.load(service.label, plist_path)
    elif action_type == "unload":
        success, message = controller.unload(service.label, plist_path)
    else:
        return {"success": False, "message": f"Invalid control action: {action_type}"}

    return {"success": success, "message": message}


def _execute_delete_action(service_id: str) -> dict:
    """Delete a service."""
    service = LaunchService.from_service_id(service_id)
    if service.file_path.exists():
        LaunchCtlController.unload(service.label, str(service.file_path))
    if service.delete():
        return {"success": True, "message": f"Deleted {service.label}"}
    return {"success": False, "message": "Failed to delete service"}


def _normalize_create_params(params: dict) -> dict:
    """Accept common AI aliases and normalize into create_from_form fields."""
    normalized = dict(params or {})

    if not normalized.get("name"):
        normalized["name"] = (
            normalized.get("service_name")
            or normalized.get("new_name")
            or normalized.get("agent_name")
            or normalized.get("label")
            or ""
        )

    if not normalized.get("category"):
        normalized["category"] = (
            normalized.get("namespace")
            or normalized.get("new_category")
            or normalized.get("service_category")
            or "other"
        )

    if not normalized.get("script_path"):
        normalized["script_path"] = (
            normalized.get("script")
            or normalized.get("command")
            or normalized.get("program")
            or ""
        )

    if not normalized.get("schedule_type"):
        normalized["schedule_type"] = normalized.get("type") or "keepalive"

    # If only a full label was provided, derive category + short name.
    label = str(normalized.get("label", "")).strip().strip("\"'`")
    if label.startswith("agent:user."):
        label = label.split("agent:", 1)[1]
    if label.startswith("user.") and "." in label:
        parts = label.split(".")
        if len(parts) >= 3:
            if not normalized.get("category") or normalized.get("category") == "other":
                normalized["category"] = parts[1]
            if not normalized.get("name") or normalized.get("name") == label:
                normalized["name"] = parts[-1]

    return normalized


def _execute_create_action(params: dict) -> dict:
    """Create a new service."""
    form_data = _normalize_create_params(params)
    service = LaunchService.create_from_form(form_data)
    if service.save():
        LaunchCtlController.load(service.label, str(service.file_path))
        return {"success": True, "message": f"Created and loaded {service.label}", "service_id": service.service_id}
    return {"success": False, "message": "Failed to save new service"}


def _execute_update_action(action_type: str, service_id: str, params: dict) -> dict:
    """Update a service attribute (schedule, script, working_dir, environment)."""
    service = LaunchService.from_service_id(service_id)
    if not service.file_path.exists():
        return {"success": False, "message": "Service not found"}

    service = LaunchService.from_file(service.file_path)
    if service is None:
        return {"success": False, "message": "Failed to load service plist"}

    if action_type == "update_schedule":
        # Build form data from params
        form_data = {"schedule_type": params.get("schedule_type", "scheduled")}
        intervals = params.get("intervals", [])
        for i, interval in enumerate(intervals):
            form_data[f"schedule_hour_{i}"] = interval.get("Hour", 0)
            form_data[f"schedule_minute_{i}"] = interval.get("Minute", 0)
        # Preserve existing script_path
        form_data["script_path"] = service.get_program()
        form_data["working_directory"] = service.get_working_directory()
        env = service.get_environment()
        form_data["environment"] = "\n".join(f"{k}={v}" for k, v in env.items()) if env else ""
        service.update_from_form(form_data)

    elif action_type == "update_script":
        form_data = {
            "script_path": params.get("script_path", ""),
            "schedule_type": service.get_schedule_type(),
            "working_directory": service.get_working_directory(),
        }
        env = service.get_environment()
        form_data["environment"] = "\n".join(f"{k}={v}" for k, v in env.items()) if env else ""
        # Preserve schedule intervals
        times = service.get_schedule_times()
        for i, t in enumerate(times):
            form_data[f"schedule_hour_{i}"] = t.get("Hour", 0)
            form_data[f"schedule_minute_{i}"] = t.get("Minute", 0)
        service.update_from_form(form_data)

    elif action_type == "update_working_dir":
        form_data = {
            "working_directory": params.get("working_directory", ""),
            "script_path": service.get_program(),
            "schedule_type": service.get_schedule_type(),
        }
        env = service.get_environment()
        form_data["environment"] = "\n".join(f"{k}={v}" for k, v in env.items()) if env else ""
        times = service.get_schedule_times()
        for i, t in enumerate(times):
            form_data[f"schedule_hour_{i}"] = t.get("Hour", 0)
            form_data[f"schedule_minute_{i}"] = t.get("Minute", 0)
        service.update_from_form(form_data)

    elif action_type == "update_environment":
        new_env = params.get("environment", {})
        env_str = "\n".join(f"{k}={v}" for k, v in new_env.items()) if isinstance(new_env, dict) else str(new_env)
        form_data = {
            "environment": env_str,
            "script_path": service.get_program(),
            "schedule_type": service.get_schedule_type(),
            "working_directory": service.get_working_directory(),
        }
        times = service.get_schedule_times()
        for i, t in enumerate(times):
            form_data[f"schedule_hour_{i}"] = t.get("Hour", 0)
            form_data[f"schedule_minute_{i}"] = t.get("Minute", 0)
        service.update_from_form(form_data)

    if service.save():
        # Reload the service
        plist_path = str(service.file_path)
        LaunchCtlController.unload(service.label, plist_path)
        LaunchCtlController.load(service.label, plist_path)
        return {"success": True, "message": f"Updated and reloaded {service.label}"}
    return {"success": False, "message": "Failed to save changes"}


def _execute_rename_action(service_id: str, params: dict) -> dict:
    """Rename a service (creates new plist, deletes old)."""
    old_service = LaunchService.from_service_id(service_id)
    if not old_service.file_path.exists():
        return {"success": False, "message": "Service not found"}

    old_service = LaunchService.from_file(old_service.file_path)
    if old_service is None:
        return {"success": False, "message": "Failed to load service plist"}

    raw_new_name = params.get("new_name", "")
    raw_new_category = params.get("new_category", old_service.namespace)
    new_name = LaunchService._normalize_form_segment(raw_new_name)
    new_category = LaunchService._normalize_form_segment(raw_new_category)
    if not new_name:
        return {"success": False, "message": "new_name is required"}

    new_label = f"user.{new_category}.{new_name}"
    try:
        LaunchService._validate_label(new_label)
    except ValueError as exc:
        return {"success": False, "message": f"Invalid rename target: {exc}"}
    if new_label == old_service.label:
        return {
            "success": True,
            "message": f"No changes needed: service already named {new_label}",
            "service_id": old_service.service_id,
        }

    # Unload old
    LaunchCtlController.unload(old_service.label, str(old_service.file_path))

    # Create new service with same data
    new_service = LaunchService(new_label, "agent")
    new_service.data = dict(old_service.data)
    new_service.data["Label"] = new_label
    # Update log paths
    new_service.data["StandardOutPath"] = f"/tmp/{new_label}.out"
    new_service.data["StandardErrorPath"] = f"/tmp/{new_label}.err"

    if new_service.save():
        old_service.delete()
        LaunchCtlController.load(new_service.label, str(new_service.file_path))
        return {"success": True, "message": f"Renamed {old_service.label} -> {new_label}", "service_id": new_service.service_id}
    return {"success": False, "message": "Failed to save renamed service"}


def _execute_convert_action(service_id: str, params: dict) -> dict:
    """Convert between KeepAlive and Scheduled."""
    service = LaunchService.from_service_id(service_id)
    if not service.file_path.exists():
        return {"success": False, "message": "Service not found"}

    service = LaunchService.from_file(service.file_path)
    if service is None:
        return {"success": False, "message": "Failed to load service plist"}

    target_type = params.get("to", "")
    if target_type not in ("keepalive", "scheduled"):
        return {"success": False, "message": "Invalid target type. Must be 'keepalive' or 'scheduled'."}

    # Clear old schedule settings
    service.data.pop("KeepAlive", None)
    service.data.pop("StartCalendarInterval", None)

    if target_type == "keepalive":
        service.data["KeepAlive"] = True
    else:
        # Default to 10:00 schedule
        service.data["StartCalendarInterval"] = [{"Hour": 10, "Minute": 0}]

    if service.save():
        plist_path = str(service.file_path)
        LaunchCtlController.unload(service.label, plist_path)
        LaunchCtlController.load(service.label, plist_path)
        return {"success": True, "message": f"Converted {service.label} to {target_type}"}
    return {"success": False, "message": "Failed to save conversion"}


def _execute_start_all_keepalive() -> dict:
    """Start all stopped KeepAlive services."""
    services = LaunchService.list_user_services()
    started = 0
    for service in services:
        if service.get_schedule_type() != 'keepalive':
            continue
        status = LaunchCtlController.get_status(service.label)
        if not status.get('running'):
            if status.get('loaded'):
                LaunchCtlController.start(service.label)
            else:
                LaunchCtlController.load(service.label, str(service.file_path))
            started += 1
    return {"success": True, "message": f"Started {started} KeepAlive agent(s)"}


@app.route('/api/chat/health')
def api_chat_health():
    """Check Ollama connectivity and model availability."""
    engine = _get_chat_engine()
    return jsonify(engine.health_check())


@app.route('/api/chat/send', methods=['POST'])
def api_chat_send():
    """Send a user message and get AI response."""
    _check_csrf()

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'error': 'Request body must be valid JSON'}), 400

    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    service_id = data.get('service_id', '')
    session_id = data.get('session_id', '')

    engine = _get_chat_engine()
    history = _get_chat_history()

    # Create session if needed
    if not session_id:
        session_id = history.generate_session_id()

    # Save user message
    history.append_message(session_id, 'user', user_message, service_id=service_id or None)

    # Server-side confirm: execute pending action even if model misses JSON action output.
    if _is_confirmation_message(user_message):
        messages = history.get_messages(session_id)
        pending_action = _find_pending_action(messages)
        if pending_action:
            result = _execute_chat_action(pending_action)
            response_text = (
                f"Action completed: {result['message']}"
                if result.get("success")
                else f"Action failed: {result['message']}"
            )
            history.append_message(
                session_id,
                'assistant',
                response_text,
                action=pending_action,
                service_id=service_id or None,
            )
            return jsonify({
                'response': response_text,
                'action': pending_action,
                'requires_confirmation': False,
                'session_id': session_id,
                'error': None,
            })

    # Get conversation context
    conversation = history.get_conversation_history(session_id, max_messages=engine.max_context)
    # Remove the last user message since send_message adds it
    if conversation and conversation[-1].get('role') == 'user':
        conversation = conversation[:-1]

    # Build services summary
    services_summary = _build_services_summary()
    selected_service = _get_selected_service_data(service_id) if service_id else None

    # Call Ollama
    result = engine.send_message(user_message, conversation, services_summary, selected_service)

    # Prevent false execution claims when no structured action exists.
    if not result.get('action'):
        response_text = str(result.get('response', '')).strip()
        if _is_confirmation_message(user_message) and _response_claims_execution_without_action(response_text):
            result['response'] = "No pending action was found to confirm. Please request the change again, then click Apply (or confirm once prompted)."
        elif _looks_like_mutation_request(user_message) and _response_claims_execution_without_action(response_text):
            result['response'] = "I couldn't execute that yet because no structured action was produced. Please retry the request; I will ask for confirmation with Apply/Cancel before any change."

    # Save assistant response
    history.append_message(
        session_id,
        'assistant',
        result['response'],
        action=result.get('action'),
        service_id=service_id or None,
    )

    return jsonify({
        'response': result['response'],
        'action': result.get('action'),
        'requires_confirmation': result.get('requires_confirmation', False),
        'session_id': session_id,
        'error': result.get('error'),
    })


@app.route('/api/chat/confirm', methods=['POST'])
def api_chat_confirm():
    """Confirm and execute a pending action."""
    _check_csrf()

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'error': 'Request body must be valid JSON'}), 400

    session_id = data.get('session_id', '')
    action_data = data.get('action')
    if not action_data:
        return jsonify({'error': 'Action data is required'}), 400

    result = _execute_chat_action(action_data)

    # Log the confirmation result
    if session_id:
        history = _get_chat_history()
        status_emoji = "completed" if result['success'] else "failed"
        history.append_message(
            session_id,
            'assistant',
            f"Action {status_emoji}: {result['message']}",
            action=action_data,
        )

    return jsonify(result)


@app.route('/api/chat/history')
def api_chat_history():
    """Retrieve chat history for a session."""
    session_id = request.args.get('session_id', '')
    if not session_id:
        return jsonify({'error': 'session_id is required'}), 400

    history = _get_chat_history()
    messages = history.get_messages(session_id)

    return jsonify({
        'session_id': session_id,
        'messages': messages,
    })


@app.route('/api/chat/sessions')
def api_chat_sessions():
    """List recent chat sessions for restore UI."""
    history = _get_chat_history()
    sessions = history.list_sessions()
    return jsonify({'sessions': sessions})


@app.route('/api/chat/clear', methods=['POST'])
def api_chat_clear():
    """Clear chat history for a session."""
    _check_csrf()

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'error': 'Request body must be valid JSON'}), 400

    session_id = data.get('session_id', '')
    if not session_id:
        return jsonify({'error': 'session_id is required'}), 400

    history = _get_chat_history()
    history.clear_session(session_id)

    return jsonify({'success': True, 'message': 'Chat history cleared'})


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------


def read_log_file(log_path, tail=50):
    """Read the last N lines of a log file, restricted to safe directories."""
    if not log_path:
        return ""

    resolved = str(Path(log_path).resolve())
    if not any(resolved.startswith(d) for d in ALLOWED_LOG_DIRS):
        return ""

    if not Path(resolved).exists():
        return ""

    try:
        with open(resolved) as f:
            last_lines = deque(f, maxlen=tail)
            return ''.join(last_lines)
    except Exception:
        app.logger.exception("Error reading log file")
        return ""


if __name__ == '__main__':
    from mac_agents_manager.cli import main
    main()
