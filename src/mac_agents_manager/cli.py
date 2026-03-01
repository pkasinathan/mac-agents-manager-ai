"""CLI entry point for Mac Agents Manager."""
import argparse
import os
import subprocess
import sys
from collections import deque
from pathlib import Path

from mac_agents_manager import __version__

ALLOWED_LOG_DIRS = ('/tmp/', '/private/tmp/', '/var/log/', '/private/var/log/',
                    '/var/folders/', '/private/var/folders/')


def _get_services():
    """Import and return service/controller classes (lazy to keep CLI fast)."""
    from mac_agents_manager.models import LaunchService
    from mac_agents_manager.launchctl import LaunchCtlController
    return LaunchService, LaunchCtlController


def _resolve_service(label):
    """Look up a LaunchService by its label (without the 'agent:' prefix)."""
    LaunchService, _ = _get_services()
    service_id = f"agent:{label}"
    try:
        service = LaunchService.from_service_id(service_id)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    if not service.file_path.exists():
        print(f"Error: no plist found for '{label}'", file=sys.stderr)
        sys.exit(1)
    loaded = LaunchService.from_file(service.file_path)
    if loaded is None:
        print(f"Error: could not parse plist for '{label}'", file=sys.stderr)
        sys.exit(1)
    return loaded


def cmd_serve(args):
    """Start the web server."""
    os.environ['MAM_PORT'] = str(args.port)
    from mac_agents_manager.app import app

    print(f"\n{'=' * 60}")
    print(f"Mac Agents Manager v{__version__}")
    print(f"http://localhost:{args.port}")
    print(f"{'=' * 60}\n")
    app.run(host=args.host, port=args.port, debug=args.debug)


def cmd_list(args):
    """List all agents with status."""
    LaunchService, LaunchCtlController = _get_services()
    tree = LaunchService.get_services_tree()

    for stype in ('scheduled', 'keepalive'):
        namespaces = tree.get(stype, {})
        if not namespaces:
            continue
        print(f"\n  {stype.upper()}")
        print(f"  {'─' * 56}")
        for ns, services in sorted(namespaces.items()):
            for svc in services:
                status = LaunchCtlController.get_status(svc.label)
                if status.get('running'):
                    indicator = "● running"
                elif status.get('loaded'):
                    indicator = "○ stopped"
                else:
                    indicator = "- not loaded"
                port_str = f"  :{svc.get_port()}" if svc.get_port() else ""
                print(f"  {indicator:<14} {svc.label}{port_str}")
    print()


def cmd_show(args):
    """Show agent details."""
    _, LaunchCtlController = _get_services()
    service = _resolve_service(args.label)
    status = LaunchCtlController.get_status(service.label)

    state = "running" if status.get('running') else "stopped" if status.get('loaded') else "not loaded"
    pid = status.get('pid', '-')
    port = service.get_port()

    print(f"\n  Label:      {service.label}")
    print(f"  Status:     {state} (PID {pid})")
    print(f"  Type:       {service.get_schedule_type()}")
    if port:
        print(f"  Port:       {port}")
    print(f"  Program:    {service.get_program()}")
    wd = service.get_working_directory()
    if wd:
        print(f"  WorkDir:    {wd}")
    env = service.get_environment()
    if env:
        print(f"  Env:")
        for k, v in env.items():
            print(f"    {k}={v}")
    times = service.get_schedule_times()
    if times:
        print(f"  Schedule:")
        for t in times:
            print(f"    {t.get('Hour', 0):02d}:{t.get('Minute', 0):02d}")
    logs = service.get_log_paths()
    if logs.get('stdout'):
        print(f"  Stdout:     {logs['stdout']}")
    if logs.get('stderr'):
        print(f"  Stderr:     {logs['stderr']}")
    print(f"\n  ── Plist XML ──\n")
    print(service.get_plist_xml())


