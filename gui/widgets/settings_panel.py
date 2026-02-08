"""Tabbed settings panel for LLM, voice, RAG, appearance, and account options."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# --- Helpers ---

class SettingsSection(QGroupBox):
    """Themed group box for a settings section."""

    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(title, parent)
        self.setObjectName("SettingsSection")
        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(12, 18, 12, 12)
        self._layout.setSpacing(10)
        self._layout.setLabelAlignment(Qt.AlignRight)

    def add_row(self, label: str, widget: QWidget) -> None:
        lbl = QLabel(label)
        lbl.setStyleSheet(
            "color: #9394a5; font-size: 11px; font-weight: bold; "
            "background: transparent;"
        )
        self._layout.addRow(lbl, widget)


class SliderWithValue(QWidget):
    """Slider with live value label."""

    value_changed = pyqtSignal(float)

    def __init__(
        self, min_val: float, max_val: float, default: float,
        step: float = 0.1, suffix: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._min = min_val
        self._max = max_val
        self._step = step
        self._suffix = suffix

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(int(min_val / step))
        self._slider.setMaximum(int(max_val / step))
        self._slider.setValue(int(default / step))
        self._slider.setFixedHeight(20)
        layout.addWidget(self._slider, 1)

        self._label = QLabel(f"{default}{suffix}")
        self._label.setFixedWidth(50)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(
            "color: #a78bfa; font-size: 11px; font-weight: bold; "
            "background: rgba(108,92,231,0.1); border-radius: 6px; "
            "padding: 2px 4px;"
        )
        layout.addWidget(self._label)

        self._slider.valueChanged.connect(self._on_change)

    def _on_change(self, raw: int) -> None:
        val = raw * self._step
        self._label.setText(f"{val:.1f}{self._suffix}")
        self.value_changed.emit(val)

    def value(self) -> float:
        return self._slider.value() * self._step


# --- Tab Panels ---

class LLMSettingsTab(QWidget):
    """LLM configuration: provider, model, temperature, max tokens."""

    settings_changed = pyqtSignal(dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(10)

        # Provider section
        provider_section = SettingsSection("Provider")

        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["Groq (Cloud)", "Gemini (Cloud)", "Ollama (Local)"])
        self._provider_combo.setMinimumHeight(28)
        provider_section.add_row("Provider:", self._provider_combo)

        self._model_combo = QComboBox()
        self._model_combo.setMinimumHeight(28)
        provider_section.add_row("Model:", self._model_combo)

        layout.addWidget(provider_section)

        # Generation section
        gen_section = SettingsSection("Generation")

        self._temp_slider = SliderWithValue(0.0, 2.0, 0.7, 0.1)
        gen_section.add_row("Temperature:", self._temp_slider)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(128, 32768)
        self._max_tokens.setValue(4096)
        self._max_tokens.setSingleStep(256)
        self._max_tokens.setMinimumHeight(28)
        gen_section.add_row("Max Tokens:", self._max_tokens)

        self._top_p_slider = SliderWithValue(0.0, 1.0, 0.9, 0.05)
        gen_section.add_row("Top P:", self._top_p_slider)

        self._stream_check = QCheckBox("Enable streaming")
        self._stream_check.setChecked(True)
        self._stream_check.setStyleSheet("color: #9394a5; background: transparent;")
        gen_section.add_row("Streaming:", self._stream_check)

        layout.addWidget(gen_section)

        # API keys section
        keys_section = SettingsSection("API Keys")

        self._groq_key = QLineEdit()
        self._groq_key.setPlaceholderText("gsk_...")
        self._groq_key.setEchoMode(QLineEdit.Password)
        self._groq_key.setMinimumHeight(28)
        keys_section.add_row("Groq Key:", self._groq_key)

        self._gemini_key = QLineEdit()
        self._gemini_key.setPlaceholderText("AIza...")
        self._gemini_key.setEchoMode(QLineEdit.Password)
        self._gemini_key.setMinimumHeight(28)
        keys_section.add_row("Gemini Key:", self._gemini_key)

        layout.addWidget(keys_section)
        layout.addStretch()

    def get_settings(self) -> dict:
        return {
            "provider": self._provider_combo.currentIndex(),
            "temperature": self._temp_slider.value(),
            "max_tokens": self._max_tokens.value(),
            "top_p": self._top_p_slider.value(),
            "streaming": self._stream_check.isChecked(),
        }


class VoiceSettingsTab(QWidget):
    """Voice configuration: TTS voice, STT, wake word."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(10)

        # TTS section
        tts_section = SettingsSection("Text-to-Speech")

        self._tts_engine = QComboBox()
        self._tts_engine.addItems(["Edge TTS (Neural)", "pyttsx3 (Offline)"])
        self._tts_engine.setMinimumHeight(28)
        tts_section.add_row("Engine:", self._tts_engine)

        self._tts_voice = QComboBox()
        self._tts_voice.addItems([
            "en-US-GuyNeural", "en-US-JennyNeural",
            "en-US-AriaNeural", "en-GB-SoniaNeural",
            "en-IN-NeerjaNeural", "en-AU-NatashaNeural",
        ])
        self._tts_voice.setMinimumHeight(28)
        tts_section.add_row("Voice:", self._tts_voice)

        self._tts_rate = SliderWithValue(0.5, 2.0, 1.0, 0.1, "x")
        tts_section.add_row("Speed:", self._tts_rate)

        layout.addWidget(tts_section)

        # STT section
        stt_section = SettingsSection("Speech-to-Text")

        self._stt_model = QComboBox()
        self._stt_model.addItems([
            "vosk-model-small-en-us-0.15",
            "vosk-model-en-us-0.22",
        ])
        self._stt_model.setMinimumHeight(28)
        stt_section.add_row("Model:", self._stt_model)

        self._auto_listen = QCheckBox("Auto-listen after response")
        self._auto_listen.setStyleSheet("color: #9394a5; background: transparent;")
        stt_section.add_row("Auto Listen:", self._auto_listen)

        layout.addWidget(stt_section)

        # Wake word
        wake_section = SettingsSection("Wake Word")

        self._wake_enabled = QCheckBox("Enable wake word detection")
        self._wake_enabled.setChecked(True)
        self._wake_enabled.setStyleSheet("color: #9394a5; background: transparent;")
        wake_section.add_row("Enabled:", self._wake_enabled)

        self._wake_word = QLineEdit("hey holex")
        self._wake_word.setMinimumHeight(28)
        wake_section.add_row("Phrase:", self._wake_word)

        layout.addWidget(wake_section)
        layout.addStretch()


