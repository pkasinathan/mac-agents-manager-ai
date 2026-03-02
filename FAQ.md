# Frequently Asked Questions

## Table of Contents

- [Getting Started](#getting-started)
- [Web Dashboard](#web-dashboard)
- [CLI](#cli)
- [LaunchAgents](#launchagents)
- [Configuration](#configuration)
- [Security](#security)
- [Development](#development)

---

## Getting Started

### What is Mac Agents Manager?

Mac Agents Manager is a web UI and CLI tool for managing macOS LaunchAgents. It lets you create, view, edit, start, stop, and reload user LaunchAgents from a browser dashboard or the `mam` command — without manually editing plist files or running raw `launchctl` commands.

### What are the prerequisites?

- **macOS** (the tool uses macOS-specific `launchctl` APIs)
- **Python 3.10+**

Install Python 3.10+ via Homebrew if needed:

```bash
brew install python@3.10
```

### How do I install Mac Agents Manager?

From PyPI:

```bash
pip3 install mac-agents-manager-ai
```

Or with uv:

```bash
uv pip install mac-agents-manager-ai
```

Or in a dedicated virtual environment:

```bash
mkdir -p ~/.mac_agents_manager
python3 -m venv ~/.mac_agents_manager/venv
source ~/.mac_agents_manager/venv/bin/activate
pip install mac-agents-manager-ai
```

### How do I start it?

Run `mam` to start the web dashboard:

```bash
mam
```

Then open **http://localhost:8081** in your browser, or run:

```bash
mam open
```

### What CLI commands are available?

| Command | Description |
|---------|-------------|
| `mam` | Start the web server (default when no subcommand given) |
| `mam serve [-p PORT] [--debug]` | Start the web server with options |
| `mam list` | List all agents with status |
| `mam show <label>` | Show agent details and plist XML |
| `mam create <name> -c CAT -s SCRIPT [-t TYPE]` | Create a new agent |
| `mam load <label>` | Register agent with launchd |
| `mam unload <label>` | Unregister agent from launchd |
| `mam start <label>` | Start a loaded agent |
| `mam stop <label>` | Stop a running agent |
| `mam restart <label>` | Restart an agent |
| `mam delete <label> [-y]` | Unload and delete an agent |
| `mam start-all` | Start all stopped keepalive agents |
| `mam logs <label> [-f] [--stderr] [-n N]` | View agent logs (`-f` follow, `--stderr` for stderr, `-n` lines) |
| `mam open` | Open the dashboard in your browser |
| `mam --version` | Show version information |

---

## Web Dashboard

### How do I access the dashboard?

Open **http://localhost:8081** in your browser, or run:

```bash
mam open
```

The web server must be running (`mam` or `mam serve`).

### What can I do on the dashboard?

The dashboard provides:

- **Agent overview** — See all LaunchAgents grouped by type (keepalive vs scheduled) with real-time status indicators
- **Agent details** — View full configuration including label, program, schedule, environment, and log paths
- **Create agents** — Form-based creation of new keepalive or scheduled LaunchAgents with environment variable support
- **Lifecycle control** — Start, stop, restart, load, and unload agents with one click
- **Log viewer** — View stdout/stderr logs for any agent directly in the browser
- **Edit agents** — Modify agent configuration and plist properties

### Can I change the port?

Yes. Set the `MAM_PORT` environment variable:

```bash
MAM_PORT=9090 mam
```

Or use the `--port` flag:

```bash
mam serve --port 9090
```

---

## CLI

### How do I create a new agent from the CLI?

Use `mam create` with a name, category, and script path:

```bash
mam create my-task -c productivity -s /path/to/script.sh
```

This creates a keepalive agent by default. For a scheduled agent:

```bash
mam create daily-backup -c maintenance -s /path/to/backup.sh -t scheduled --hour 2 --minute 0
```

After creating, register it with launchd:

```bash
mam load <label>
```

### How do I view agent logs?

```bash
mam logs <label>              # Last 50 lines of stdout
mam logs <label> -f           # Follow (tail -f) stdout
mam logs <label> --stderr     # Show stderr instead
mam logs <label> -n 100       # Last 100 lines
```

### How do I see agent details?

```bash
mam show <label>
```

This displays the agent's label, status, PID, type (keepalive/scheduled), program path, environment variables, schedule times, log paths, and the raw plist XML.

### How do I delete an agent?

```bash
mam delete <label>        # Prompts for confirmation
mam delete <label> -y     # Skip confirmation
```

This unloads the agent from launchd and removes the plist file.

---

## LaunchAgents

### What are LaunchAgents?

LaunchAgents are macOS background services that run in the user's login session. They are defined by plist (property list) files in `~/Library/LaunchAgents/` and managed by `launchctl`. They can run continuously (keepalive) or on a schedule.

### What is the difference between keepalive and scheduled agents?

| Type | Behavior |
|------|----------|
| **keepalive** | Runs continuously. If the process exits, launchd restarts it automatically. |
| **scheduled** | Runs at specific times defined by hour/minute. The process runs once and exits. |

### How do I manage the lifecycle of an agent?

```bash
mam load <label>       # Register the plist with launchd
mam start <label>      # Start a loaded agent
mam stop <label>       # Stop a running agent
mam restart <label>    # Stop and start an agent
mam unload <label>     # Unregister from launchd
mam delete <label>     # Unload and remove the plist file
```

### Where are plist files stored?

All user LaunchAgent plists are stored in `~/Library/LaunchAgents/`. Mac Agents Manager reads from and writes to this directory.

### How do I start all stopped agents at once?

```bash
mam start-all
```

This starts all keepalive agents that are loaded but not running, and loads any that are not yet registered with launchd.

---

## Configuration

### What environment variables are available?

| Variable | Default | Description |
|----------|---------|-------------|
| `MAM_PORT` | `8081` | Port the web server listens on |
| `FLASK_DEBUG` | off | Set to `1` or `true` to enable Flask debug mode |
| `MAM_LABEL_PREFIXES` | — | Comma-separated extra label prefixes to include (e.g. `com.myorg.,com.acme.`) |

### What label prefixes are shown by default?

Mac Agents Manager shows agents whose labels start with `user.`. To also show agents from other namespaces, set `MAM_LABEL_PREFIXES`:

```bash
MAM_LABEL_PREFIXES="com.myorg.,com.acme." mam
```

### How do I enable debug mode?

```bash
FLASK_DEBUG=1 mam
```

Or:

```bash
mam serve --debug
```

Debug mode enables Flask's interactive debugger and auto-reloading on code changes.

---

## Security

### Is this tool safe to use?

Mac Agents Manager is designed for single-user, localhost-only use:

- The Flask server binds exclusively to `127.0.0.1` — it is not accessible from other machines
- All state-changing endpoints require a CSRF token to prevent cross-origin attacks
- Service labels are validated against a strict character allowlist
- File paths are checked to stay within `~/Library/LaunchAgents/`
- Log file reads are restricted to known safe directories (`/tmp/`, `/var/log/`, `/var/folders/`)
- Security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`) are set on all responses

See [SECURITY.md](SECURITY.md) for the full security model and vulnerability reporting instructions.

### Does any data leave my machine?

**No.** Mac Agents Manager runs entirely locally. There are no cloud APIs, no telemetry, and no external network calls.

---

## Development

### How do I set up a development environment?

```bash
git clone https://github.com/pkasinathan/mac-agents-manager.git
cd mac-agents-manager
make dev    # Creates venv, installs runtime + dev dependencies
source venv/bin/activate
```

### How do I run tests?

```bash
make test
```

### How do I lint and format code?

```bash
make lint      # Run ruff linter
make format    # Auto-format with ruff
make check     # Run lint + tests together
```

### How do I uninstall?

```bash
pip3 uninstall mac-agents-manager-ai
rm -rf ~/.mac_agents_manager
```
