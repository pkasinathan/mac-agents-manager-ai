---
name: mac-agents-manager-ai
description: >
  Expert guide for the Mac Agents Manager project and its `mam` CLI — managing
  macOS LaunchAgents (create, load, start, stop, restart, delete, view logs,
  run the web dashboard). Use this skill whenever the user asks about:
  - `mam` commands or `mac-agents-manager` / `mac_agents_manager`
  - Creating, starting, stopping, restarting, or deleting LaunchAgents
  - Viewing or tailing LaunchAgent logs with `mam logs`
  - Understanding agent labels, keepalive vs scheduled agents
  - The web dashboard at localhost:8081
  - Debugging why a LaunchAgent is stopped, crashed, or not loading
  - The `MAM_LABEL_PREFIXES` environment variable or agent label namespacing
  - Working on the mac-agents-manager source code (Flask app, models, launchctl wrapper)
  Trigger on any mention of `mam`, LaunchAgent management, or mac-agents-manager,
  even if the user doesn't phrase it as a question.
---

# Mac Agents Manager — Skill Guide

## Project at a glance

Mac Agents Manager (PyPI: `mac-agents-manager-ai`) is a macOS-only tool that
wraps `launchctl` with a friendlier interface. Users interact through two
surfaces:

- **`mam` CLI** — the primary focus of this skill
- **Web dashboard** at `http://localhost:8081` (Flask, binds to `127.0.0.1`)

Source layout (Python 3.10+, Flask 3.0+):
```
src/mac_agents_manager/
├── cli.py        — argparse CLI, all subcommands
├── app.py        — Flask web app and routes
├── models.py     — LaunchService: plist parsing/creation, label validation
├── launchctl.py  — LaunchCtlController: thin subprocess wrappers
├── templates/    — Jinja2 HTML
└── static/       — CSS (Pico.css + custom)
```

---

## Label naming convention

Every agent is identified by a **dot-separated label**. `mam` creates agents
under the `user.` prefix:

```
user.<category>.<name>
```

Examples:
```
user.productivity.pomodoro-timer
user.finance.invoice-sync
user.automation.backup-photos
```

Labels are validated against `^[a-zA-Z0-9._-]+$` (max 128 chars, no `..`).

`mam list` / `mam start-all` only show agents whose label starts with `user.`
or `com.user.` by default. To expose agents from other namespaces set:
```bash
export MAM_LABEL_PREFIXES="com.myorg.,com.acme."
```

---

## Agent types

| Type | plist key | Behaviour |
|------|-----------|-----------|
| `keepalive` | `KeepAlive = true` | launchd restarts it whenever it exits |
| `scheduled` | `StartCalendarInterval` | runs once at each specified HH:MM |

Log paths are auto-generated at creation time:
```
/tmp/<label>.out   (stdout)
/tmp/<label>.err   (stderr)
```

---

## CLI reference

### Default behaviour
Running `mam` with no subcommand is equivalent to `mam serve`.

### `mam serve`
```bash
mam serve [-p PORT] [--host HOST] [--debug]
# env vars: MAM_PORT (default 8081), FLASK_DEBUG=1
```

### `mam list`
Lists all user agents grouped by type, with live status indicators:
- `● running` — process active (has PID)
- `○ stopped` — loaded in launchd but not running
- `- not loaded` — plist exists but not registered

### `mam show <label>`
Detailed view: status, PID, type, port, program, working dir, env vars,
schedule times, log paths, and raw plist XML.

### `mam create`
```bash
mam create <name> \
  -c <category> \          # required; becomes the namespace segment
  -s <script-or-cmd> \     # required; .sh → /bin/bash, .py → python3 auto-prepended
  -t keepalive|scheduled \ # default: keepalive
  [--hour H [H ...]] \     # for scheduled; default 10
  [--minute M [M ...]] \   # for scheduled; default 0
  [-w <workdir>] \
  [-e "KEY=VAL\nKEY=VAL"]
```
Creates the plist at `~/Library/LaunchAgents/<label>.plist` but does **not**
load it. Follow up with `mam load <label>`.

**Full create + activate workflow:**
```bash
mam create my-script -c automation -s /Users/me/scripts/run.sh
mam load user.automation.my-script
# For keepalive, launchd starts it automatically (RunAtLoad = true)
# For manual start:
mam start user.automation.my-script
```

