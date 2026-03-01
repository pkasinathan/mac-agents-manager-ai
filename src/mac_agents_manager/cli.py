"""CLI entry point for Mac Agents Manager."""
import argparse
import os

from mac_agents_manager import __version__


def main():
    """Start the Mac Agents Manager web server."""
    parser = argparse.ArgumentParser(
        prog='mam',
        description='Mac Agents Manager -- a web UI for managing macOS LaunchAgents',
    )
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=int(os.environ.get('MAM_PORT', '8081')),
        help='port to listen on (default: 8081, env: MAM_PORT)',
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='host to bind to (default: 127.0.0.1)',
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        default=os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true'),
        help='enable Flask debug mode (default: off, env: FLASK_DEBUG)',
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {__version__}',
    )
    args = parser.parse_args()

    os.environ['MAM_PORT'] = str(args.port)

    from mac_agents_manager.app import app

    print(f"\n{'=' * 60}")
    print(f"Mac Agents Manager v{__version__}")
    print(f"http://localhost:{args.port}")
    print(f"{'=' * 60}\n")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
