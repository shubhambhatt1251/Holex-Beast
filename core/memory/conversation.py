"""Conversation memory — history, context windowing, persistence."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from core.events import EventType, get_event_bus
from core.llm.base import Message, Role

logger = logging.getLogger(__name__)


@dataclass
class Conversation:
    """A single conversation with metadata."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = "New Chat"
    messages: list[Message] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model: str = ""
    provider: str = ""

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def preview(self) -> str:
        """First user message as preview."""
        for msg in self.messages:
            if msg.role == "user":
                text = msg.content if isinstance(msg.content, str) else str(msg.content)
                return text[:80] + ("..." if len(text) > 80 else "")
        return "Empty conversation"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model": self.model,
            "provider": self.provider,
            "message_count": self.message_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        messages = []
        for m in data.get("messages", []):
            messages.append(Message(
                role=Role(m["role"]),
                content=m["content"],
                name=m.get("name"),
            ))
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            title=data.get("title", "Untitled"),
            messages=messages,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            model=data.get("model", ""),
            provider=data.get("provider", ""),
        )

    def auto_title(self) -> None:
        """Generate title from first user message."""
        for msg in self.messages:
            if msg.role == "user":
                text = msg.content if isinstance(msg.content, str) else str(msg.content)
                text = text.strip()
                if len(text) > 40:
                    self.title = text[:40] + "..."
                else:
                    self.title = text
                return
        self.title = "New Chat"


class ConversationManager:
    """
    Manages multiple conversations with persistence.
    Handles creation, switching, saving, and loading.
    """

    def __init__(self):
        self.bus = get_event_bus()
        self._conversations: dict[str, Conversation] = {}
        self._active_id: Optional[str] = None
        self._storage = None  # FirebaseService or LocalStorageService

    def set_storage(self, storage) -> None:
        """Set the storage backend (Firebase or Local)."""
        self._storage = storage

    def new_conversation(self) -> Conversation:
        """Create a new empty conversation."""
        conv = Conversation()
        self._conversations[conv.id] = conv
        self._active_id = conv.id
        self.bus.emit(EventType.GUI_NEW_CONVERSATION, {"id": conv.id})
        logger.debug(f"New conversation: {conv.id}")
        return conv

    def get_active(self) -> Optional[Conversation]:
        """Get the currently active conversation."""
        if self._active_id and self._active_id in self._conversations:
            return self._conversations[self._active_id]
        return None

    def switch_to(self, conversation_id: str) -> Optional[Conversation]:
        """Switch to a different conversation."""
        if conversation_id in self._conversations:
            self._active_id = conversation_id
            conv = self._conversations[conversation_id]
            self.bus.emit(EventType.GUI_LOAD_CONVERSATION, {
                "id": conversation_id,
                "messages": [m.to_dict() for m in conv.messages],
            })
            return conv
        return None

    def add_message(self, message: Message) -> None:
        """Add a message to the active conversation."""
        conv = self.get_active()
        if not conv:
            conv = self.new_conversation()
        conv.messages.append(message)
        conv.updated_at = datetime.now(timezone.utc).isoformat()

        # Auto-title after first exchange
        if conv.message_count == 1:
            conv.auto_title()

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            if self._active_id == conversation_id:
                self._active_id = next(iter(self._conversations), None)
            return True
        return False

    def save_active(self) -> bool:
        """Save active conversation to storage."""
        conv = self.get_active()
        if not conv or not self._storage:
            return False
        try:
            if hasattr(self._storage, "save_conversation"):
                return self._storage.save_conversation(
                    conv.id, conv.title, [m.to_dict() for m in conv.messages]
                )
        except Exception as e:
            logger.error(f"Save failed: {e}")
        return False

    def list_all(self) -> list[dict]:
        """List all conversations with metadata."""
        return [
            {
                "id": c.id,
                "title": c.title,
                "preview": c.preview,
                "message_count": c.message_count,
                "updated_at": c.updated_at,
                "is_active": c.id == self._active_id,
            }
            for c in sorted(
                self._conversations.values(),
                key=lambda c: c.updated_at,
                reverse=True,
            )
        ]

    def clear_active(self) -> None:
        """Clear messages from active conversation."""
        conv = self.get_active()
        if conv:
            conv.messages.clear()
            conv.title = "New Chat"
            self.bus.emit(EventType.GUI_CLEAR_CHAT, {"id": conv.id})

    @property
    def active_id(self) -> Optional[str]:
        return self._active_id

    @property
    def count(self) -> int:
        return len(self._conversations)