### `mam load / unload <label>`
```bash
mam load user.automation.my-script    # registers plist with launchd
mam unload user.automation.my-script  # unregisters (agent stops)
```
Internally calls `launchctl load/unload <plist-path>`.

### `mam start / stop / restart <label>`
```bash
mam start user.automation.my-script
mam stop user.automation.my-script
mam restart user.automation.my-script   # stop + start (agent must be loaded)
```

### `mam delete <label> [-y]`
Unloads then removes the plist file. Prompts for confirmation unless `-y`.

### `mam start-all`
Iterates all user keepalive agents and:
- Starts any that are loaded but stopped
- Loads (and thereby starts) any that are not yet loaded
Useful after a reboot before the auto-start agent kicks in.

### `mam logs <label>`
```bash
mam logs user.automation.my-script          # last 50 lines of stdout
mam logs user.automation.my-script -f       # tail -f (follow mode)
mam logs user.automation.my-script --stderr # stderr instead of stdout
mam logs user.automation.my-script -n 200   # last 200 lines
```
Follow mode replaces the current process with `tail -f` (`os.execvp`).
The log path is validated against `ALLOWED_LOG_DIRS` to prevent traversal.

### `mam open`
Opens `http://localhost:<MAM_PORT>` in the default browser.

### `mam --version`
Prints `mam <version>`.

---

## Common workflows

### 1. Create and run a keepalive service
```bash
mam create pomodoro -c productivity -s ~/scripts/pomodoro.py -w ~/scripts
mam load user.productivity.pomodoro
mam list   # confirm ● running
```

### 2. Create a nightly scheduled job
```bash
mam create backup -c automation -s ~/scripts/backup.sh \
  -t scheduled --hour 2 --minute 30
mam load user.automation.backup
mam show user.automation.backup   # verify schedule: 02:30
```

### 3. Temporarily stop and restart
```bash
mam stop user.productivity.pomodoro
# ... do something ...
mam start user.productivity.pomodoro
```

### 4. Full teardown
```bash
mam delete user.productivity.pomodoro -y
```

### 5. View logs while debugging
```bash
mam logs user.productivity.pomodoro --stderr -n 100
mam logs user.productivity.pomodoro -f   # live follow
```

---

## Troubleshooting

**Agent shows `○ stopped` right after load**
- Check stderr for crash info: `mam logs <label> --stderr`
- Verify the script path is absolute and executable: `ls -l <script>`
- For `.py` scripts: confirm `python3` is on the PATH launchd uses
  (launchd has a minimal PATH; set `PATH` in `-e "PATH=/usr/local/bin:/usr/bin:/bin"`)

**Agent keeps restarting / crash loop (keepalive)**
- Keepalive is working as designed — but if the script exits with an error
  launchd will restart it. Check stderr logs to find the error.
- To stop the loop: `mam unload <label>`, fix the script, then `mam load` again.

**`mam list` doesn't show my agent**
- The agent label must start with `user.` or `com.user.` (or a prefix in
  `MAM_LABEL_PREFIXES`). Agents installed by system or third-party apps are
  intentionally filtered out.

**`mam logs` says "Log file does not exist"**
- The agent hasn't run yet, or it started before the plist was created via `mam`.
  Run `mam start <label>` and wait a moment, then check again.

**Port not showing in `mam list`**
- `get_port()` tries 5 strategies: live lsof → plist Description → stdout logs →
  env vars → command args. If none match, the port column is blank (not an error).

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `MAM_PORT` | `8081` | Dashboard and `mam open` target port |
| `FLASK_DEBUG` | off | Set `1` or `true` to enable Flask debug mode |
| `MAM_LABEL_PREFIXES` | — | Extra label prefixes to include in `list`/`start-all` |

---

## Development quick reference

```bash
make dev      # install in editable mode with dev deps
make test     # run pytest
make lint     # ruff check
make format   # ruff format
make check    # lint + test together
```

Key data flow for contributors:
1. `cli.py` parses args → calls `cmd_*` function
2. `cmd_*` calls `_resolve_service(label)` → returns a `LaunchService` instance
3. `LaunchService` holds parsed plist data; mutations go through `save()`
4. `LaunchCtlController` runs subprocess calls to `launchctl`; always returns
   `(bool, str)` — success flag + human-readable message