def cmd_create(args):
    """Create a new agent."""
    LaunchService, _ = _get_services()

    form_data = {
        'name': args.name,
        'category': args.category,
        'script_path': args.script,
        'schedule_type': args.type,
        'working_directory': args.workdir or '',
        'environment': args.env or '',
    }
    if args.type == 'scheduled':
        for i, (h, m) in enumerate(zip(args.hour, args.minute)):
            form_data[f'schedule_hour_{i}'] = str(h)
            form_data[f'schedule_minute_{i}'] = str(m)

    try:
        service = LaunchService.create_from_form(form_data)
        if service.save():
            print(f"Created {service.label}")
            print(f"  Plist: {service.file_path}")
            print(f"  Run 'mam load {service.label}' to register with launchd")
        else:
            print("Error: failed to save plist", file=sys.stderr)
            sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _control(label, action):
    """Run a launchctl action on a service."""
    _, LaunchCtlController = _get_services()
    service = _resolve_service(label)
    plist_path = str(service.file_path)

    if action == 'load':
        ok, msg = LaunchCtlController.load(service.label, plist_path)
    elif action == 'unload':
        ok, msg = LaunchCtlController.unload(service.label, plist_path)
    elif action == 'start':
        ok, msg = LaunchCtlController.start(service.label)
    elif action == 'stop':
        ok, msg = LaunchCtlController.stop(service.label)
    elif action == 'restart':
        ok, msg = LaunchCtlController.restart(service.label, plist_path)
    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        sys.exit(1)

    print(msg)
    if not ok:
        sys.exit(1)


def cmd_load(args):
    _control(args.label, 'load')

def cmd_unload(args):
    _control(args.label, 'unload')

def cmd_start(args):
    _control(args.label, 'start')

def cmd_stop(args):
    _control(args.label, 'stop')

def cmd_restart(args):
    _control(args.label, 'restart')


def cmd_delete(args):
    """Unload and delete an agent."""
    _, LaunchCtlController = _get_services()
    service = _resolve_service(args.label)

    if not args.yes:
        answer = input(f"Delete {service.label}? [y/N] ")
        if answer.lower() != 'y':
            print("Cancelled")
            return

    LaunchCtlController.unload(service.label, str(service.file_path))
    if service.delete():
        print(f"Deleted {service.label}")
    else:
        print("Error: failed to delete plist", file=sys.stderr)
        sys.exit(1)


def cmd_start_all(args):
    """Start all stopped keepalive agents."""
    LaunchService, LaunchCtlController = _get_services()
    services = LaunchService.list_user_services()
    count = 0

    for svc in services:
        if svc.get_schedule_type() != 'keepalive':
            continue
        status = LaunchCtlController.get_status(svc.label)
        if not status.get('running') and status.get('loaded'):
            ok, msg = LaunchCtlController.start(svc.label)
            print(f"  {'✓' if ok else '✗'} {svc.label}: {msg}")
            count += 1
        elif not status.get('loaded'):
            ok, msg = LaunchCtlController.load(svc.label, str(svc.file_path))
            print(f"  {'✓' if ok else '✗'} {svc.label}: {msg}")
            count += 1

    if count == 0:
        print("All keepalive agents are already running")
    else:
        print(f"\nStarted {count} agent(s)")


def cmd_logs(args):
    """Show last N lines of agent logs."""
    service = _resolve_service(args.label)
    log_paths = service.get_log_paths()
    log_path = log_paths.get('stderr' if args.stderr else 'stdout', '')

    if not log_path:
        print(f"No {'stderr' if args.stderr else 'stdout'} log path configured", file=sys.stderr)
        sys.exit(1)

    resolved = str(Path(log_path).resolve())
    if not any(resolved.startswith(d) for d in ALLOWED_LOG_DIRS):
        print(f"Log path outside allowed directories", file=sys.stderr)
        sys.exit(1)

    if not Path(resolved).exists():
        print(f"Log file does not exist: {log_path}")
        return

    if args.follow:
        os.execvp('tail', ['tail', '-f', resolved])
    else:
        with open(resolved, 'r') as f:
            lines = deque(f, maxlen=args.lines)
        sys.stdout.write(''.join(lines))


