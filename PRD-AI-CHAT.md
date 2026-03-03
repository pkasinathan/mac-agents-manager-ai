# PRD: AI Chat for Mac Agents Manager

| Field | Value |
|-------|-------|
| **Author** | Prabhu Kasinathan |
| **Version** | 1.0 |
| **Status** | Draft |
| **Target Release** | v2.0.0 |
| **Date** | 2025-07-13 |

---

## Implementation Notes (Current)

This PRD is the original design proposal. Current implementation includes these notable deltas/updates:

- Added `GET /api/chat/sessions` for session restore UI.
- Chat input is multiline (`textarea`) with Enter-to-send, Shift+Enter newline, and auto-resize behavior.
- Added server-side confirm fallback in `POST /api/chat/send` to execute unresolved pending actions when the user sends explicit confirmation text.
- Added safeguards to block model responses that claim mutation execution without a structured `action` payload.
- Pending-action resolution now matches terminal statuses to the same action payload to avoid resolving unrelated actions.
- Rename action normalizes/validates target label segments and safely no-ops when renaming to the same label.

## 1. Overview

Add a conversational AI Chat interface to Mac Agents Manager (MAM), powered by Ollama `qwen3.5:4b`, that provides natural-language access to **every IDE capability**. The right panel gains two tabs — *IDE* (existing layout, untouched) and *AI Chat* (new). Chat context adapts dynamically based on whether a service is selected in the left sidebar tree.

---

## 2. Problem Statement

MAM's IDE interface requires users to understand plist structure, form fields, and button actions. For quick operations (rename, change schedule, view stats) users must navigate forms and menus manually. A chat interface lowers the barrier — users describe intent in plain English and the AI executes it, with a preview + confirm step before any mutation.

---

## 3. Goals

| # | Goal |
|---|------|
| G1 | Add AI Chat tab alongside existing IDE tab — zero changes to IDE |
| G2 | All IDE actions available via chat (create, edit, rename, schedule, start, stop, restart, delete, etc.) |
| G3 | Context-aware suggested prompts (global vs. service-specific) |
| G4 | Ollama `qwen3.5:4b` with auto-start + crash recovery (chronometry pattern) |
| G5 | Chat history persisted to `~/.mac_agents_manager/chat/` |
| G6 | Preview + Confirm before any mutation (never auto-apply) |
| G7 | Non-streaming responses (wait for full response, then display) |

---

## 4. Non-Goals

| # | Non-Goal |
|---|----------|
| N1 | Mobile-responsive layout (not in scope for this PRD) |
| N2 | Multi-turn planning / Claude Code delegation (Ollama does everything) |
| N3 | Voice input |
| N4 | Streaming token-by-token display |

---

## 5. User Experience

### 5.1 Tab Switching

The right panel gets two tabs at the top-right corner:

