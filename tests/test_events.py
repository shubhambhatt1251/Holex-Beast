"""Tests for the pub-sub event bus — subscribe, emit, unsubscribe, one-shot."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_event_bus_subscribe_emit():
    """EventBus should deliver events to subscribers."""
    from core.events import Event, EventBus, EventType

    bus = EventBus()
    received = []

    def handler(event: Event):
        received.append(event)

    bus.on(EventType.LLM_RESPONSE, handler)
    bus.emit(EventType.LLM_RESPONSE, {"text": "hello"})

    assert len(received) == 1
    assert received[0].data["text"] == "hello"


def test_event_bus_multiple_subscribers():
    """Multiple handlers for same event type."""
    from core.events import EventBus, EventType

    bus = EventBus()
    count = [0]

    def h1(e):
        count[0] += 1

    def h2(e):
        count[0] += 10

    bus.on(EventType.APP_READY, h1)
    bus.on(EventType.APP_READY, h2)
    bus.emit(EventType.APP_READY)

    assert count[0] == 11


def test_event_bus_unsubscribe():
    """Unsubscribed handler should not receive events."""
    from core.events import EventBus, EventType

    bus = EventBus()
    received = []

    def handler(e):
        received.append(e)

    bus.on(EventType.APP_ERROR, handler)
    bus.off(EventType.APP_ERROR, handler)
    bus.emit(EventType.APP_ERROR, {"error": "test"})

    assert len(received) == 0


def test_event_types_exist():
    """Core event types should be defined."""
    from core.events import EventType

    required = [
        "LLM_REQUEST", "LLM_RESPONSE", "LLM_STREAM_CHUNK",
        "AGENT_THINKING", "AGENT_TOOL_CALL", "AGENT_RESPONSE",
        "VOICE_LISTENING_START", "VOICE_STT_RESULT",
        "GUI_THEME_CHANGED", "GUI_USER_MESSAGE",
        "APP_READY", "APP_ERROR",
    ]
    for name in required:
        assert hasattr(EventType, name), f"Missing EventType.{name}"
