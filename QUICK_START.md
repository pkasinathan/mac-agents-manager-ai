# Mac Agents Manager Quick Start

## 1. Install

```bash
pip install mac-agents-manager-ai
```

Or in a dedicated virtual environment:

```bash
mkdir -p ~/.mac_agents_manager
python3 -m venv ~/.mac_agents_manager/venv
source ~/.mac_agents_manager/venv/bin/activate
pip install mac-agents-manager-ai
```

## 2. Start

```bash
mam service install
```

This installs Mac Agents Manager as a LaunchAgent that auto-starts at login.

## 3. Open Dashboard

```bash
mam open
```

Or visit **http://localhost:8081** in your browser.

## 4. Use AI Chat (Optional)

In the dashboard, switch to **AI Chat** mode to manage agents with natural language.
Mutations require explicit **Apply/Cancel** confirmation before execution.

## Useful Commands

```bash
mam service status    # Check service status
mam service stop      # Stop the service
mam service start     # Start the service
mam service restart   # Restart the service
mam list              # List all agents with status
mam show <label>      # Show agent details
mam start <label>     # Start an agent
mam stop <label>      # Stop an agent
mam logs <label> -f   # Follow agent logs
mam create <name> -c <category> -s <script>  # Create a new agent
mam --version         # Show version
```