class RAGSettingsTab(QWidget):
    """RAG configuration: document list, add/remove/search settings."""

    document_added = pyqtSignal(str)
    document_removed = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(10)

        # Documents section
        doc_section = SettingsSection("Knowledge Base Documents")

        self._doc_list = QListWidget()
        self._doc_list.setMinimumHeight(160)
        self._doc_list.setStyleSheet(
            "QListWidget { background: rgba(20,20,35,0.4); "
            "border: 1px solid rgba(108,92,231,0.2); border-radius: 8px; "
            "color: #9394a5; font-size: 11px; }"
        )
        doc_section._layout.addRow(self._doc_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Document")
        add_btn.setObjectName("RAGAddBtn")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFixedHeight(28)
        add_btn.clicked.connect(self._add_document)
        btn_row.addWidget(add_btn)

        remove_btn = QPushButton("− Remove")
        remove_btn.setObjectName("RAGRemoveBtn")
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setFixedHeight(28)
        remove_btn.clicked.connect(self._remove_document)
        btn_row.addWidget(remove_btn)

        doc_section._layout.addRow(btn_row)
        layout.addWidget(doc_section)

        # Search settings
        search_section = SettingsSection("Search Settings")

        self._top_k = QSpinBox()
        self._top_k.setRange(1, 20)
        self._top_k.setValue(5)
        self._top_k.setMinimumHeight(28)
        search_section.add_row("Top-K Results:", self._top_k)

        self._chunk_size = QSpinBox()
        self._chunk_size.setRange(100, 2000)
        self._chunk_size.setValue(500)
        self._chunk_size.setSingleStep(50)
        self._chunk_size.setMinimumHeight(28)
        search_section.add_row("Chunk Size:", self._chunk_size)

        self._chunk_overlap = QSpinBox()
        self._chunk_overlap.setRange(0, 500)
        self._chunk_overlap.setValue(50)
        self._chunk_overlap.setSingleStep(10)
        self._chunk_overlap.setMinimumHeight(28)
        search_section.add_row("Overlap:", self._chunk_overlap)

        layout.addWidget(search_section)
        layout.addStretch()

    def _add_document(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Add RAG Document", "",
            "Documents (*.pdf *.txt *.md *.docx *.csv *.json *.py *.html);;All (*)",
        )
        if path:
            from pathlib import Path
            name = Path(path).name
            self._doc_list.addItem(name)
            self._doc_list.item(self._doc_list.count() - 1).setData(Qt.UserRole, path)
            self.document_added.emit(path)

    def _remove_document(self) -> None:
        item = self._doc_list.currentItem()
        if item:
            path = item.data(Qt.UserRole)
            row = self._doc_list.row(item)
            self._doc_list.takeItem(row)
            if path:
                self.document_removed.emit(path)

    def add_document_item(self, name: str, path: str) -> None:
        self._doc_list.addItem(name)
        self._doc_list.item(self._doc_list.count() - 1).setData(Qt.UserRole, path)


class AppearanceTab(QWidget):
    """Theme and font settings."""

    theme_changed = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(10)

        theme_section = SettingsSection("Theme")

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["🌙 Dark", "🌃 Midnight", "☀️ Light"])
        self._theme_combo.setMinimumHeight(28)
        self._theme_combo.currentTextChanged.connect(
            lambda t: self.theme_changed.emit(t.split()[-1].lower())
        )
        theme_section.add_row("Theme:", self._theme_combo)

        self._font_size = QSpinBox()
        self._font_size.setRange(10, 20)
        self._font_size.setValue(13)
        self._font_size.setMinimumHeight(28)
        theme_section.add_row("Font Size:", self._font_size)

        self._accent_combo = QComboBox()
        self._accent_combo.addItems([
            "💜 Purple", "💙 Blue", "💚 Green", "🧡 Orange", "❤️ Red",
        ])
        self._accent_combo.setMinimumHeight(28)
        theme_section.add_row("Accent:", self._accent_combo)

        layout.addWidget(theme_section)

        # Window section
        win_section = SettingsSection("Window")

        self._compact = QCheckBox("Compact mode")
        self._compact.setStyleSheet("color: #9394a5; background: transparent;")
        win_section.add_row("Layout:", self._compact)

        self._animations = QCheckBox("Enable animations")
        self._animations.setChecked(True)
        self._animations.setStyleSheet("color: #9394a5; background: transparent;")
        win_section.add_row("Animations:", self._animations)

        layout.addWidget(win_section)
        layout.addStretch()


