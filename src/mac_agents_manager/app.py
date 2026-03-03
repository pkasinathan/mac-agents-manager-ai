"""Flask application for managing macOS LaunchAgents."""
import hashlib
import hmac
import os
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
        "frame-ancestors 'none'"
    )
    response.headers['Content-Security-Policy'] = csp
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    allowed_origins = {f'http://localhost:{port}', f'http://127.0.0.1:{port}'}
    origin = request.headers.get('Origin', '')
    if origin and origin not in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = ''
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


def _execute_chat_action(action_data: dict) -> dict:
    """Execute a confirmed chat action by calling existing MAM backend functions.

    Returns:
        {"success": bool, "message": str}
    """
    action_type = action_data.get("action", "")
    service_id = action_data.get("service_id", "")
    params = action_data.get("params", {})

    try:
        if action_type in ("start", "stop", "restart", "load", "unload"):
            return _execute_control_action(action_type, service_id)

        if action_type == "delete":
            return _execute_delete_action(service_id)

        if action_type == "create":
            return _execute_create_action(params)

        if action_type in ("update_schedule", "update_script", "update_working_dir", "update_environment"):
            return _execute_update_action(action_type, service_id, params)

        if action_type == "rename":
            return _execute_rename_action(service_id, params)

        if action_type == "convert_schedule_type":
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


def _execute_create_action(params: dict) -> dict:
    """Create a new service."""
    service = LaunchService.create_from_form(params)
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

    new_name = params.get("new_name", "")
    new_category = params.get("new_category", old_service.namespace)
    if not new_name:
        return {"success": False, "message": "new_name is required"}

    new_label = f"user.{new_category}.{new_name}"

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
