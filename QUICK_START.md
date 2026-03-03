# Mac Agents Manager Quick Start

## 1. Install

```bash
pip3 install mac-agents-manager-ai
```

Or in a dedicated virtual environment:

```bash
mkdir -p ~/.mac_agents_manager
python3 -m venv ~/.mac_agents_manager/venv
source ~/.mac_agents_manager/venv/bin/activate
pip install mac-agents-manager-ai
```

## 2. Install Ollama (for AI Chat)

```bash
# Install Ollama
brew install ollama

# Start Ollama as a background service (auto-starts at login)
brew services start ollama

# Pull the text model used by AI Chat
ollama pull qwen3.5:4b
```

> **Note:** If you skip this step, everything except AI Chat works normally. MAM also attempts to auto-start Ollama and auto-pull the model on first chat use.

## 3. Start

```bash
mam service install
```

This installs Mac Agents Manager as a LaunchAgent that auto-starts at login.

## 4. Open Dashboard

```bash
mam open
```

Or visit **http://localhost:8081** in your browser.

## 5. Use AI Chat (Optional)

In the dashboard, switch to the **AI Chat** tab to manage agents with natural language.
Mutations require explicit **Apply/Cancel** confirmation before execution.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAM_PORT` | `8081` | Port to listen on |
| `MAM_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `MAM_OLLAMA_MODEL` | `qwen3.5:4b` | Model used for AI Chat |

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
