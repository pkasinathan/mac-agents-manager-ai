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
python3.10 -m venv ~/.mam-venv
source ~/.mam-venv/bin/activate
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

## LaunchAgent not starting

### Symptoms

- Running `bash install.sh` completes but the dashboard is not accessible at http://localhost:8081
- `mam list` shows the agent as "not loaded" or "stopped"
- `launchctl load` returns an error

### Cause

Common causes:

- The plist file references a stale virtual environment path (e.g. the project folder was moved)
- The `scripts/start.sh` file is not executable
- Python or the `mam` command is not found inside the virtual environment

### Fix

#### Step 1: Check the agent status

```bash
launchctl list | grep mac_agents_manager
```

If nothing is returned, the agent is not loaded.

#### Step 2: Re-run the install script

If you moved the project folder or recreated the virtual environment:

```bash
cd /path/to/mac-agents-manager
bash install.sh
```

This rebuilds the virtual environment and generates a new plist with the correct paths.

#### Step 3: Check logs

```bash
cat /tmp/mac_agents_manager.out
cat /tmp/mac_agents_manager.err
```

These files contain stdout and stderr output from the LaunchAgent process.

#### Step 4: Verify manually

```bash
cd /path/to/mac-agents-manager
source venv/bin/activate
mam
```

If this works, the issue is with the plist paths. Re-run `install.sh` to regenerate them.