class AccountTab(QWidget):
    """Firebase account and sync settings."""

    login_requested = pyqtSignal(str, str)   # email, password
    sync_requested = pyqtSignal()
    logout_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(10)

        # Status section
        status_section = SettingsSection("Account Status")

        self._status_label = QLabel("⚫  Not connected (using local storage)")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            "color: #9394a5; font-size: 11px; background: transparent;"
        )
        status_section._layout.addRow(self._status_label)

        layout.addWidget(status_section)

        # Auth section
        auth_section = SettingsSection("Firebase Authentication")

        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("email@example.com")
        self._email_input.setMinimumHeight(28)
        auth_section.add_row("Email:", self._email_input)

        self._pass_input = QLineEdit()
        self._pass_input.setPlaceholderText("Password")
        self._pass_input.setEchoMode(QLineEdit.Password)
        self._pass_input.setMinimumHeight(28)
        auth_section.add_row("Password:", self._pass_input)

        btn_row = QHBoxLayout()

        login_btn = QPushButton("🔐 Login / Register")
        login_btn.setCursor(Qt.PointingHandCursor)
        login_btn.setFixedHeight(32)
        login_btn.setStyleSheet(
            "QPushButton { background: #6c5ce7; color: white; "
            "border-radius: 8px; font-weight: bold; font-size: 11px; } "
            "QPushButton:hover { background: #5b4bd5; }"
        )
        login_btn.clicked.connect(
            lambda: self.login_requested.emit(
                self._email_input.text(), self._pass_input.text()
            )
        )
        btn_row.addWidget(login_btn)

        logout_btn = QPushButton("Logout")
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setFixedHeight(32)
        logout_btn.setStyleSheet(
            "QPushButton { background: rgba(239,68,68,0.15); color: #ef4444; "
            "border-radius: 8px; font-weight: bold; font-size: 11px; } "
            "QPushButton:hover { background: rgba(239,68,68,0.3); }"
        )
        logout_btn.clicked.connect(self.logout_requested.emit)
        btn_row.addWidget(logout_btn)

        auth_section._layout.addRow(btn_row)
        layout.addWidget(auth_section)

        # Sync section
        sync_section = SettingsSection("Cloud Sync")

        sync_btn = QPushButton("☁️  Sync Conversations")
        sync_btn.setCursor(Qt.PointingHandCursor)
        sync_btn.setFixedHeight(32)
        sync_btn.setStyleSheet(
            "QPushButton { background: rgba(59,130,246,0.15); color: #3b82f6; "
            "border-radius: 8px; font-weight: bold; font-size: 11px; } "
            "QPushButton:hover { background: rgba(59,130,246,0.3); }"
        )
        sync_btn.clicked.connect(self.sync_requested.emit)
        sync_section._layout.addRow(sync_btn)

        self._last_sync = QLabel("Last synced: Never")
        self._last_sync.setStyleSheet(
            "color: #5c5d72; font-size: 10px; background: transparent;"
        )
        sync_section._layout.addRow(self._last_sync)

        layout.addWidget(sync_section)
        layout.addStretch()

    def set_connected(self, email: str) -> None:
        self._status_label.setText(f"🟢  Connected as {email}")
        self._status_label.setStyleSheet(
            "color: #22c55e; font-size: 11px; background: transparent;"
        )

    def set_disconnected(self) -> None:
        self._status_label.setText("⚫  Not connected (using local storage)")
        self._status_label.setStyleSheet(
            "color: #9394a5; font-size: 11px; background: transparent;"
        )

    def set_last_sync(self, timestamp: str) -> None:
        self._last_sync.setText(f"Last synced: {timestamp}")