```
┌─────────────────────────────────────────────────────────┐
│  [Service Name]                    [ IDE ] [ AI Chat ]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  (content area switches based on active tab)            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

- **IDE tab** → Shows the existing editor-top (form) + editor-bottom (plist/stdout/stderr). No changes.
- **AI Chat tab** → Replaces the entire right content area with a chat window.

Switching tabs preserves state on both sides. Going from Chat → IDE and back keeps chat history intact.

### 5.2 Chat Window Layout

```
┌─────────────────────────────────────────────────────────┐
│  Suggested Prompts (horizontal scroll chips)            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Chat Messages (scrollable, newest at bottom)           │
│                                                         │
│  🤖 Welcome! I can help manage your LaunchAgents.       │
│     Select a service or ask me anything.                │
│                                                         │
│  👤 Show me service statistics                          │
│                                                         │
│  🤖 Here's an overview of your services:                │
│     • Total: 24 agents                                  │
│     • Running: 18 | Stopped: 4 | Not Loaded: 2         │
│     • KeepAlive: 15 | Scheduled: 9                     │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [ Type a message...                        ] [ Send ]  │
└─────────────────────────────────────────────────────────┘
```

### 5.3 Suggested Prompts

Prompts are displayed as clickable chips above the chat area. They change dynamically based on context.

#### When NO service is selected (Global Context)

| Chip Label | What It Does |
|------------|-------------|
| 📊 Summarize all services | Full summary of all agents — counts, status breakdown |
| 📈 Service statistics | Running/stopped/loaded stats per namespace |
| 🚀 Start all KeepAlive | Start all stopped KeepAlive agents |
| 🔍 Find failing services | List agents with errors in stderr logs |
| 📝 List all scheduled agents | Show all scheduled agents with their cron times |
| ➕ Create new agent | Guided agent creation via chat |
| 🏷️ List namespaces | Show all namespaces and their agent counts |

#### When a service IS selected (Service Context)

| Chip Label | What It Does |
|------------|-------------|
| ℹ️ Summarize this service | Show label, status, schedule, logs summary |
| 📅 Change schedule | Modify the cron schedule (hour/minute) |
| ✏️ Rename | Rename the agent (changes label + plist filename) |
| 🔄 Change script path | Update the ProgramArguments |
| 📂 Change working directory | Update WorkingDirectory |
| 🌍 Edit environment variables | Add/update/remove env vars |
| ▶️ Start | Start the service |
| ⏹️ Stop | Stop the service |
| 🔁 Restart / Reload | Restart the service |
| 📥 Load | Load into launchd |
| 📤 Unload | Unload from launchd |
| 📄 Show plist | Display the raw plist XML |
| 📋 Show stdout logs | Display recent stdout |
| 🚨 Show stderr logs | Display recent stderr |
| 🗑️ Delete | Delete the agent (with confirmation) |
| 🔀 Convert to KeepAlive | Convert scheduled → keepalive |
| 🔀 Convert to Scheduled | Convert keepalive → scheduled |

### 5.4 Mutation Flow (Preview + Confirm)

All state-changing operations follow a 3-step pattern:

```
User: "Change the schedule to run at 8am and 6pm"

🤖 AI: Here's what I'll change for `user.finance.reconcile`:

   Current schedule:
   • Hour: 10, Minute: 0

   Proposed schedule:
   • Hour: 8, Minute: 0
   • Hour: 18, Minute: 0

   [ Apply ✅ ]  [ Cancel ❌ ]

User: clicks [ Apply ✅ ]

🤖 AI: ✅ Schedule updated for `user.finance.reconcile`.
       The agent has been reloaded to pick up the changes.
