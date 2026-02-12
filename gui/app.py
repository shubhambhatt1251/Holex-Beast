"""
Holex Beast - Main Window

This is the core GUI entry point. It sets up the 3-panel layout:
1. Tools (Left) - Sidebar with agent capabilities
2. Control Center (Middle) - The voice/visualizer engine
3. Chat (Right) - Standard message interface

Wires up all the signal/slots between the backend (Agent/STT) and the frontend.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from gui.styles import get_palette
from gui.widgets.chat_bubbles import MessageBubble, ToolCallBadge, TypingIndicator
from gui.widgets.control_center import ControlCenter
from gui.widgets.input_bar import InputBar
from gui.widgets.settings_panel import SettingsPanel
from gui.widgets.sidebar import Sidebar

# Holex Beast GUI widgets
from gui.widgets.tools_panel import ToolsPanel
from gui.widgets.voice_overlay import VoiceOverlay
from gui.widgets.welcome_screen import WelcomeScreen

# ═══════════════════════════════════════════════════════════════════
# Async Worker Threads
# ═══════════════════════════════════════════════════════════════════

class AsyncWorker(QThread):
    """Run an async coroutine in a background thread."""

    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, coro, parent=None):
        super().__init__(parent)
        self._coro = coro

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._coro)
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            loop.close()


# ═══════════════════════════════════════════════════════════════════
# Chat Area (right panel message list)
# ═══════════════════════════════════════════════════════════════════

class ChatArea(QWidget):
    """Scrollable chat message area with optional welcome screen."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Stack: welcome <-> messages
        self._stack = QStackedWidget()

        # Welcome screen
        self._welcome = WelcomeScreen()
        self._stack.addWidget(self._welcome)

        # Messages scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setObjectName("ChatScrollArea")
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        self._messages_container = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setContentsMargins(16, 12, 16, 12)
        self._messages_layout.setSpacing(6)
        self._messages_layout.addStretch()

        self._scroll.setWidget(self._messages_container)
        self._stack.addWidget(self._scroll)

        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack)

    def show_welcome(self) -> None:
        self._stack.setCurrentIndex(0)

    def show_messages(self) -> None:
        self._stack.setCurrentIndex(1)

    def add_message(
        self, role: str, content: str, animate: bool = True,
    ) -> MessageBubble:
        """Add a message bubble and scroll to bottom."""
        is_user = role == "user"
        avatar = "🧑" if is_user else "🤖"
        timestamp = datetime.now().strftime("%H:%M")
        bubble = MessageBubble(
            text=content,
            is_user=is_user,
            avatar=avatar,
            timestamp=timestamp,
        )
        # Insert before the stretch
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, bubble)
        self._scroll_to_bottom()
        return bubble

    def add_typing_indicator(self) -> TypingIndicator:
        indicator = TypingIndicator()
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, indicator)
        self._scroll_to_bottom()
        return indicator

    def remove_widget(self, widget: QWidget) -> None:
        self._messages_layout.removeWidget(widget)
        widget.deleteLater()

    def clear_messages(self) -> None:
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    @property
    def welcome(self) -> WelcomeScreen:
        return self._welcome


# ═══════════════════════════════════════════════════════════════════
# Main Window
# ═══════════════════════════════════════════════════════════════════

