# Mac Agents Manager

**Web UI and CLI for managing macOS LaunchAgents.**

[![CI](https://github.com/pkasinathan/mac-agents-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/pkasinathan/mac-agents-manager/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mac-agents-manager-ai)](https://pypi.org/project/mac-agents-manager-ai/)
[![Python](https://img.shields.io/pypi/pyversions/mac-agents-manager-ai)](https://pypi.org/project/mac-agents-manager-ai/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Mac Agents Manager lets you create, view, edit, start, stop, and reload user LaunchAgents from a web dashboard or the `mam` CLI — no manual plist editing or raw `launchctl` commands required.

## Features

- **Web Dashboard** — Modern browser UI to browse, create, edit, and control LaunchAgents on localhost
- **Unified CLI** — Single `mam` command for all operations (list, create, start, stop, logs, delete)
- **LaunchAgent Lifecycle** — Load, unload, start, stop, restart, and delete agents with one command
- **Agent Creation** — Create new keepalive or scheduled LaunchAgents from the CLI or web UI
- **Log Viewer** — Tail stdout/stderr logs for any agent with follow mode
- **Auto-Start** — Install Mac Agents Manager itself as a LaunchAgent so the dashboard starts at login
- **Localhost Only** — Binds to `127.0.0.1` for single-user, local-only access

## How It Works

```
┌────────────────────────────────────────────────────────────────┐
│                           Your Mac                             │
│                                                                │
│   🖥️ Web Dashboard (localhost:8081)    ⌨️ CLI (mam)            │
│   ├─ Browse all LaunchAgents           ├─ mam list             │
│   ├─ Create / Edit agents              ├─ mam create           │
│   ├─ Start / Stop / Restart            ├─ mam start <label>    │
│   └─ View logs                         └─ mam logs <label>     │
│           │                                    │               │
│           └────────────┬───────────────────────┘               │
│                        ▼                                       │
│      ┌───────────────────────────────────────────────┐         │
│      │      ~/Library/LaunchAgents/*.plist            │         │
│      │  User LaunchAgent property list files          │         │
│      └───────────────────────┬───────────────────────┘         │
│                              │                                 │
│                              ▼                                 │
│      ┌───────────────────────────────────────────────┐         │
│      │            launchctl (macOS)                   │         │
│      │  Load · Unload · Start · Stop · Status         │         │
│      └───────────────────────────────────────────────┘         │
│                                                                │
│      Everything runs locally. Nothing leaves your machine.     │
└────────────────────────────────────────────────────────────────┘

```

## Quick Start

### Prerequisites

- **macOS** (uses macOS-specific `launchctl` APIs)
- **Python 3.10+** — check with `python3 --version`. If below 3.10, install it:
  ```bash
  brew install python@3.10
  ```

### Install

```bash
# From PyPI
pip3 install mac-agents-manager-ai

# Or with uv
uv pip install mac-agents-manager-ai
```

### Run

```bash
# Start the web dashboard (default: http://localhost:8081)
mam

# Or explicitly
mam serve --port 8081
```

### Verify

```bash
# List all LaunchAgents
mam list

# Check version
mam --version
```

### Install as LaunchAgent (auto-start at login)

```bash
git clone https://github.com/pkasinathan/mac-agents-manager.git
cd mac-agents-manager
bash install.sh
```

This creates a virtual environment, installs the package, generates a plist at `~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist`, and starts the web app.

The dashboard is at **http://localhost:8081**.

## CLI Reference

```
mam                              # Start web server (default)
mam serve [-p PORT] [--debug]    # Start web server
mam list                         # List all agents with status
mam show <label>                 # Show agent details and plist XML
mam create <name> -c CAT -s SCRIPT [-t keepalive|scheduled]
mam load <label>                 # Register agent with launchd
mam unload <label>               # Unregister agent from launchd
mam start <label>                # Start a loaded agent
mam stop <label>                 # Stop a running agent
mam restart <label>              # Restart an agent
mam delete <label> [-y]          # Unload and delete an agent
mam start-all                    # Start all stopped keepalive agents
mam logs <label> [-f] [--stderr] [-n N]  # View agent logs
mam open                         # Open dashboard in browser
mam --version                    # Version info
```

## Architecture

```
src/mac_agents_manager/
├── __init__.py       # Package version
├── cli.py            # Unified CLI (argparse)
├── app.py            # Flask web dashboard and routes
├── models.py         # LaunchAgent parsing, serialization, and UI data
├── launchctl.py      # Thin wrapper around launchctl commands
├── templates/        # HTML templates (Jinja2)
└── static/           # CSS styles
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAM_PORT` | `8081` | Port to listen on |
| `FLASK_DEBUG` | off | Set to `1` or `true` to enable Flask debug mode |
| `MAM_LABEL_PREFIXES` | — | Comma-separated extra label prefixes to include (e.g. `com.myorg.,com.acme.`) |

## Security

This tool binds to `127.0.0.1` only and is designed for single-user, localhost use. See [SECURITY.md](SECURITY.md) for the full security model and vulnerability reporting instructions.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request. This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## Development

```bash
# Clone and install in dev mode
git clone https://github.com/pkasinathan/mac-agents-manager.git
cd mac-agents-manager
make dev

# Run linter
make lint

# Auto-format
make format

# Run tests
make test

# All quality checks
make check
```

## Uninstall

```bash
# If installed via pip
pip3 uninstall mac-agents-manager-ai

# If installed as a LaunchAgent
launchctl unload ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist
rm ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