```

- The AI generates the proposed change and presents a diff/comparison
- User must click **Apply** to execute
- **Cancel** discards the proposed change
- After Apply, the AI calls the existing MAM backend APIs (`/api/save/`, `/control/`) to make the change

### 5.5 Tab Behavior & Context Sync

| Event | Behavior |
|-------|----------|
| Click service in left tree → AI Chat active | Chat receives context update; suggested prompts change to service-specific |
| Click service in left tree → IDE active | IDE loads service as today (no change) |
| Switch IDE → AI Chat | Chat panel shows; if service selected, service context loads |
| Switch AI Chat → IDE | IDE panel shows; if service was selected, IDE shows it |
| Select different service while in AI Chat | Chat adds a system message "Now viewing: [label]"; suggested prompts update |
| Deselect service (click welcome area) | Chat reverts to global prompts |

---

## 6. Architecture

### 6.1 System Diagram

```
┌──────────────┐     ┌──────────────────────┐     ┌─────────────┐
│   Browser     │────▸│  Flask Backend (MAM)  │────▸│   Ollama     │
│   (JS Chat)   │◂────│  /api/chat/*          │◂────│  qwen3.5:4b  │
└──────────────┘     └──────────────────────┘     └─────────────┘
       │                       │
       │                       ├── /api/services (existing)
       │                       ├── /api/service/<id> (existing)
       │                       ├── /api/save/<id> (existing)
       │                       ├── /control/<id>/<action> (existing)
       │                       │
       │                       ├── /api/chat/send (NEW)
       │                       ├── /api/chat/history (NEW)
       │                       ├── /api/chat/clear (NEW)
       │                       └── /api/chat/health (NEW)
       │
       └── localStorage (tab state, scroll position)
```

### 6.2 New Backend Module: `ollama_chat.py`

A new module at `src/mac_agents_manager/ollama_chat.py` encapsulates all Ollama interaction.

```python
# Key components:
class OllamaChatEngine:
    """Manages Ollama lifecycle and chat conversations."""

    def __init__(self, model="qwen3.5:4b", base_url="http://localhost:11434"):
        ...

    def ensure_running(self) -> bool:
        """Auto-start Ollama if not running (chronometry pattern)."""

    def send_message(self, user_message: str, context: dict) -> dict:
        """Send message with service context, return AI response."""

    def build_system_prompt(self, context: dict) -> str:
        """Build system prompt with current MAM state."""
```

#### Ollama Lifecycle (borrowed from chronometry)

| Feature | Implementation |
|---------|---------------|
| Auto-start | `ensure_ollama_running()` — checks health, finds binary, spawns `ollama serve` |
| Health check | `GET http://localhost:11434` returns 200 |
| Crash recovery | On 500 "no longer running" → `pkill ollama` + restart |
| Model auto-pull | On 404 → `POST /api/pull` with model name |
| Binary discovery | `shutil.which("ollama")` → `/opt/homebrew/bin/ollama` → `/usr/local/bin/ollama` |
| Start timeout | 30 seconds |

#### System Prompt Design

The system prompt dynamically includes MAM's current state so the model can reason about services:

```
You are the AI assistant for Mac Agents Manager (MAM).
You help users manage macOS LaunchAgents through natural language.

AVAILABLE ACTIONS:
- summarize: Get status summaries and statistics
- modify: Change schedule, script path, working directory, environment variables, label/name
- control: start, stop, restart, load, unload, delete
- create: Create new agents
- query: View plist XML, stdout/stderr logs

CURRENT STATE:
{service_list_json}

SELECTED SERVICE:
{selected_service_json_or_none}

RULES:
1. For any modification, output a JSON block with action type and parameters.
   Format: ```json\n{"action": "...", "params": {...}}\n```
2. Never apply changes directly. Always present what you'll change and wait for user confirmation.
3. For read-only queries (summarize, logs, plist), respond directly with the information.
4. Be concise and technical. This user is an expert.
5. Use the service data provided — do not guess or hallucinate service names/labels.
```

#### Action Response Parsing

The backend parses AI responses for structured action blocks:

```python
import re, json

def parse_ai_response(response_text: str) -> dict:
    """Extract action JSON from AI response if present."""
    pattern = r'```json\s*(\{.*?\})\s*```'
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        action = json.loads(match.group(1))
        return {
            "type": "action",
            "action": action,
            "message": re.sub(pattern, '', response_text).strip()
        }
    return {
        "type": "info",
        "message": response_text
    }
```

### 6.3 New API Endpoints

#### `POST /api/chat/send`

Send a user message and get AI response.

**Request:**
```json
{
  "message": "Change the schedule to 8am and 6pm",
  "service_id": "agent:user.finance.reconcile",
  "session_id": "abc123"
}
```

- `service_id`: Optional. If provided, enriches the system prompt with that service's full data.
- `session_id`: Chat session identifier. Used for history persistence.

**Response:**
```json
{
  "response": "Here's what I'll change...",
  "action": {
    "type": "update_schedule",
    "service_id": "agent:user.finance.reconcile",
    "params": {
      "schedule_type": "scheduled",
      "intervals": [
        {"Hour": 8, "Minute": 0},
        {"Hour": 18, "Minute": 0}
      ]
    }
  },
  "requires_confirmation": true,
  "session_id": "abc123"
}
```

- `action`: Extracted from AI response. `null` if informational only.
- `requires_confirmation`: `true` for mutations, `false` for queries.

#### `POST /api/chat/confirm`

Confirm and execute a pending action.

**Request:**
```json
{
  "session_id": "abc123",
  "action": {
    "type": "update_schedule",
    "service_id": "agent:user.finance.reconcile",
    "params": {
      "schedule_type": "scheduled",
      "intervals": [
        {"Hour": 8, "Minute": 0},
        {"Hour": 18, "Minute": 0}
      ]
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Schedule updated for user.finance.reconcile. Agent reloaded."
}
```

The backend maps action types to existing MAM functions:

| Action Type | MAM Backend Call |
|------------|------------------|
| `update_schedule` | `LaunchService.update_from_form()` + `save()` + reload |
| `update_script` | `LaunchService.update_from_form()` + `save()` |
| `update_working_dir` | `LaunchService.update_from_form()` + `save()` |
| `update_environment` | `LaunchService.update_from_form()` + `save()` |
| `rename` | Create new plist with new label, delete old, reload |
| `start` | `LaunchCtlController.start()` |
| `stop` | `LaunchCtlController.stop()` |
| `restart` | `LaunchCtlController.restart()` |
| `load` | `LaunchCtlController.load()` |
| `unload` | `LaunchCtlController.unload()` |
| `delete` | `LaunchCtlController.unload()` + `LaunchService.delete()` |
| `create` | `LaunchService.create_from_form()` + `save()` + load |
| `convert_schedule_type` | Modify plist data (KeepAlive ↔ StartCalendarInterval) + save + reload |

#### `GET /api/chat/history?session_id=abc123`

Retrieve persisted chat history for a session.

**Response:**
```json
{
  "session_id": "abc123",
  "messages": [
    {"role": "user", "content": "Show me stats", "timestamp": "2025-07-13T10:30:00"},
    {"role": "assistant", "content": "Here are your stats...", "timestamp": "2025-07-13T10:30:02"}
  ]
}
```

#### `POST /api/chat/clear`

Clear chat history for a session.

**Request:**
```json
{
  "session_id": "abc123"
}
```

#### `GET /api/chat/health`

Check Ollama connectivity and model availability.

**Response:**
```json
{
  "ollama_running": true,
  "model_loaded": true,
  "model_name": "qwen3.5:4b",
  "base_url": "http://localhost:11434"
}
```

### 6.4 Chat History Persistence

| Aspect | Design |
|--------|--------|
| Storage path | `~/.mac_agents_manager/chat/` |
| File format | JSON — one file per session: `{session_id}.json` |
| Session ID | Generated on first chat open: `chat_{YYYYMMDD}_{HHMMSS}_{random4}` |
| Max messages per session | 200 (oldest trimmed for Ollama context window) |
| Retention | 30 days, auto-cleanup on startup |
| Ollama context | Last 20 messages sent as conversation history |
| What's stored | `role`, `content`, `timestamp`, `action` (if any), `service_id` (if any) |

File structure:
```
~/.mac_agents_manager/
├── chat/
│   ├── chat_20250713_103000_a1b2.json
│   ├── chat_20250713_143000_c3d4.json
│   └── ...
└── logs/
    └── (existing)
```

### 6.5 Frontend Design

#### Tab Implementation

Modify `index.html` — add mode tabs to `editor-header`:

```html
<div class="editor-header" id="editor-header">
    <div class="editor-title" id="editor-title">Service Editor</div>
    <div class="editor-mode-tabs">
        <button class="mode-tab active" data-mode="ide" onclick="switchMode('ide')">IDE</button>
        <button class="mode-tab" data-mode="chat" onclick="switchMode('chat')">AI Chat</button>
    </div>
    <div class="editor-actions" id="ide-actions">
        <!-- existing buttons (only shown in IDE mode) -->
    </div>
</div>
```

#### Chat Panel HTML

```html
<div id="chat-panel" class="chat-panel hidden">
    <!-- Suggested Prompts -->
    <div class="chat-suggestions" id="chat-suggestions">
        <!-- Dynamically populated chips -->
    </div>

    <!-- Messages -->
    <div class="chat-messages" id="chat-messages">
        <div class="chat-message assistant">
            <span class="chat-avatar">🤖</span>
            <div class="chat-bubble">Welcome! I can help manage your LaunchAgents. Select a service or ask me anything.</div>
        </div>
    </div>

    <!-- Input -->
    <div class="chat-input-area">
        <input type="text" id="chat-input" placeholder="Type a message..." autocomplete="off">
        <button id="chat-send" onclick="sendChatMessage()">Send</button>
    </div>
</div>
```

#### CSS Additions

New styles added to `style.css`:

- `.editor-mode-tabs` — Tab bar in the header (IDE | AI Chat)
- `.mode-tab` / `.mode-tab.active` — Individual tab buttons
- `.chat-panel` — Full-height flex container replacing editor-top + editor-bottom
- `.chat-suggestions` — Horizontal scrollable chip container
- `.suggestion-chip` — Individual clickable chip
- `.chat-messages` — Scrollable message area
- `.chat-message` — Message row (user or assistant)
- `.chat-avatar` — Emoji avatar (🤖 or 👤)
- `.chat-bubble` — Message content bubble
- `.chat-bubble.action-preview` — Special style for mutation previews
- `.chat-action-buttons` — Apply/Cancel button pair
- `.chat-input-area` — Input bar at bottom
- `.chat-loading` — Spinner/animation while waiting for Ollama response

Theme support: All chat styles use existing CSS variables (`--bg-card`, `--text-primary`, etc.) so dark/light theme works automatically.

### 6.6 Configuration

Environment variables (all optional, sensible defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `MAM_OLLAMA_MODEL` | `qwen3.5:4b` | Ollama model for chat |
| `MAM_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `MAM_OLLAMA_TIMEOUT` | `120` | Request timeout in seconds |
| `MAM_CHAT_HISTORY_DIR` | `~/.mac_agents_manager/chat` | Chat persistence directory |
| `MAM_CHAT_MAX_CONTEXT` | `20` | Max messages sent to Ollama as context |
| `MAM_CHAT_RETENTION_DAYS` | `30` | Auto-cleanup chat files older than N days |

---

## 7. File Changes

### New Files

| File | Purpose |
|------|---------|
| `src/mac_agents_manager/ollama_chat.py` | Ollama lifecycle, chat engine, prompt builder, action parser |
| `src/mac_agents_manager/chat_history.py` | Chat persistence (read/write/cleanup JSON files) |
| `tests/test_ollama_chat.py` | Unit tests for chat engine, prompt building, action parsing |
| `tests/test_chat_history.py` | Unit tests for chat persistence |

### Modified Files

| File | Changes |
|------|---------|
| `src/mac_agents_manager/app.py` | Add 4 new routes: `/api/chat/send`, `/api/chat/confirm`, `/api/chat/history`, `/api/chat/health`, `/api/chat/clear` |
| `src/mac_agents_manager/templates/index.html` | Add mode tabs (IDE/AI Chat), chat panel HTML |
| `src/mac_agents_manager/templates/layout.html` | Update CSP to allow Ollama connection (`connect-src 'self' http://localhost:11434`) |
| `src/mac_agents_manager/static/style.css` | Add chat panel styles, mode tabs, suggestion chips, message bubbles, loading state |
| `pyproject.toml` | Add `requests` to dependencies; bump version to `2.0.0` |
| `requirements.txt` | Add `requests` |
| `CHANGELOG.md` | Document v2.0.0 AI Chat feature |
| `README.md` | Update feature list, add AI Chat section with screenshots |

### Unchanged Files (explicitly)

| File | Status |
|------|--------|
| `src/mac_agents_manager/models.py` | ✅ No changes |
| `src/mac_agents_manager/launchctl.py` | ✅ No changes |
| `src/mac_agents_manager/launchctl_list.py` | ✅ No changes |
| `src/mac_agents_manager/constants.py` | ✅ No changes |
| `src/mac_agents_manager/cli.py` | ✅ No changes |

---

## 8. Execution Plan (Phases)

### Phase 1: Backend — Ollama Integration (`ollama_chat.py`)
- Port Ollama lifecycle functions from chronometry (`ensure_running`, `restart`, `auto-pull`)
- Implement `OllamaChatEngine` with system prompt builder
- Implement action parsing from AI responses
- Add action-to-MAM-API executor (maps action types to `LaunchService` / `LaunchCtlController` calls)
- Unit tests with mocked Ollama responses

### Phase 2: Backend — Chat History (`chat_history.py`)
- Implement JSON file persistence (`~/.mac_agents_manager/chat/`)
- Session management (create, read, append, clear)
- Auto-cleanup of old sessions (>30 days)
- Unit tests

### Phase 3: Backend — Flask Routes
- Add `/api/chat/send` — accepts message + context, calls Ollama, returns response + parsed action
- Add `/api/chat/confirm` — executes a confirmed action via existing MAM APIs
- Add `/api/chat/history` — returns persisted messages for a session
- Add `/api/chat/clear` — clears a session
- Add `/api/chat/health` — Ollama status check
- CSRF protection on POST routes
- Update CSP headers for Ollama connectivity

### Phase 4: Frontend — Tab System
- Add IDE / AI Chat mode tabs to `editor-header`
- Implement `switchMode('ide' | 'chat')` — toggles visibility of IDE panels vs chat panel
- Preserve state on both sides when switching

### Phase 5: Frontend — Chat UI
- Build chat panel HTML (suggestions bar, messages area, input bar)
- Implement `sendChatMessage()` — POST to `/api/chat/send`, render response
- Implement suggested prompt chips (global vs service-specific)
- Dynamic chip updates when service selection changes
- Render action previews with Apply/Cancel buttons
- Handle confirm flow via `/api/chat/confirm`
- Chat loading state (spinner while Ollama responds)
- Auto-scroll to newest message

### Phase 6: Frontend — Chat Styling
- CSS for all chat components using existing design tokens
- Dark/light theme support via CSS variables
- Responsive message bubbles, code blocks in responses, diff-style previews

### Phase 7: Integration Testing & Polish
- End-to-end test: create agent via chat
- End-to-end test: modify schedule via chat
- End-to-end test: start/stop via chat
- End-to-end test: view stats via chat
- Edge cases: Ollama down, model not pulled, empty response
- Session persistence across page refresh
- Update README, CHANGELOG

---

## 9. Security Considerations

| Concern | Mitigation |
|---------|-----------|
| Prompt injection via service names/labels | Service data is treated as data context, not instructions. System prompt is separated from user input. Labels are validated by existing `LABEL_RE` regex. |
| Chat endpoint abuse | All POST endpoints require CSRF token (existing pattern). Localhost-only binding. |
| Ollama exposure | MAM talks to Ollama on `localhost:11434` only. No external Ollama calls. |
| Chat history leakage | Files stored in `~/.mac_agents_manager/chat/` with `0600` permissions. Auto-cleanup after 30 days. |
| Action execution | All mutations go through existing `LaunchService` and `LaunchCtlController` with their existing validation (label regex, path traversal checks, etc.). |
| CSP update | `connect-src` adds `http://localhost:11434` only for health checks. All Ollama API calls go through Flask backend, not browser. |

---

## 10. Dependencies

| Dependency | Current | Required |
|-----------|---------|----------|
| Flask | >=3.0.0 | No change |
| requests | — | NEW (for Ollama HTTP API) |
| Ollama | — | Must be installed on host (`brew install ollama`) |
| qwen3.5:4b | — | Auto-pulled if missing |

---

## 11. Success Metrics

| Metric | Target |
|--------|--------|
| AI Chat tab loads without breaking IDE tab | ✅ Zero regressions |
| Ollama auto-starts if not running | ✅ Within 30s |
| All IDE actions available via chat | ✅ 100% coverage |
| Mutation flow has preview + confirm | ✅ No direct mutations |
| Chat history persists across page refresh | ✅ Verified |
| Dark/light theme works for chat UI | ✅ Uses existing CSS vars |
| All existing tests pass | ✅ No regressions |

---

## 12. Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | Should the chat panel show a "Connecting to Ollama..." state on first load if Ollama needs to start? | Proposed: Yes — show a status bar at top of chat panel with Ollama health |
| 2 | Maximum tokens for Ollama response? | Proposed: 2048 (sufficient for action JSON + explanation) |
| 3 | Should we support `/` commands in chat input (e.g., `/clear`, `/history`)? | Proposed: Yes, nice-to-have for Phase 7 |
| 4 | When creating a new agent via chat, should the tree auto-refresh? | Proposed: Yes — after successful create/delete, refresh tree |

---

## 13. Appendix

### A. Suggested Prompt → System Prompt Mapping

When a user clicks a suggested prompt chip, the frontend sends the chip's predefined message to `/api/chat/send`. The system prompt is enriched with:

**Global context (no service selected):**
```
CURRENT STATE:
Total agents: 24
Running: 18, Stopped: 4, Not Loaded: 2
KeepAlive: 15, Scheduled: 9
Namespaces: productivity (8), finance (5), automation (4), ...

Services list:
- user.productivity.chronometry-menubar [KeepAlive, Running, PID: 1234]
- user.finance.reconcile [Scheduled 10:00, Stopped]
- ...
```

**Service context (service selected):**
```
SELECTED SERVICE: user.finance.reconcile
Label: user.finance.reconcile
Type: Scheduled
Schedule: Hour=10, Minute=0
Status: Loaded, Not Running
Script: /bin/bash /Users/pkasinathan/scripts/reconcile.sh
Working Dir: /Users/pkasinathan/workspace/finance
Env Vars: PYTHONPATH=/usr/local/lib, HOME=/Users/pkasinathan
Plist XML:
<?xml version="1.0" ...?>
<plist ...>
  ...
</plist>
Stdout (last 10 lines):
  ...
Stderr (last 10 lines):
  ...
```

### B. Action JSON Schema

```json
{
  "action": "update_schedule | update_script | update_working_dir | update_environment | rename | start | stop | restart | load | unload | delete | create | convert_schedule_type",
  "service_id": "agent:user.finance.reconcile",
  "params": {
    // varies by action type
  }
}
```

**Examples:**

```json
// Change schedule
{"action": "update_schedule", "service_id": "agent:user.finance.reconcile", "params": {"schedule_type": "scheduled", "intervals": [{"Hour": 8, "Minute": 0}, {"Hour": 18, "Minute": 0}]}}

// Rename
{"action": "rename", "service_id": "agent:user.finance.reconcile", "params": {"new_name": "daily-reconcile", "new_category": "finance"}}

// Create
{"action": "create", "params": {"name": "backup", "category": "automation", "script_path": "/bin/bash /Users/pkasinathan/scripts/backup.sh", "schedule_type": "scheduled", "schedule_hour_0": 2, "schedule_minute_0": 0}}

// Start
{"action": "start", "service_id": "agent:user.finance.reconcile", "params": {}}

// Delete
{"action": "delete", "service_id": "agent:user.finance.reconcile", "params": {}}

// Convert schedule type
{"action": "convert_schedule_type", "service_id": "agent:user.finance.reconcile", "params": {"to": "keepalive"}}
```
