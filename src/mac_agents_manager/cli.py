"""CLI entry point for Mac Agents Manager."""
import os


def main():
    """Start the Mac Agents Manager web server."""
    from mac_agents_manager.app import app

    port = int(os.environ.get('MAM_PORT', '8081'))
    debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true')
    print(f"\n{'=' * 60}")
    print(f"Mac Agents Manager starting on http://localhost:{port}")
    print(f"{'=' * 60}\n")
    app.run(host='127.0.0.1', port=port, debug=debug)


if __name__ == '__main__':
    main()
