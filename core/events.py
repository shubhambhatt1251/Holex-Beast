"""Simple pub/sub event bus so components don't import each other."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """All event types in Holex Beast."""

    # LLM Events
    LLM_REQUEST = "llm.request"
    LLM_RESPONSE = "llm.response"
    LLM_STREAM_CHUNK = "llm.stream.chunk"
    LLM_STREAM_START = "llm.stream.start"
    LLM_STREAM_END = "llm.stream.end"
    LLM_ERROR = "llm.error"
    LLM_PROVIDER_CHANGED = "llm.provider.changed"
    LLM_MODEL_CHANGED = "llm.model.changed"

    # Agent Events
    AGENT_THINKING = "agent.thinking"
    AGENT_TOOL_CALL = "agent.tool.call"
    AGENT_TOOL_RESULT = "agent.tool.result"
    AGENT_RESPONSE = "agent.response"
    AGENT_ERROR = "agent.error"

    # Voice Events
    VOICE_WAKE_WORD = "voice.wake_word"
    VOICE_LISTENING_START = "voice.listening.start"
    VOICE_LISTENING_STOP = "voice.listening.stop"
    VOICE_STT_RESULT = "voice.stt.result"
    VOICE_STT_PARTIAL = "voice.stt.partial"
    VOICE_TTS_START = "voice.tts.start"
    VOICE_TTS_END = "voice.tts.end"
    VOICE_TTS_ERROR = "voice.tts.error"
    VOICE_AUDIO_LEVEL = "voice.audio.level"

    # GUI Events
    GUI_USER_MESSAGE = "gui.user.message"
    GUI_CLEAR_CHAT = "gui.clear.chat"
    GUI_NEW_CONVERSATION = "gui.new.conversation"
    GUI_LOAD_CONVERSATION = "gui.load.conversation"
    GUI_THEME_CHANGED = "gui.theme.changed"
    GUI_SETTINGS_UPDATED = "gui.settings.updated"

    # RAG Events
    RAG_DOCUMENT_ADDED = "rag.document.added"
    RAG_DOCUMENT_REMOVED = "rag.document.removed"
    RAG_QUERY_RESULT = "rag.query.result"
    RAG_INDEX_PROGRESS = "rag.index.progress"

    # Firebase Events
    FIREBASE_AUTH_LOGIN = "firebase.auth.login"
    FIREBASE_AUTH_LOGOUT = "firebase.auth.logout"
    FIREBASE_SYNC_START = "firebase.sync.start"
    FIREBASE_SYNC_COMPLETE = "firebase.sync.complete"
    FIREBASE_ERROR = "firebase.error"

    # System Events
    APP_READY = "app.ready"
    APP_SHUTDOWN = "app.shutdown"
    APP_ERROR = "app.error"
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_ERROR = "plugin.error"
    STATUS_UPDATE = "status.update"
    NOTIFICATION = "notification"


@dataclass
class Event:
    """Event payload container."""
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    source: str = "system"
    timestamp: float = field(default_factory=lambda: __import__("time").time())

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __repr__(self) -> str:
        return f"Event({self.type.value}, source={self.source}, keys={list(self.data.keys())})"


# Type aliases
SyncHandler = Callable[[Event], None]
AsyncHandler = Callable[[Event], Coroutine[Any, Any, None]]
Handler = SyncHandler | AsyncHandler


class EventBus:
    """
    Thread-safe publish-subscribe event bus.
    Supports both sync and async handlers.

    Usage:
        bus = EventBus()

        # Subscribe
        bus.on(EventType.LLM_RESPONSE, handle_response)

        # Publish
        bus.emit(EventType.LLM_RESPONSE, {"text": "Hello!"})

        # One-time listener
        bus.once(EventType.APP_READY, on_ready)
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[tuple[Handler, bool]]] = defaultdict(list)
        self._lock = Lock()
        self._middleware: list[Callable[[Event], Optional[Event]]] = []
        self._history: deque[Event] = deque(maxlen=100)

    def on(self, event_type: EventType, handler: Handler) -> Callable:
        """Subscribe to an event type. Returns unsubscribe function."""
        with self._lock:
            self._handlers[event_type].append((handler, False))

        def unsubscribe():
            self.off(event_type, handler)
        return unsubscribe

    def once(self, event_type: EventType, handler: Handler) -> None:
        """Subscribe to an event type, auto-unsubscribe after first call."""
        with self._lock:
            self._handlers[event_type].append((handler, True))

    def off(self, event_type: EventType, handler: Handler) -> None:
        """Unsubscribe a handler from an event type."""
        with self._lock:
            self._handlers[event_type] = [
                (h, once) for h, once in self._handlers[event_type]
                if h != handler
            ]

    def use(self, middleware: Callable[[Event], Optional[Event]]) -> None:
        """Add middleware that can transform or cancel events."""
        self._middleware.append(middleware)

    def emit(self, event_type: EventType, data: dict[str, Any] | None = None,
             source: str = "system") -> None:
        """
        Emit an event to all subscribed handlers.
        Supports both sync and async handlers.
        """
        event = Event(type=event_type, data=data or {}, source=source)

        # Run through middleware
        for mw in self._middleware:
            event = mw(event)
            if event is None:
                return  # Middleware cancelled the event

        # Store in history
        self._history.append(event)

        # Get handlers snapshot
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))

        # Execute handlers
        to_remove: list[Handler] = []
        for handler, is_once in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    # Schedule async handler
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(handler(event))
                    except RuntimeError:
                        asyncio.run(handler(event))
                else:
                    handler(event)

                if is_once:
                    to_remove.append(handler)
            except Exception as e:
                logger.error(f"Error in handler for {event_type.value}: {e}", exc_info=True)

        # Remove one-time handlers
        if to_remove:
            with self._lock:
                for handler in to_remove:
                    self._handlers[event_type] = [
                        (h, once) for h, once in self._handlers[event_type]
                        if h != handler
                    ]

    def clear(self, event_type: Optional[EventType] = None) -> None:
        """Clear handlers for a specific event or all events."""
        with self._lock:
            if event_type:
                self._handlers[event_type].clear()
            else:
                self._handlers.clear()

    def get_history(self, event_type: Optional[EventType] = None,
                    limit: int = 20) -> list[Event]:
        """Get recent event history, optionally filtered by type."""
        events = list(self._history)
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]

    @property
    def stats(self) -> dict[str, int]:
        """Get subscriber counts per event type."""
        with self._lock:
            return {
                et.value: len(handlers)
                for et, handlers in self._handlers.items()
                if handlers
            }


# Global Event Bus Singleton
_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