# --- Main Settings Panel ---

class SettingsPanel(QWidget):
    """
    Right-side settings panel with tabs.
    Slides in/out with animation.
    """

    theme_changed = pyqtSignal(str)
    settings_updated = pyqtSignal(dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("SettingsPanel")
        self.setFixedWidth(340)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet(
            "QFrame { background: rgba(20,20,35,0.6); "
            "border-bottom: 1px solid rgba(108,92,231,0.15); }"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 0, 14, 0)

        title = QLabel("⚙  Settings")
        title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e1e2f0; "
            "background: transparent;"
        )
        header_layout.addWidget(title)

        header_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; "
            "color: #5c5d72; font-size: 14px; } "
            "QPushButton:hover { color: #ef4444; }"
        )
        close_btn.clicked.connect(lambda: self.setVisible(False))
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setObjectName("SettingsTabs")
        self._tabs.setDocumentMode(True)

        # Scrollable tabs
        self._llm_tab = LLMSettingsTab()
        self._voice_tab = VoiceSettingsTab()
        self._rag_tab = RAGSettingsTab()
        self._appearance_tab = AppearanceTab()
        self._account_tab = AccountTab()

        self._tabs.addTab(self._wrap_scroll(self._llm_tab), "🧠 LLM")
        self._tabs.addTab(self._wrap_scroll(self._voice_tab), "🔊 Voice")
        self._tabs.addTab(self._wrap_scroll(self._rag_tab), "📚 RAG")
        self._tabs.addTab(self._wrap_scroll(self._appearance_tab), "🎨 Theme")
        self._tabs.addTab(self._wrap_scroll(self._account_tab), "👤 Account")

        # Forward signals
        self._appearance_tab.theme_changed.connect(self.theme_changed.emit)

        layout.addWidget(self._tabs)

    def _wrap_scroll(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(widget)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        return scroll

    @property
    def llm_tab(self) -> LLMSettingsTab:
        return self._llm_tab

    @property
    def voice_tab(self) -> VoiceSettingsTab:
        return self._voice_tab

    @property
    def rag_tab(self) -> RAGSettingsTab:
        return self._rag_tab

    @property
    def appearance_tab(self) -> AppearanceTab:
        return self._appearance_tab

    @property
    def account_tab(self) -> AccountTab:
        return self._account_tab
