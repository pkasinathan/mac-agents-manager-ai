"""Chat history persistence for Mac Agents Manager AI Chat.

Stores chat sessions as JSON files in ~/.mac_agents_manager/chat/.
"""

from __future__ import annotations

import json
import logging
import os
import random
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CHAT_DIR = os.path.join(str(Path.home()), ".mac_agents_manager", "chat")
DEFAULT_MAX_MESSAGES = 200
DEFAULT_RETENTION_DAYS = 30


class ChatHistory:
    """Manages chat session persistence to disk."""

    def __init__(
        self,
        chat_dir: str | None = None,
        max_messages: int = DEFAULT_MAX_MESSAGES,
        retention_days: int | None = None,
    ):
        self.chat_dir = Path(chat_dir or os.environ.get("MAM_CHAT_HISTORY_DIR", DEFAULT_CHAT_DIR))
        self.max_messages = max_messages
        self.retention_days = retention_days or int(os.environ.get("MAM_CHAT_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS)))
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create chat directory with safe permissions if it doesn't exist."""
        try:
            self.chat_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(str(self.chat_dir), 0o700)
        except Exception as exc:
            logger.error("Failed to create chat directory %s: %s", self.chat_dir, exc)

    def _session_path(self, session_id: str) -> Path:
        """Get the file path for a session. Validates session_id to prevent path traversal."""
        # Sanitize: only allow alphanumerics, hyphens, underscores
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        if not safe_id or safe_id != session_id:
            raise ValueError(f"Invalid session_id: {session_id}")
        return self.chat_dir / f"{safe_id}.json"

    @staticmethod
    def generate_session_id() -> str:
        """Generate a unique session ID."""
        now = datetime.now(timezone.utc)
        rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"chat_{now.strftime('%Y%m%d_%H%M%S')}_{rand}"

    def create_session(self, session_id: str) -> dict[str, Any]:
        """Create a new session file."""
        session_data = {
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "messages": [],
        }
        self._write_session(session_id, session_data)
        return session_data

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Read a session from disk."""
        path = self._session_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read session %s: %s", session_id, exc)
            return None

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        action: dict[str, Any] | None = None,
        service_id: str | None = None,
    ) -> None:
        """Append a message to a session. Creates session if it doesn't exist."""
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id)

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if action is not None:
            message["action"] = action
        if service_id is not None:
            message["service_id"] = service_id

        session["messages"].append(message)
        session["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Trim if over max
        if len(session["messages"]) > self.max_messages:
            session["messages"] = session["messages"][-self.max_messages:]

        self._write_session(session_id, session)

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get all messages for a session."""
        session = self.get_session(session_id)
        if session is None:
            return []
        return session.get("messages", [])

    def get_conversation_history(self, session_id: str, max_messages: int | None = None) -> list[dict[str, str]]:
        """Get conversation history formatted for Ollama (role + content only).

        Returns the most recent messages limited to max_messages.
        """
        limit = max_messages or self.max_messages
        messages = self.get_messages(session_id)
        recent = messages[-limit:]
        return [{"role": m["role"], "content": m["content"]} for m in recent if m["role"] in ("user", "assistant")]

    def clear_session(self, session_id: str) -> bool:
        """Clear all messages in a session."""
        path = self._session_path(session_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except OSError as exc:
                logger.error("Failed to clear session %s: %s", session_id, exc)
                return False
        return True

    def list_sessions(self) -> list[dict[str, str]]:
        """List all sessions with metadata."""
        sessions = []
        if not self.chat_dir.exists():
            return sessions

        for f in sorted(self.chat_dir.glob("chat_*.json"), reverse=True):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                    sessions.append({
                        "session_id": data.get("session_id", f.stem),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                        "message_count": len(data.get("messages", [])),
                    })
            except (json.JSONDecodeError, OSError):
                continue

        return sessions

    def cleanup_old_sessions(self) -> int:
        """Remove sessions older than retention_days. Returns count removed."""
        if not self.chat_dir.exists():
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        removed = 0

        for f in self.chat_dir.glob("chat_*.json"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                continue

        if removed:
            logger.info("Cleaned up %d old chat sessions", removed)
        return removed

    def _write_session(self, session_id: str, data: dict[str, Any]) -> None:
        """Write session data to disk."""
        path = self._session_path(session_id)
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            os.chmod(str(path), 0o600)
        except OSError as exc:
            logger.error("Failed to write session %s: %s", session_id, exc)
