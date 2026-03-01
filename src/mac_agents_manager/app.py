"""Flask application for managing macOS LaunchAgents."""
import os
import hmac
import hashlib
from collections import deque
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from mac_agents_manager.models import LaunchService
from mac_agents_manager.launchctl import LaunchCtlController

_pkg_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
            template_folder=os.path.join(_pkg_dir, 'templates'),
            static_folder=os.path.join(_pkg_dir, 'static'))
app.secret_key = os.urandom(24)

_csrf_token = hashlib.sha256(os.urandom(32)).hexdigest()

ALLOWED_LOG_DIRS = ('/tmp/', '/var/log/', '/var/folders/')


@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "frame-ancestors 'none'"
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response


def _check_csrf():
    """Validate CSRF token on state-changing requests."""
    token = request.headers.get('X-CSRF-Token', '')
    if not hmac.compare_digest(token, _csrf_token):
        abort(403)


@app.route('/api/csrf-token')
def csrf_token():
    """Return a CSRF token for the frontend to include in state-changing requests."""
    return jsonify({'token': _csrf_token})


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
        data = request.get_json()
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


@app.route('/control/<path:service_id>/<action>', methods=['POST'])
def control(service_id, action):
    """Control a service (load, unload, start, stop, restart)."""
    _check_csrf()
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
        # Protect self-agent from being unloaded to avoid orphaning the UI
        if service.label == 'user.productivity.mac_agents_manager':
            return jsonify({'success': False, 'message': 'Unload disabled for Mac Agents Manager. Use reload.'}), 400
        success, message = controller.unload(service.label, plist_path)
    elif action == 'start':
        success, message = controller.start(service.label)
    elif action == 'stop':
        success, message = controller.stop(service.label)
    elif action == 'restart':
        # Prefer kickstart for self-agent to avoid unload/load race
        if service.label == 'user.productivity.mac_agents_manager':
            success, message = controller.kickstart(service.label)
        else:
            success, message = controller.restart(service.label, plist_path)
    else:
        return jsonify({'success': False, 'message': 'Invalid action'}), 400
    
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
        with open(resolved, 'r') as f:
            last_lines = deque(f, maxlen=tail)
            return ''.join(last_lines)
    except Exception:
        app.logger.exception("Error reading log file")
        return ""


if __name__ == '__main__':
    from mac_agents_manager.cli import main
    main()