class HolexBeastApp(QMainWindow):
    """
    Premium 3-panel desktop AI assistant.

    Layout:
    ┌─────────────────────────────────────────────────────────┐
    │                   Top Header Bar                        │
    ├──────────┬───────────────────────┬──────────────────────┤
    │  TOOLS   │   CONTROL CENTER      │       CHAT           │
    │  PANEL   │  Voice Sphere + Mic   │    Messages          │
    │  210px   │   Quick Actions       │    Input Bar         │
    │          │     (flexible)        │      400px           │
    ├──────────┴───────────────────────┴──────────────────────┤
    │                    Status Bar                           │
    └─────────────────────────────────────────────────────────┘
    """

    # Thread-safe signals for STT callbacks (called from background threads)
    _stt_partial_signal = pyqtSignal(str)
    _stt_final_signal = pyqtSignal(str)
    _audio_level_signal = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self._workers: List[QThread] = []
        self._current_conversation_id: Optional[str] = None
        self._typing_indicator: Optional[TypingIndicator] = None
        self._voice_mode = False

        # Connect thread-safe STT signals (partial/final text)
        self._stt_partial_signal.connect(self._on_stt_partial)
        self._stt_final_signal.connect(self._on_stt_final)

        # Backend references (set by run.py)
        self.llm_router = None
        self.agent = None
        self.stt = None
        self.tts = None
        self.wake_word = None
        self.rag_pipeline = None
        self.conversation_manager = None
        self.storage_service = None
        self.event_bus = None
        self._current_mode = "chat"  # Default input mode (web/chat/sparkle)

        self._setup_window()
        self._setup_ui()

        # Now that _control_center exists, connect audio level signal
        self._audio_level_signal.connect(
            lambda lvl: self._control_center.set_audio_level(lvl)
        )
        self._connect_signals()
        self._setup_shortcuts()
        self._setup_system_tray()
        self._load_models()

    # ── Window Setup ────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle("Holex Beast")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 850)

        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                (geo.width() - self.width()) // 2,
                (geo.height() - self.height()) // 2,
            )

    # ── UI Assembly ─────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Top Header Bar ──
        self._header = self._build_header()
        root_layout.addWidget(self._header)

        # ── Body Layout: Sidebar + 3-Panel ──
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # SIDEBAR — Conversation history (collapsible, hidden by default)
        self._sidebar = Sidebar()
        self._sidebar.setVisible(False)
        body.addWidget(self._sidebar)

        # Sidebar separator
        sep0 = QFrame()
        sep0.setFixedWidth(1)
        sep0.setStyleSheet("background: rgba(255,255,255,0.04);")
        body.addWidget(sep0)

        # LEFT — Tools Panel
        self._tools_panel = ToolsPanel()
        body.addWidget(self._tools_panel)

        # Vertical separator
        sep1 = QFrame()
        sep1.setFixedWidth(1)
        sep1.setStyleSheet("background: rgba(255,255,255,0.04);")
        body.addWidget(sep1)

        # CENTER + RIGHT — Resizable via QSplitter
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(3)
        self._splitter.setStyleSheet(
            "QSplitter::handle { background: rgba(108,92,231,0.15); }"
            "QSplitter::handle:hover { background: rgba(108,92,231,0.4); }"
        )

        # Center: Control Center
        self._control_center = ControlCenter()
        self._control_center.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._splitter.addWidget(self._control_center)

        # Right: Chat Panel
        self._chat_panel = self._build_chat_panel()
        self._chat_panel.setMinimumWidth(320)
        self._splitter.addWidget(self._chat_panel)

        # Set initial sizes (60% center, 40% chat)
        self._splitter.setSizes([600, 400])

        body.addWidget(self._splitter, 1)

        root_layout.addLayout(body, 1)

        # Voice overlay (hidden, covers chat area)
        self._voice_overlay = VoiceOverlay(self._chat_panel)
        self._voice_overlay.setVisible(False)
        self._voice_overlay.setGeometry(self._chat_panel.rect())

        # Settings panel (hidden, overlays right side)
        self._settings_panel = SettingsPanel()
        self._settings_panel.setVisible(False)

        # ── Status Bar ──
        self._status_bar = QStatusBar()
        self._status_bar.setFixedHeight(26)
        self._status_bar.setStyleSheet(
            "QStatusBar { background: rgba(8,8,16,0.9); "
            "border-top: 1px solid rgba(255,255,255,0.04); }"
        )
        self._status_label = QLabel("Holex Beast v1.0 · Ready")
        self._status_label.setStyleSheet(
            "color: #4a4b60; font-size: 10px; background: transparent; "
            "padding-left: 12px; letter-spacing: 0.3px;"
        )
        self._status_bar.addPermanentWidget(self._status_label)
        self.setStatusBar(self._status_bar)

    def _build_header(self) -> QFrame:
        """Top header bar with logo, title, and controls."""
        header = QFrame()
        header.setObjectName("TopHeader")
        header.setFixedHeight(48)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        # Logo
        logo = QLabel("✦")
        logo.setStyleSheet(
            "font-size: 20px; color: #6c5ce7; background: transparent;"
        )
        layout.addWidget(logo)

        # Title
        title = QLabel("Holex Beast")
        title.setStyleSheet(
            "color: #c0c0d8; font-size: 14px; font-weight: 700; "
            "background: transparent; letter-spacing: 0.5px;"
        )
        layout.addWidget(title)

        layout.addSpacing(8)

        # Toggle sidebar (History)
        self._toggle_sidebar_btn = QPushButton("☰")
        self._toggle_sidebar_btn.setObjectName("HeaderBtn")
        self._toggle_sidebar_btn.setFixedSize(32, 32)
        self._toggle_sidebar_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_sidebar_btn.setToolTip("Toggle Menu / History")
        self._toggle_sidebar_btn.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self._toggle_sidebar_btn)

        # New chat
        self._new_chat_btn = QPushButton("+")
        self._new_chat_btn.setObjectName("HeaderBtn")
        self._new_chat_btn.setFixedSize(32, 32)
        self._new_chat_btn.setCursor(Qt.PointingHandCursor)
        self._new_chat_btn.setToolTip("New chat (Ctrl+N)")
        layout.addWidget(self._new_chat_btn)

        layout.addStretch()

        # Provider badge
        self._provider_badge = QLabel("GROQ")
        self._provider_badge.setStyleSheet(
            "color: #f97316; background: rgba(249,115,22,0.12); "
            "border: 1px solid rgba(249,115,22,0.25); border-radius: 10px; "
            "padding: 2px 10px; font-size: 9px; font-weight: 700; "
            "letter-spacing: 0.5px;"
        )
        layout.addWidget(self._provider_badge)

        layout.addSpacing(4)

        # Model name
        self._model_badge = QLabel("kimi-k2-instruct")
        self._model_badge.setStyleSheet(
            "color: #6c6d80; font-size: 10px; background: transparent;"
        )
        layout.addWidget(self._model_badge)

        layout.addStretch()

        # Plan badge
        plan = QLabel("Free Plan")
        plan.setObjectName("PlanBadge")
        plan.setAlignment(Qt.AlignCenter)
        layout.addWidget(plan)

        layout.addSpacing(4)

        # Upgrade
        upgrade = QPushButton("Upgrade")
        upgrade.setObjectName("UpgradeBtn")
        upgrade.setCursor(Qt.PointingHandCursor)
        upgrade.setFixedHeight(28)
        # Upgrade — open settings panel to LLM tab
        self._upgrade_btn = upgrade
        upgrade.clicked.connect(self._on_upgrade_clicked)
        layout.addWidget(upgrade)

        layout.addSpacing(8)

        # Settings
        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("HeaderBtn")
        settings_btn.setFixedSize(32, 32)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setToolTip("Settings (Ctrl+,)")
        settings_btn.clicked.connect(self._toggle_settings)
        layout.addWidget(settings_btn)

        # Avatar — open account settings
        avatar = QPushButton("S")
        avatar.setObjectName("HeaderAvatar")
        avatar.setFixedSize(32, 32)
        avatar.setCursor(Qt.PointingHandCursor)
        avatar.setToolTip("Profile & Account")
        avatar.clicked.connect(self._on_avatar_clicked)
        layout.addWidget(avatar)

        return header

    def _build_chat_panel(self) -> QFrame:
        """Right panel: chat header + message area + input bar."""
        panel = QFrame()
        panel.setObjectName("ChatPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Chat header
        chat_header = QFrame()
        chat_header.setFixedHeight(42)
        chat_header.setObjectName("ChatPanelHeader")
        ch_layout = QHBoxLayout(chat_header)
        ch_layout.setContentsMargins(16, 0, 16, 0)
        ch_layout.setSpacing(8)

        chat_icon = QLabel("💬")
        chat_icon.setStyleSheet(
            "font-size: 14px; background: transparent;"
        )
        ch_layout.addWidget(chat_icon)

        chat_title = QLabel("AI Chat")
        chat_title.setStyleSheet(
            "color: #b0b0c8; font-size: 13px; font-weight: 700; "
            "background: transparent;"
        )
        ch_layout.addWidget(chat_title)

        ch_layout.addStretch()

        # Clear chat button
        clear_btn = QPushButton("🗑")
        clear_btn.setObjectName("HeaderBtn")
        clear_btn.setFixedSize(28, 28)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setToolTip("Clear chat")
        clear_btn.clicked.connect(self._on_clear_chat)
        ch_layout.addWidget(clear_btn)

        layout.addWidget(chat_header)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.04);")
        layout.addWidget(sep)

        # Chat area
        self._chat_area = ChatArea()
        layout.addWidget(self._chat_area, 1)

        # Input bar
        self._input_bar = InputBar()
        layout.addWidget(self._input_bar)

        return panel

    # ── Signal Wiring ───────────────────────────────────────────────

    def _connect_signals(self) -> None:
        # Connect signals
        # self._toggle_sidebar_btn is already connected in _build_header

        # Shortcuts
        self._new_chat_btn.clicked.connect(self._on_new_chat)

        # Chat input
        self._input_bar.message_submitted.connect(self._on_user_message)
        self._input_bar.model_changed.connect(self._on_model_changed)
        self._input_bar.stop_requested.connect(self._on_stop_generation)
        self._input_bar.voice_toggled.connect(self._on_voice_toggle)
        self._input_bar.file_attached.connect(self._on_file_attached)
        self._input_bar.image_attached.connect(self._on_image_attached)
        self._input_bar.mode_changed.connect(self._on_mode_changed)

        # Welcome suggestions
        self._chat_area.welcome.prompt_selected.connect(self._on_user_message)

        # Tools panel → insert command into chat
        self._tools_panel.tool_activated.connect(self._on_tool_activated)

        # Control center
        self._control_center.voice_toggled.connect(self._on_center_voice_toggle)
        self._control_center.command_submitted.connect(self._on_command_submitted)
        self._control_center.text_submitted.connect(self._on_voice_text)

        # Settings
        self._settings_panel.theme_changed.connect(self._apply_theme)
        self._settings_panel.rag_tab.document_added.connect(
            self._on_rag_document_added
        )
        self._settings_panel.rag_tab.document_removed.connect(
            self._on_rag_document_removed
        )
        self._settings_panel.account_tab.login_requested.connect(self._on_login)
        self._settings_panel.account_tab.sync_requested.connect(self._on_sync)
        self._settings_panel.settings_updated.connect(self._on_settings_updated)

        # Sidebar
        self._sidebar.new_chat_requested.connect(self._on_new_chat)
        self._sidebar.conversation_selected.connect(self._on_conversation_selected)
        self._sidebar.conversation_deleted.connect(self._on_conversation_deleted)
        self._sidebar.theme_selected.connect(self._apply_theme)

        # Voice overlay
        self._voice_overlay.text_submitted.connect(self._on_user_message)
        self._voice_overlay.voice_stopped.connect(self._on_voice_overlay_stopped)

    def _load_models(self) -> None:
        """Populate model selector in input bar and subscribe to agent events."""
        # Subscribe to agent tool call events
        if self.event_bus:
            try:
                from core.events import EventType
                self.event_bus.on(
                    EventType.AGENT_TOOL_CALL,
                    self._on_agent_tool_event,
                )
            except Exception:
                pass

        if self.llm_router and self.llm_router.available_providers:
            from core.llm.models import ALL_MODELS
            models = {}
            for prov in self.llm_router.available_providers:
                provider_models = ALL_MODELS.get(prov, [])
                models[prov.title()] = [
                    m.id for m in provider_models if m.max_output > 0
                ]
            if models:
                self._input_bar.set_models(models)
                return
        # Fallback
        models = {
            "Groq": [
                "moonshotai/kimi-k2-instruct",
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
            ],
            "Gemini": [
                "gemini-2.5-flash",
                "gemini-2.0-flash",
            ],
            "Ollama": [
                "llama3.2:3b",
                "mistral:7b",
            ],
        }
        self._input_bar.set_models(models)

    # ── Message Handling ────────────────────────────────────────────

    @pyqtSlot(str)
    def _on_user_message(self, text: str) -> None:
        self._chat_area.show_messages()
        self._chat_area.add_message("user", text)
        self._typing_indicator = self._chat_area.add_typing_indicator()
        self._input_bar.set_enabled(False)
        self._status_label.setText("Holex Beast v1.0 · Processing…")

        # Save to conversation manager
        if self.conversation_manager:
            from core.llm.base import Message as LLMMessage
            self.conversation_manager.add_message(LLMMessage.user(text))
            # Update sidebar title (auto-titled after first message)
            conv = self.conversation_manager.get_active()
            if conv and conv.id in self._sidebar._items:
                item = self._sidebar._items[conv.id]
                # title = conv.title[:28] + ("..." if len(conv.title) > 28 else "")
                item.title_text = conv.title
                item.findChild(QLabel, "ConvTitle")
                # Just remove and re-add to update display
                self._sidebar.remove_conversation(conv.id)
                self._sidebar.add_conversation(
                    conv_id=conv.id, title=conv.title, is_active=True
                )

        if self.agent:
            self._send_to_agent(text)
        else:
            QTimer.singleShot(1500, lambda: self._on_response_received(
                f"I received: \"{text}\"\n\n"
                "🔧 **Backend not connected** — connect LLM providers in "
                "`run.py` to get real AI responses."
            ))

    def _send_to_agent(self, text: str) -> None:
        async def _run():
            # Query RAG for relevant document context
            rag_context = None
            if self.rag_pipeline:
                try:
                    rag_context = await self.rag_pipeline.query(text)
                except Exception:
                    pass  # RAG is optional enhancement
            return await self.agent.process(text, rag_context=rag_context)

        worker = AsyncWorker(_run())
        worker.result_ready.connect(self._on_agent_response)
        worker.error_occurred.connect(self._on_agent_error)
        self._workers.append(worker)
        worker.finished.connect(
            lambda: self._workers.remove(worker)
            if worker in self._workers else None
        )
        worker.start()

    def _send_image_to_agent(self, text: str, image_path: str) -> None:
        async def _run():
            return await self.agent.process_with_image(text, image_path)

        worker = AsyncWorker(_run())
        worker.result_ready.connect(self._on_agent_response)
        worker.error_occurred.connect(self._on_agent_error)
        self._workers.append(worker)
        worker.finished.connect(
            lambda: self._workers.remove(worker)
            if worker in self._workers else None
        )
        worker.start()

    def _on_agent_response(self, response) -> None:
        text = response.content if hasattr(response, "content") else str(response)
        self._on_response_received(text)

    def _on_agent_error(self, error: str) -> None:
        self._on_response_received(
            f"⚠️ **Error**: {error}\n\n"
            "Please check your API keys and network connection."
        )

    def _show_tool_badge(self, tool_name: str) -> None:
        """Show a badge in the chat area while a tool is being used."""
        badge = ToolCallBadge(tool_name)
        count = self._chat_area._messages_layout.count()
        self._chat_area._messages_layout.insertWidget(count - 1, badge)
        self._chat_area._scroll_to_bottom()

    def _on_agent_tool_event(self, event) -> None:
        """Agent is calling a tool — show badge (thread-safe via QTimer)."""
        tool_name = ""
        if hasattr(event, "data") and isinstance(event.data, dict):
            tool_name = event.data.get("tool", event.data.get("name", "tool"))
        elif isinstance(event, dict):
            tool_name = event.get("tool", event.get("name", "tool"))
        if tool_name:
            QTimer.singleShot(0, lambda: self._show_tool_badge(tool_name))

    def _on_response_received(self, text: str) -> None:
        if self._typing_indicator:
            self._chat_area.remove_widget(self._typing_indicator)
            self._typing_indicator = None
        self._chat_area.add_message("assistant", text, animate=True)
        self._input_bar.set_enabled(True)
        self._input_bar.focus_input()
        self._status_label.setText("Holex Beast v1.0 · Ready")

        # Save assistant response to conversation manager
        if self.conversation_manager:
            from core.llm.base import Message as LLMMessage
            self.conversation_manager.add_message(LLMMessage.assistant(text))

        # Update Voice UI with the response text
        self._control_center.set_ai_text(text)

        # TTS — only speak for voice-initiated messages
        if self._voice_mode and self.tts:
            self._voice_mode = False
            try:
                import threading

                def _speak_async():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self.tts.speak(text))
                    except Exception:
                        pass
                    finally:
                        loop.close()

                threading.Thread(target=_speak_async, daemon=True).start()
            except Exception:
                pass
        else:
            self._voice_mode = False

    # ── Conversation Management ─────────────────────────────────────

    @pyqtSlot()
    def _on_new_chat(self) -> None:
        self._chat_area.clear_messages()
        self._chat_area.show_welcome()
        self._current_conversation_id = str(uuid.uuid4())
        # Clear agent memory so AI doesn't remember old conversation
        if self.agent:
            self.agent.clear_history()
        # Start a new conversation in the manager
        if self.conversation_manager:
            conv = self.conversation_manager.new_conversation()
            self._current_conversation_id = conv.id
            # Add to sidebar
            self._sidebar.add_conversation(
                conv_id=conv.id, title="New Chat", is_active=True
            )
            self._sidebar.set_active(conv.id)

    @pyqtSlot()
    def _on_clear_chat(self) -> None:
        reply = QMessageBox.question(
            self, "Clear Chat",
            "Clear all messages in the current conversation?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._chat_area.clear_messages()
            self._chat_area.show_welcome()
            # Clear agent memory
            if self.agent:
                self.agent.clear_history()
            if self.conversation_manager:
                self.conversation_manager.clear_active()

    @pyqtSlot(str)
    def _on_conversation_selected(self, conv_id: str) -> None:
        """Switch to a different conversation from the sidebar."""
        if self.conversation_manager:
            conv = self.conversation_manager.switch_to(conv_id)
            if conv:
                self._chat_area.clear_messages()
                self._chat_area.show_messages()
                # Replay messages into the chat UI
                for msg in conv.messages:
                    role = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
                    if role in ("user", "assistant"):
                        self._chat_area.add_message(role, msg.content)
                # Rebuild agent history
                if self.agent:
                    self.agent.clear_history()
                    self.agent._history = list(conv.messages)
                self._sidebar.set_active(conv_id)
                self._current_conversation_id = conv_id

    @pyqtSlot(str)
    def _on_conversation_deleted(self, conv_id: str) -> None:
        """Delete a conversation from the sidebar."""
        reply = QMessageBox.question(
            self, "Delete Conversation",
            "Delete this conversation permanently?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            if self.conversation_manager:
                self.conversation_manager.delete_conversation(conv_id)
            self._sidebar.remove_conversation(conv_id)

    # ── Voice Overlay ───────────────────────────────────────────────

    def _on_voice_toggle(self, active: bool) -> None:
        """Toggle voice overlay from input bar's mic button."""
        if active:
            # We now use the Control Center (inline) instead of overlay
            # self._voice_overlay.setGeometry(...)
            # self._voice_overlay.activate()
            self._start_listening()
        else:
            # self._voice_overlay.deactivate()
            self._stop_listening()

    def _on_center_voice_toggle(self, active: bool) -> None:
        """Toggle voice from control center's mic button."""
        if active:
            # Use inline Control Center
            self._start_listening()
        else:
            self._stop_listening()

    def _on_voice_overlay_stopped(self) -> None:
        """Voice overlay closed."""
        self._voice_overlay.deactivate()
        self._stop_listening()

    # ── Sidebar Toggle ──────────────────────────────────────────────

    @pyqtSlot()
    def _toggle_sidebar(self) -> None:
        """Toggle conversation history sidebar visibility."""
        is_visible = self._sidebar.isVisible()
        self._sidebar.setVisible(not is_visible)


    # ── Upgrade / Avatar Buttons ────────────────────────────────────

    def _on_upgrade_clicked(self) -> None:
        """Show settings panel, opened to LLM tab."""
        self._settings_panel.setVisible(True)
        # Switch to LLM tab (index 0)
        self._settings_panel._tabs.setCurrentIndex(0)
        self._status_label.setText("Holex Beast v1.0 · Configure your LLM providers")

    def _on_avatar_clicked(self) -> None:
        """Show settings panel, opened to Account tab."""
        self._settings_panel.setVisible(True)
        # Switch to Account tab (index 4)
        self._settings_panel._tabs.setCurrentIndex(4)
        self._status_label.setText("Holex Beast v1.0 · Profile & Account")

    # ── Model / Provider ────────────────────────────────────────────

    @pyqtSlot(str, str)
    def _on_model_changed(self, provider: str, model: str) -> None:
        if self.llm_router:
            try:
                self.llm_router.switch_provider(provider.lower(), model)
            except Exception:
                try:
                    self.llm_router.switch_model(model)
                except Exception:
                    pass
        # Update header badges
        provider_colors = {
            "groq": "#f97316", "gemini": "#3b82f6", "ollama": "#22c55e",
        }
        color = provider_colors.get(provider.lower(), "#6c5ce7")
        self._provider_badge.setText(provider.upper())
        self._provider_badge.setStyleSheet(
            f"color: {color}; background: {color}18; "
            f"border: 1px solid {color}35; border-radius: 10px; "
            "padding: 2px 10px; font-size: 9px; font-weight: 700; "
            "letter-spacing: 0.5px;"
        )
        # Shorten model name for display
        short = model.split("/")[-1] if "/" in model else model
        self._model_badge.setText(short)
        self._status_label.setText(
            f"Holex Beast v1.0 · {provider.title()} / {short}"
        )

    # ── Stop Generation ─────────────────────────────────────────────

    @pyqtSlot()
    def _on_stop_generation(self) -> None:
        for worker in self._workers:
            if worker.isRunning():
                worker.quit()
        if self._typing_indicator:
            self._chat_area.remove_widget(self._typing_indicator)
            self._typing_indicator = None
        self._input_bar.set_enabled(True)
        self._input_bar.focus_input()
        self._status_label.setText("Holex Beast v1.0 · Stopped")

    # ── Voice Control ───────────────────────────────────────────────
    # NOTE: _on_voice_toggle and _on_center_voice_toggle are defined
    # above in the Voice Overlay section (lines ~788-806).
    # They launch VoiceOverlay AND call _start/_stop_listening.

    def _start_listening(self) -> None:
        self._control_center.activate_voice()
        self._input_bar.set_voice_active(True)

        # Shared View: Keep Chat Panel visible
        self._chat_panel.show()
        self._splitter.setSizes([650, 500])

        if not self.stt:
            # FEEDBACK for missing model
            self._control_center.set_status("❌ Voice Error: No STT Model")
            self._control_center.set_ai_text(
                "Please download a Vosk model to the `models/` directory.\n"
                "Check logs for details."
            )
            QTimer.singleShot(3000, self._stop_listening)
            return

        if self.stt:
            try:
                self.stt.start_listening(
                    on_result=lambda t: self._stt_final_signal.emit(t),
                    on_partial=lambda t: self._stt_partial_signal.emit(t),
                )
            except Exception:
                pass
        if self.event_bus:
            try:
                from core.events import EventType
                self.event_bus.on(
                    EventType.VOICE_AUDIO_LEVEL,
                    self._on_audio_level_event,
                )
            except Exception:
                pass

    def _stop_listening(self) -> None:
        self._control_center.deactivate_voice()
        self._input_bar.set_voice_active(False)

        # Restore default balanced view
        self._chat_panel.show()
        self._splitter.setSizes([600, 500])

        if self.stt:
            try:
                self.stt.stop_listening()
            except Exception:
                pass

    @pyqtSlot(str)
    def _on_command_submitted(self, cmd: str) -> None:
        """Handle Quick Action commands (intercept for reliability)."""
        # 1. Show in Chat
        self._on_user_message(cmd)

        # 2. Fast-path for Screenshot (Reliability fix)
        # If the user clicks "Screenshot", we shouldn't rely solely on LLM agent
        # which might be slow or offline.
        if "screenshot" in cmd.lower() and "take" in cmd.lower():
            # Try to find the system_control tool
            if self.agent:
                for tool in self.agent.tools:
                    if tool.name == "system_control":
                        # Execute directly in background
                        async def _run_snap():
                            await tool.execute("screenshot")

                        worker = AsyncWorker(_run_snap())
                        worker.result_ready.connect(lambda res: (
                            self._on_response_received(f"✅ {res.output}")
                        ))
                        worker.start()
                        self._workers.append(worker)
                        return

    def _on_stt_partial(self, text: str) -> None:
        if text.strip():
            self._control_center.set_partial_text(text.strip())
            # Forward to voice overlay
            if self._voice_overlay.isVisible():
                self._voice_overlay.set_partial_text(text.strip())

    def _on_stt_final(self, text: str) -> None:
        if text.strip():
            self._control_center.set_final_text(text.strip())
            # Forward to voice overlay
            if self._voice_overlay.isVisible():
                self._voice_overlay.set_final_text(text.strip())
            self._on_voice_text(text.strip())

    def _on_audio_level_event(self, event) -> None:
        level = 0.0
        if hasattr(event, "data") and isinstance(event.data, dict):
            level = event.data.get("level", 0.0)
        elif isinstance(event, dict):
            level = event.get("level", 0.0)
        self._audio_level_signal.emit(level)
        # Forward to voice overlay
        if self._voice_overlay.isVisible():
            self._voice_overlay.set_audio_level(level)

    def _on_voice_text(self, text: str) -> None:
        if text.strip():
            self._voice_mode = True
            self._on_user_message(text.strip())

    # ── Tools Panel ─────────────────────────────────────────────────

    @pyqtSlot(str, str)
    def _on_tool_activated(self, tool_id: str, example: str) -> None:
        """Tool card clicked → send example command directly to AI."""
        self._on_user_message(example)

    # ── Mode Toggle ─────────────────────────────────────────────────

    @pyqtSlot(str)
    def _on_mode_changed(self, mode: str) -> None:
        """Handle mode toggle (web/chat/sparkle) from input bar."""
        self._current_mode = mode
        mode_labels = {"web": "Web Search", "chat": "Chat", "sparkle": "AI Analysis"}
        self._status_label.setText(
            f"Holex Beast v1.0 · {mode_labels.get(mode, 'Chat')} Mode"
        )

    # ── File / Image Attachment ─────────────────────────────────────

    @pyqtSlot(str, str)
    def _on_image_attached(self, text: str, image_path: str) -> None:
        self._chat_area.show_messages()
        self._chat_area.add_message(
            "user", f"[Image: {Path(image_path).name}]\n{text}"
        )
        self._typing_indicator = self._chat_area.add_typing_indicator()
        self._input_bar.set_enabled(False)
        self._status_label.setText("Holex Beast v1.0 · Analysing image…")
        if self.agent:
            self._send_image_to_agent(text, image_path)
        else:
            QTimer.singleShot(1500, lambda: self._on_response_received(
                "Image analysis requires a connected LLM backend."
            ))

    @pyqtSlot(str)
    def _on_file_attached(self, path: str) -> None:
        if self.rag_pipeline:
            try:
                import asyncio as _aio
                _loop = _aio.new_event_loop()
                try:
                    _loop.run_until_complete(
                        self.rag_pipeline.ingest_file(path)
                    )
                finally:
                    _loop.close()
                self._settings_panel.rag_tab.add_document_item(
                    Path(path).name, path
                )
            except Exception as e:
                QMessageBox.warning(
                    self, "RAG Error", f"Failed to add document:\n{e}"
                )

    @pyqtSlot(str)
    def _on_rag_document_added(self, path: str) -> None:
        self._on_file_attached(path)

    @pyqtSlot(str)
    def _on_rag_document_removed(self, path: str) -> None:
        if self.rag_pipeline:
            try:
                self.rag_pipeline.remove_document(path)
            except Exception:
                pass

    # ── Settings Apply ──────────────────────────────────────────────

    @pyqtSlot(dict)
    def _on_settings_updated(self, settings: dict) -> None:
        """Apply LLM settings from the settings panel to the router."""
        if self.llm_router:
            if "temperature" in settings:
                self.llm_router.default_temperature = settings["temperature"]
            if "max_tokens" in settings:
                self.llm_router.default_max_tokens = settings["max_tokens"]
        self._status_label.setText("Holex Beast v1.0 · Settings applied ✓")

    # ── UI Toggles ──────────────────────────────────────────────────

    def _toggle_tools(self) -> None:
        vis = self._tools_panel.isVisible()
        self._tools_panel.setVisible(not vis)

    def _toggle_settings(self) -> None:
        vis = self._settings_panel.isVisible()
        self._settings_panel.setVisible(not vis)
        if not vis:
            # Overlay settings on the right side of the window
            self._settings_panel.setParent(self.centralWidget())
            w = 320
            self._settings_panel.setGeometry(
                self.centralWidget().width() - w, 48,
                w, self.centralWidget().height() - 74,
            )
            self._settings_panel.raise_()
            self._settings_panel.show()

    def _apply_theme(self, theme_name: str) -> None:
        from gui.styles.stylesheet import generate_stylesheet
        palette = get_palette(theme_name)
        self._current_theme = theme_name
        QApplication.instance().setStyleSheet(generate_stylesheet(palette))

    # ── Firebase / Account ──────────────────────────────────────────

    @pyqtSlot(str, str)
    def _on_login(self, email: str, password: str) -> None:
        if not email or not password:
            QMessageBox.warning(self, "Login", "Enter email and password.")
            return
        if self.storage_service and hasattr(self.storage_service, "authenticate"):
            try:
                self.storage_service.authenticate(email, password)
                self._settings_panel.account_tab.set_connected(email)
            except Exception as e:
                QMessageBox.warning(self, "Login Failed", str(e))
        else:
            QMessageBox.information(
                self, "Firebase",
                "Firebase not configured. Using local SQLite storage.\n"
                "Add Firebase credentials to .env to enable cloud sync.",
            )

    @pyqtSlot()
    def _on_sync(self) -> None:
        if self.storage_service and hasattr(self.storage_service, "sync"):
            try:
                self.storage_service.sync()
                self._settings_panel.account_tab.set_last_sync(
                    datetime.now().strftime("%H:%M:%S")
                )
            except Exception as e:
                QMessageBox.warning(self, "Sync Failed", str(e))

    # ── Keyboard Shortcuts ──────────────────────────────────────────

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(
            self._on_new_chat
        )
        QShortcut(QKeySequence("Ctrl+/"), self).activated.connect(
            self._toggle_tools
        )
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(
            self._toggle_settings
        )
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(
            lambda: self._on_center_voice_toggle(
                not self._control_center.is_listening
            )
        )
        QShortcut(QKeySequence(Qt.Key_Escape), self).activated.connect(
            self._on_escape
        )
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(
            lambda: self._input_bar.focus_input()
        )

    def _on_escape(self) -> None:
        if self._settings_panel.isVisible():
            self._settings_panel.setVisible(False)
        elif self._control_center.is_listening:
            self._stop_listening()
        else:
            self._on_stop_generation()

    # ── System Tray ─────────────────────────────────────────────────

    def _setup_system_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self)
        icon = self.windowIcon()
        if icon.isNull():
            icon = QApplication.style().standardIcon(
                QApplication.style().SP_ComputerIcon
            )
        self._tray.setIcon(icon)
        self._tray.setToolTip("Holex Beast")

        menu = QMenu()
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self._tray_show)
        menu.addAction(show_action)
        new_chat_action = QAction("New Chat", self)
        new_chat_action.triggered.connect(self._on_new_chat)
        menu.addAction(new_chat_action)
        menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._tray_quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._tray_show()

    def _tray_show(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _tray_quit(self) -> None:
        self._force_quit = True
        self.close()

    # ── Overrides ───────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Reposition settings overlay on resize
        if self._settings_panel.isVisible():
            w = 320
            self._settings_panel.setGeometry(
                self.centralWidget().width() - w, 48,
                w, self.centralWidget().height() - 74,
            )
        # Reposition voice overlay on resize
        if self._voice_overlay.isVisible():
            self._voice_overlay.setGeometry(self._chat_panel.rect())

    def closeEvent(self, event) -> None:
        if hasattr(self, "_tray") and not getattr(self, "_force_quit", False):
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "Holex Beast",
                "Running in background. Double-click tray icon to open.",
                QSystemTrayIcon.Information, 2000,
            )
            return
        # Cleanup
        if self.stt:
            try:
                self.stt.stop_listening()
            except Exception:
                pass
        if self.wake_word:
            try:
                self.wake_word.stop()
            except Exception:
                pass
        if self.llm_router:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.llm_router.shutdown())
                loop.close()
            except Exception:
                pass
        for worker in self._workers:
            if worker.isRunning():
                worker.quit()
                worker.wait(2000)
        if hasattr(self, "_tray"):
            self._tray.hide()
        event.accept()
