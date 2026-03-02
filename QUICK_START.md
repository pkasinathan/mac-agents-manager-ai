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
mam
```

This starts the web dashboard at **http://localhost:8081**.

## 3. Open Dashboard

```bash
mam open
```

Or visit **http://localhost:8081** in your browser.

## Useful Commands

```bash
mam list              # List all agents with status
mam show <label>      # Show agent details
mam start <label>     # Start an agent
mam stop <label>      # Stop an agent
mam logs <label> -f   # Follow agent logs
mam create <name> -c <category> -s <script>  # Create a new agent
mam --version         # Show version
```
