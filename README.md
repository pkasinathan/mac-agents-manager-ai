# Mac Agents Manager

A web UI for managing macOS LaunchAgents. Create, view, edit, start, stop, and reload user LaunchAgents from your browser.

## Install

### Option A: pip (recommended)

```bash
pip install mac-agents-manager-ai
mam
```

Then open http://localhost:8081.

### Option B: Install as a LaunchAgent (auto-start on login)

```bash
cd ~/workspace
git clone https://github.com/pkasinathan/mac-agents-manager.git
cd mac-agents-manager
bash install.sh
```

This will:
- Create a Python virtual environment in `venv/`
- Install the package in editable mode
- Generate and load a user-specific plist at `~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist`
- Start the web app at http://localhost:8081

### Option C: Run from source

```bash
git clone https://github.com/pkasinathan/mac-agents-manager.git
cd mac-agents-manager
python3 -m venv venv
source venv/bin/activate
pip install -e .
mam
```

## Project Structure

```
src/mac_agents_manager/
    __init__.py         Package version
    app.py              Flask app and routes
    cli.py              CLI entry point (mam command)
    models.py           LaunchAgent parsing, serialization, and UI data
    launchctl.py        Thin wrapper around launchctl commands
    templates/          HTML templates
    static/             CSS styles
```

- `install.sh` -- Creates venv, installs package, installs/loads LaunchAgent
- `start_mac_agents_manager.sh` -- Start script used by the LaunchAgent
- `pyproject.toml` -- Package metadata for PyPI

## Common Commands

Unload / reload the app agent:
```bash
launchctl unload ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist
launchctl load   ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist
```

Or use the Makefile:
```bash
make stop
make start
make logs
```

## Environment Variables

| Variable | Description |
|---|---|
| `FLASK_DEBUG` | Set to `1` or `true` to enable Flask debug mode (default: off) |
| `MAM_PORT` | Port to listen on (default: `8081`) |
| `MAM_LABEL_PREFIXES` | Comma-separated extra label prefixes to include (e.g. `com.myorg.,com.acme.`) |

## Security

This tool binds to `127.0.0.1` only and is designed for single-user, localhost use. See [SECURITY.md](SECURITY.md) for the full security model and vulnerability reporting instructions.

## Development

```bash
git clone https://github.com/pkasinathan/mac-agents-manager.git
cd mac-agents-manager
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
make lint
make test
```

## Notes
- Default port is 8081. Override with `MAM_PORT` env var.
- If you move the project folder, re-run `install.sh` (it rebuilds the venv and refreshes the LaunchAgent paths).

## License

Apache-2.0. See [LICENSE](LICENSE) for details.
