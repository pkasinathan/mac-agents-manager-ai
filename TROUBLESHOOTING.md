# Troubleshooting

## `pip: command not found`

### Symptoms

- Running `pip install mac-agents-manager-ai` returns `pip: command not found` or `zsh: command not found: pip`

### Cause

Modern macOS (Homebrew Python 3.12+) and many Linux distributions no longer provide a bare `pip` command. Only `pip3` or `python3 -m pip` is available.

### Fix

Use `pip3` instead:

```bash
pip3 install mac-agents-manager-ai
```

Or use `python3 -m pip`:

```bash
python3 -m pip install mac-agents-manager-ai
```

---

## Python 3.10+ not installed

### Symptoms

- `python3 --version` shows a version below 3.10, or `python3: command not found`
- Installing mac-agents-manager fails with a Python version error

### Fix

Install Python 3.10+ via Homebrew (recommended on macOS):

```bash
brew install python@3.10
```

After installation, it's available as `python3.10` and `pip3.10`. Create a virtual environment:

```bash
mkdir -p ~/.mac_agents_manager
python3.10 -m venv ~/.mac_agents_manager/venv
source ~/.mac_agents_manager/venv/bin/activate
pip install mac-agents-manager-ai
```

Alternatively, use **pyenv** to manage multiple Python versions:

```bash
brew install pyenv
pyenv install 3.10
pyenv global 3.10
pip install mac-agents-manager-ai
```

Or use **uv** (fastest):

```bash
uv python install 3.10
uv pip install mac-agents-manager-ai
```

---

## Port 8081 already in use

### Symptoms

- Starting `mam` fails with `Address already in use` or `OSError: [Errno 48] Address already in use`

### Cause

Another process is already listening on port 8081. This could be another instance of Mac Agents Manager or a different application.

### Fix

#### Option 1: Use a different port

```bash
MAM_PORT=9090 mam
```

#### Option 2: Find and stop the conflicting process

```bash
lsof -i :8081
```

This shows the process using port 8081. Kill it if appropriate:

```bash
kill <PID>
```

#### Option 3: If it's a stale LaunchAgent

```bash
launchctl unload ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist
mam
```

---

## `mam: command not found` after install

### Symptoms

- Running `mam` returns `zsh: command not found: mam`
- `pip install mac-agents-manager-ai` completed successfully

### Cause

If you installed into a virtual environment, the `mam` command is only available when that environment is activated. If you installed globally, the install directory may not be on your `PATH`.

### Fix

#### If installed in a virtual environment

Activate the environment first:

```bash
source ~/.mac_agents_manager/venv/bin/activate
mam
```

#### If installed globally

Check where pip installed the script:

```bash
python3 -m pip show mac-agents-manager-ai
```

Ensure the `bin/` directory from the install location is on your `PATH`. On macOS with Homebrew Python, this is typically `~/Library/Python/3.x/bin/` or `/opt/homebrew/bin/`.

---

## AI Chat says "No pending action was found to confirm"

### Symptoms

- You type `confirm`/`yes` and chat responds with: "No pending action was found to confirm..."

### Cause

There is no unresolved pending mutation in the current session. The prior action may already be completed/canceled, or the model response did not include a structured action payload.

### Fix

1. Re-issue the desired mutation request.
2. Wait for an action preview with Apply/Cancel.
3. Click Apply (or confirm) on that fresh preview.
4. Verify you are in the expected chat session from the session selector.

---

## AI Chat not responding / Ollama unavailable

### Symptoms

- Chat health indicator is not ready
- Messages fail with Ollama connectivity/model errors

### Cause

Ollama is not installed/running, or the configured model is not available locally.

### Fix

1. Ensure Ollama is installed:

```bash
brew install ollama
```

2. Start Ollama manually (optional; MAM also attempts auto-start):

```bash
ollama serve
```

3. Pull the model used by MAM (default: `qwen3.5:4b`):

```bash
ollama pull qwen3.5:4b
```

4. If you use custom settings, verify:

```bash
echo "$MAM_OLLAMA_MODEL"
echo "$MAM_OLLAMA_BASE_URL"
```

---

## Rename appears to do nothing

### Symptoms

- Rename returns success, but label/file do not change.

### Cause

The requested rename resolves to the same final label (`user.<category>.<name>`). This is intentionally treated as a safe no-op.

### Fix

- Confirm the requested `new_name`/`new_category` differ from the current label.
- Use `mam show <label>` or the dashboard details to verify current label before renaming.
