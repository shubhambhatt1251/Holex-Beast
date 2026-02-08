"""Tests for conversation memory — creation, messages, serialization, and manager ops."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_conversation_default_fields():
    """A new conversation should have valid defaults."""
    from core.memory.conversation import Conversation

    conv = Conversation()
    assert len(conv.id) == 12
    assert conv.title == "New Chat"
    assert conv.messages == []
    assert conv.message_count == 0
    assert conv.created_at.endswith("+00:00")


def test_conversation_preview_empty():
    """Preview of empty conversation should say so."""
    from core.memory.conversation import Conversation

    conv = Conversation()
    assert conv.preview == "Empty conversation"


def test_conversation_preview_from_user_message():
    """Preview should come from the first user message."""
    from core.llm.base import Message
    from core.memory.conversation import Conversation

    conv = Conversation()
    conv.messages.append(Message.user("How does Python GIL work?"))
    assert "Python GIL" in conv.preview


def test_conversation_preview_truncation():
    """Preview should truncate long messages at 80 chars."""
    from core.llm.base import Message
    from core.memory.conversation import Conversation

    long_text = "x" * 200
    conv = Conversation()
    conv.messages.append(Message.user(long_text))
    assert conv.preview.endswith("...")
    assert len(conv.preview) == 83  # 80 + "..."


def test_auto_title_short():
    """Auto-title should use the full text if under 40 chars."""
    from core.llm.base import Message
    from core.memory.conversation import Conversation

    conv = Conversation()
    conv.messages.append(Message.user("Quick question"))
    conv.auto_title()
    assert conv.title == "Quick question"


def test_auto_title_truncates():
    """Auto-title should truncate at 40 chars with ellipsis."""
    from core.llm.base import Message
    from core.memory.conversation import Conversation

    conv = Conversation()
    conv.messages.append(Message.user("A" * 60))
    conv.auto_title()
    assert conv.title.endswith("...")
    assert len(conv.title) == 43  # 40 + "..."


def test_conversation_serialization_roundtrip():
    """to_dict → from_dict should preserve all fields."""
    from core.llm.base import Message
    from core.memory.conversation import Conversation

    original = Conversation(title="Test Chat", model="gemini-2.5-flash", provider="gemini")
    original.messages.append(Message.user("Hello"))
    original.messages.append(Message.assistant("Hi there!"))

    data = original.to_dict()
    restored = Conversation.from_dict(data)

    assert restored.id == original.id
    assert restored.title == "Test Chat"
    assert restored.model == "gemini-2.5-flash"
    assert len(restored.messages) == 2
    assert restored.messages[0].content == "Hello"
    assert restored.messages[1].content == "Hi there!"


def test_conversation_manager_lifecycle():
    """Manager should handle new/switch/delete conversations."""
    from core.memory.conversation import ConversationManager

    mgr = ConversationManager()

    # Start with nothing
    assert mgr.count == 0
    assert mgr.get_active() is None

    # Create first conversation
    c1 = mgr.new_conversation()
    assert mgr.count == 1
    assert mgr.active_id == c1.id
    assert mgr.get_active() is c1

    # Create second
    c2 = mgr.new_conversation()
    assert mgr.count == 2
    assert mgr.active_id == c2.id

    # Switch back to first
    result = mgr.switch_to(c1.id)
    assert result is c1
    assert mgr.active_id == c1.id

    # Delete active
    mgr.delete_conversation(c1.id)
    assert mgr.count == 1
    assert c1.id not in [c["id"] for c in mgr.list_all()]


def test_conversation_manager_add_message():
    """Adding a message should auto-create conversation if none active."""
    from core.llm.base import Message
    from core.memory.conversation import ConversationManager

    mgr = ConversationManager()
    assert mgr.get_active() is None

    mgr.add_message(Message.user("First message"))
    assert mgr.get_active() is not None
    assert mgr.get_active().message_count == 1
    assert mgr.get_active().title == "First message"  # auto-titled


def test_conversation_manager_clear_active():
    """Clearing should empty messages and reset title."""
    from core.llm.base import Message
    from core.memory.conversation import ConversationManager

    mgr = ConversationManager()
    conv = mgr.new_conversation()
    mgr.add_message(Message.user("test"))
    mgr.add_message(Message.assistant("response"))

    assert conv.message_count == 2
    mgr.clear_active()
    assert conv.message_count == 0
    assert conv.title == "New Chat"


def test_conversation_manager_list_sorted():
    """list_all should return conversations sorted by updated_at descending."""
    from core.llm.base import Message
    from core.memory.conversation import ConversationManager

    mgr = ConversationManager()
    c1 = mgr.new_conversation()
    mgr.add_message(Message.user("first"))

    c2 = mgr.new_conversation()
    mgr.add_message(Message.user("second"))

    items = mgr.list_all()
    # c2 was updated last, so it should come first
    assert items[0]["id"] == c2.id
    assert items[1]["id"] == c1.id
