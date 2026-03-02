# Mac Agents Manager

[![CI](https://github.com/pkasinathan/mac-agents-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/pkasinathan/mac-agents-manager/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mac-agents-manager-ai)](https://pypi.org/project/mac-agents-manager-ai/)
[![Python](https://img.shields.io/pypi/pyversions/mac-agents-manager-ai)](https://pypi.org/project/mac-agents-manager-ai/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

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

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request. This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

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

## Uninstall

### If installed via pip

```bash
pip uninstall mac-agents-manager-ai
```

### If installed as a LaunchAgent

```bash
launchctl unload ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist
rm ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist
rm -rf /path/to/mac-agents-manager   # remove the cloned repo
```

## Notes
- Default port is 8081. Override with `MAM_PORT` env var.
- If you move the project folder, re-run `install.sh` (it rebuilds the venv and refreshes the LaunchAgent paths).

## License

Apache-2.0. See [LICENSE](LICENSE) for details.