def cmd_open(args):
    """Open the web dashboard in the default browser."""
    port = int(os.environ.get('MAM_PORT', '8081'))
    url = f"http://localhost:{port}"
    print(f"Opening {url}")
    subprocess.run(['open', url])


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog='mam',
        description='Mac Agents Manager -- manage macOS LaunchAgents from CLI or web UI',
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {__version__}',
    )
    subparsers = parser.add_subparsers(dest='command')

    # serve
    p_serve = subparsers.add_parser('serve', help='start the web server')
    p_serve.add_argument('-p', '--port', type=int,
                         default=int(os.environ.get('MAM_PORT', '8081')),
                         help='port to listen on (default: 8081)')
    p_serve.add_argument('--host', default='127.0.0.1',
                         help='host to bind to (default: 127.0.0.1)')
    p_serve.add_argument('--debug', action='store_true',
                         default=os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true'),
                         help='enable debug mode')
    p_serve.set_defaults(func=cmd_serve)

    # list
    p_list = subparsers.add_parser('list', help='list all agents with status')
    p_list.set_defaults(func=cmd_list)

    # show
    p_show = subparsers.add_parser('show', help='show agent details')
    p_show.add_argument('label', help='agent label (e.g. user.productivity.myapp)')
    p_show.set_defaults(func=cmd_show)

    # create
    p_create = subparsers.add_parser('create', help='create a new agent')
    p_create.add_argument('name', help='agent name (alphanumeric, hyphens, underscores)')
    p_create.add_argument('-c', '--category', required=True, help='category/namespace')
    p_create.add_argument('-s', '--script', required=True, help='script or command path')
    p_create.add_argument('-t', '--type', choices=['scheduled', 'keepalive'],
                          default='keepalive', help='schedule type (default: keepalive)')
    p_create.add_argument('--hour', type=int, nargs='+', default=[10],
                          help='schedule hour(s) for scheduled type (default: 10)')
    p_create.add_argument('--minute', type=int, nargs='+', default=[0],
                          help='schedule minute(s) for scheduled type (default: 0)')
    p_create.add_argument('-w', '--workdir', help='working directory')
    p_create.add_argument('-e', '--env', help='environment vars (KEY=VAL\\nKEY=VAL)')
    p_create.set_defaults(func=cmd_create)

    # load / unload / start / stop / restart
    for action, helptext in [
        ('load', 'register agent with launchd'),
        ('unload', 'unregister agent from launchd'),
        ('start', 'start a loaded agent'),
        ('stop', 'stop a running agent'),
        ('restart', 'restart an agent'),
    ]:
        p = subparsers.add_parser(action, help=helptext)
        p.add_argument('label', help='agent label')
        p.set_defaults(func={'load': cmd_load, 'unload': cmd_unload,
                             'start': cmd_start, 'stop': cmd_stop,
                             'restart': cmd_restart}[action])

    # delete
    p_delete = subparsers.add_parser('delete', help='unload and delete an agent')
    p_delete.add_argument('label', help='agent label')
    p_delete.add_argument('-y', '--yes', action='store_true', help='skip confirmation')
    p_delete.set_defaults(func=cmd_delete)

    # start-all
    p_startall = subparsers.add_parser('start-all', help='start all stopped keepalive agents')
    p_startall.set_defaults(func=cmd_start_all)

    # logs
    p_logs = subparsers.add_parser('logs', help='show agent logs')
    p_logs.add_argument('label', help='agent label')
    p_logs.add_argument('--stderr', action='store_true', help='show stderr instead of stdout')
    p_logs.add_argument('-f', '--follow', action='store_true', help='follow log output (tail -f)')
    p_logs.add_argument('-n', '--lines', type=int, default=50, help='number of lines (default: 50)')
    p_logs.set_defaults(func=cmd_logs)

    # open
    p_open = subparsers.add_parser('open', help='open web dashboard in browser')
    p_open.set_defaults(func=cmd_open)

    args = parser.parse_args()

    if args.command is None:
        # Backward compat: `mam` with no args starts the server
        args.port = int(os.environ.get('MAM_PORT', '8081'))
        args.host = '127.0.0.1'
        args.debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true')
        cmd_serve(args)
    else:
        args.func(args)


if __name__ == '__main__':
    main()
