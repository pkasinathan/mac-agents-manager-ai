# Mac Agents Manager

**Web UI and CLI for managing macOS LaunchAgents, with AI Chat powered by Ollama.**

[![CI](https://github.com/pkasinathan/mac-agents-manager-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/pkasinathan/mac-agents-manager-ai/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mac-agents-manager-ai)](https://pypi.org/project/mac-agents-manager-ai/)
[![Python](https://img.shields.io/pypi/pyversions/mac-agents-manager-ai)](https://pypi.org/project/mac-agents-manager-ai/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Mac Agents Manager lets you create, view, edit, start, stop, and reload user LaunchAgents from a web dashboard or the `mam` CLI — no manual plist editing or raw `launchctl` commands required. The dashboard includes an AI Chat mode powered by a local Ollama model for natural-language agent management.

## What's New (2.0.1)

- **AI Chat Assistant** — Natural-language control of LaunchAgents with Apply/Cancel confirmation before mutations
- **Session persistence** — Chat sessions saved to `~/.mac_agents_manager/chat/` and restorable from the session picker
- **Ollama auto-lifecycle** — Auto-start, crash recovery, and model auto-pull (same pattern as [Chronometry](https://github.com/pkasinathan/chronometry-ai))
- **Safety hardening** — Server-side confirmation resolves only unresolved matching pending actions; fallback rewrites unstructured mutation claims

## Features

- **Web Dashboard** — Modern browser UI to browse, create, edit, and control LaunchAgents on localhost
- **AI Chat Assistant** — Natural-language control with explicit Apply/Cancel confirmation before mutations
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
│   ├─ View logs                         ├─ mam logs <label>     │
│   └─ AI Chat (Ollama)                  └─ mam open             │
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
- **Ollama** — local LLM runtime (required for AI Chat)

```bash
# Install Ollama
brew install ollama

# Start Ollama as a background service (auto-starts at login)
brew services start ollama

# Pull the text model used by AI Chat
ollama pull qwen3.5:4b
```

> **Note:** If you skip Ollama setup, everything except AI Chat works normally. The chat health indicator will show "disconnected" until Ollama is available. MAM also attempts to auto-start Ollama and auto-pull the model on first chat use, but pre-installing is recommended for the best experience.

### Install

```bash
# From PyPI
pip3 install mac-agents-manager-ai

# Or with uv
uv pip install mac-agents-manager-ai

# Or in a dedicated virtual environment
mkdir -p ~/.mac_agents_manager
python3 -m venv ~/.mac_agents_manager/venv
source ~/.mac_agents_manager/venv/bin/activate
pip install mac-agents-manager-ai
```

### Run

```bash
# Install as macOS service (auto-start at login)
mam service install

# Or start manually
mam serve

# Open the dashboard
mam open
```

The dashboard is at **http://localhost:8081**.

### Verify

```bash
# Check service status
mam service status

# List all LaunchAgents
mam list

# Check version
mam --version
```

## AI Chat (Web Dashboard)

The dashboard right panel has two tabs: **IDE** (the classic editor) and **AI Chat**.

- **No service selected** — Global suggested prompts: "Summarize all services", "Service statistics", "List failed agents", etc.
- **Service selected** — Context-aware prompts: "Change schedule", "Rename", "Start", "Stop", "View logs", and all other IDE-equivalent actions.
- **Confirmation-first mutations** — The assistant proposes changes and requires Apply/Cancel before execution.
- **Safer confirmations** — Server-side confirmation only executes unresolved matching pending actions.
- **Session restore** — Chat sessions persist to `~/.mac_agents_manager/chat/` and can be resumed from the session picker.
- **Fallback safety** — If the model claims a mutation without structured action payload, the response is rewritten to a safe retry instruction.

### Ollama Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAM_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `MAM_OLLAMA_MODEL` | `qwen3.5:4b` | Model used for AI Chat |

Chat API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/health` | GET | Ollama + model readiness check |
| `/api/chat/send` | POST | Send a message and get AI response |
| `/api/chat/confirm` | POST | Apply or cancel a pending mutation |
| `/api/chat/history` | GET | Retrieve chat history for a session |
| `/api/chat/sessions` | GET | List available chat sessions |
| `/api/chat/clear` | POST | Clear chat history for a session |

## CLI Reference

```
mam                              # Start web server (default)
mam serve [-p PORT] [--debug]    # Start web server
mam service install              # Install as LaunchAgent (auto-start at login)
mam service uninstall            # Uninstall the LaunchAgent
mam service start|stop|restart   # Control the LaunchAgent service
mam service status               # Show service status
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
├── app.py            # Flask web dashboard and routes (IDE + Chat API)
├── models.py         # LaunchAgent parsing, serialization, and UI data
├── launchctl.py      # Thin wrapper around launchctl commands
├── ollama_chat.py    # Ollama lifecycle, system prompt, action parsing, chat engine
├── chat_history.py   # Chat session persistence (~/.mac_agents_manager/chat/)
├── templates/        # HTML templates (Jinja2)
└── static/           # CSS styles
```

## Runtime Directory

Chat sessions and AI state are stored in `~/.mac_agents_manager/`:

```
~/.mac_agents_manager/
├── chat/                    # Chat session history (JSON files)
│   ├── session_abc123.json  # Individual session with messages + pending actions
│   └── ...
└── venv/                    # Virtual environment (if installed per Quick Start)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAM_PORT` | `8081` | Port to listen on |
| `FLASK_DEBUG` | off | Set to `1` or `true` to enable Flask debug mode |
| `MAM_LABEL_PREFIXES` | — | Comma-separated extra label prefixes to include (e.g. `com.myorg.,com.acme.`) |
| `MAM_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `MAM_OLLAMA_MODEL` | `qwen3.5:4b` | Model used for AI Chat |

## Security

This tool binds to `127.0.0.1` only and is designed for single-user, localhost use. AI Chat mutations require explicit user confirmation. See [SECURITY.md](SECURITY.md) for the full security model and vulnerability reporting instructions.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request. This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## Development

```bash
# Clone and install in dev mode
git clone https://github.com/pkasinathan/mac-agents-manager-ai.git
cd mac-agents-manager-ai
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

## Release Process

Use the release checklist in [RELEASE.md](RELEASE.md) before publishing.

## Uninstall

```bash
mam service uninstall
pip3 uninstall mac-agents-manager-ai
```

To also remove all chat history and local data:

```bash
rm -rf ~/.mac_agents_manager
```

> **Warning:** Deleting `~/.mac_agents_manager` permanently removes all chat sessions and local configuration. This cannot be undone.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
