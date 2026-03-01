# Mac Agents Manager

A simple web UI for managing macOS LaunchAgents. Create, view, edit, start, stop, and reload user LaunchAgents from your browser.

## Quick Start

1) Install and start as a user LaunchAgent

```bash
cd ~/workspace
git clone https://github.com/pkasinathan/mac_agents_manager.git
cd mac_agents_manager
bash install.sh
```

This will:
- Create a Python virtual environment in `venv/`
- Install dependencies from `requirements.txt`
- Generate and load a user-specific plist at `~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist` (with correct paths and env vars)
- Start the web app at http://localhost:8081

2) Open the UI

- Visit http://localhost:8081

## Project Structure

- `app.py`: Flask app entrypoint and routes
- `models.py`: LaunchAgent parsing, serialization, and UI data
- `launchctl.py`: Thin wrapper around `launchctl` commands
- `templates/` and `static/`: Web UI
- `start_mac_agents_manager.sh`: Starts the app (used by the LaunchAgent)
- `install.sh`: Creates venv, installs deps, installs/loads LaunchAgent
- `requirements.txt`: Python dependencies

## Common Commands

Unload / reload the app agent:
```bash
launchctl unload ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist
launchctl load   ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist
```

Logs:
```bash
# App stdout / stderr
tail -f /tmp/mac_agents_manager.out
tail -f /tmp/mac_agents_manager.err
```

Run locally without LaunchAgent:
```bash
cd ~/workspace
git clone https://github.com/pkasinathan/mac_agents_manager.git
cd mac_agents_manager
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Environment Variables

| Variable | Description |
|---|---|
| `FLASK_DEBUG` | Set to `1` or `true` to enable Flask debug mode (default: off) |
| `MAM_LABEL_PREFIXES` | Comma-separated extra label prefixes to include (e.g. `com.myorg.,com.acme.`) |

## Security

This tool binds to `127.0.0.1` only and is designed for single-user, localhost use. See [SECURITY.md](SECURITY.md) for the full security model and vulnerability reporting instructions.

## Notes
- Default port is 8081. To change it, update the hardcoded port in `app.py` and any references in `install.sh`.
- If you move the project folder, re-run `install.sh` (it rebuilds the venv and refreshes the LaunchAgent paths).

## License

Apache-2.0. See [LICENSE](LICENSE) for details.
