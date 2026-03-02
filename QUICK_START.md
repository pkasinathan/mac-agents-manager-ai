# Mac Agents Manager Quick Start

## 1. Install

```bash
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

## 4. Auto-Start at Login (optional)

```bash
git clone https://github.com/pkasinathan/mac-agents-manager.git
cd mac-agents-manager
bash install.sh
```

This installs Mac Agents Manager as a LaunchAgent so the dashboard starts automatically when you log in.

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
