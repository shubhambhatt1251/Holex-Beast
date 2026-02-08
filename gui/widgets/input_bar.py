"""Floating input bar with mode toggles, model selector, voice, and attachment buttons."""

from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class AutoExpandTextEdit(QTextEdit):
    """
    Text input that auto-expands vertically as you type,
    up to a maximum height. Enter sends, Shift+Enter newline.
    """

    submit_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("InputField")
        self.setAcceptRichText(False)
        self.setPlaceholderText("Let's begin...")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumHeight(42)
        self.setMaximumHeight(150)

        self.document().contentsChanged.connect(self._auto_resize)

    def _auto_resize(self) -> None:
        """Resize to fit content."""
        doc_height = self.document().size().height()
        new_height = max(42, min(int(doc_height) + 14, 150))
        self.setFixedHeight(new_height)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Enter to send, Shift+Enter for new line."""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submit_requested.emit()
        else:
            super().keyPressEvent(event)

    def get_text(self) -> str:
        return self.toPlainText().strip()

    def clear_text(self) -> None:
        self.clear()
        self.setFixedHeight(42)


class ModeToggleButton(QPushButton):
    """A small icon toggle button for mode selection (web/chat/sparkle)."""

    def __init__(self, icon_text: str, tooltip: str, parent=None):
        super().__init__(icon_text, parent)
        self.setObjectName("ModeToggle")
        self.setFixedSize(32, 32)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)


class InputBar(QWidget):
    """
    Floating input bar:
    ┌─────────────────────────────────────────────┐
    │  [text input area]                          │
    │  🌐 💬 ✨  │ Holex Core ▾ │  📎  🎤/⬛    │
    └─────────────────────────────────────────────┘
    """

    message_submitted = pyqtSignal(str)
    voice_toggled = pyqtSignal(bool)
    file_attached = pyqtSignal(str)
    image_attached = pyqtSignal(str, str)   # (text, image_path)
    mode_changed = pyqtSignal(str)     # "web" | "chat" | "sparkle"
    model_changed = pyqtSignal(str, str)  # provider, model
    stop_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("InputContainer")
        self._is_voice_active = False
        self._is_generating = False
        self._current_mode = "chat"
        self._pending_image: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        # Outer layout with centering margins
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 14)
        outer.setSpacing(0)

        # Floating card container
        self._card = QFrame()
        self._card.setObjectName("InputCard")
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(8)

        # Attachment preview (hidden by default)
        self._attach_preview = QFrame()
        self._attach_preview.setVisible(False)
        self._attach_preview.setStyleSheet(
            "QFrame { background: rgba(108,92,231,0.08); "
            "border-radius: 6px; padding: 4px 8px; }"
        )
        ap_layout = QHBoxLayout(self._attach_preview)
        ap_layout.setContentsMargins(6, 3, 6, 3)
        self._attach_label = QLabel("📎 file.txt")
        self._attach_label.setStyleSheet(
            "color: #9394a5; font-size: 11px; background: transparent;"
        )
        ap_layout.addWidget(self._attach_label)
        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(16, 16)
        rm_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; "
            "color: #5c5d72; font-size: 10px; } "
            "QPushButton:hover { color: #ef4444; }"
        )
        rm_btn.clicked.connect(self._remove_attachment)
        ap_layout.addWidget(rm_btn)
        ap_layout.addStretch()
        card_layout.addWidget(self._attach_preview)

        # Text input area
        self._input = AutoExpandTextEdit()
        self._input.submit_requested.connect(self._on_submit)
        card_layout.addWidget(self._input)

        # Bottom row: mode toggles | model selector | attach | mic/stop
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)

        # Mode toggle buttons
        self._web_btn = ModeToggleButton("🌐", "Web Search mode")
        self._chat_btn = ModeToggleButton("💬", "Chat mode")
        self._sparkle_btn = ModeToggleButton("✨", "AI Analysis mode")

        self._chat_btn.setChecked(True)  # Default mode

        self._web_btn.clicked.connect(lambda: self._set_mode("web"))
        self._chat_btn.clicked.connect(lambda: self._set_mode("chat"))
        self._sparkle_btn.clicked.connect(lambda: self._set_mode("sparkle"))

        bottom_row.addWidget(self._web_btn)
        bottom_row.addWidget(self._chat_btn)
        bottom_row.addWidget(self._sparkle_btn)

        # Small divider
        div = QFrame()
        div.setFixedSize(1, 20)
        div.setStyleSheet("background: rgba(255,255,255,0.08);")
        bottom_row.addWidget(div)

        # Model selector dropdown (compact)
        self._model_selector = QComboBox()
        self._model_selector.setObjectName("InputModelSelector")
        self._model_selector.setMinimumWidth(120)
        self._model_selector.setMaximumWidth(160)
        self._model_selector.setCursor(Qt.PointingHandCursor)
        self._model_selector.addItem("Holex Core")
        self._model_selector.currentIndexChanged.connect(self._on_model_changed)
        bottom_row.addWidget(self._model_selector)

        bottom_row.addStretch()

        # Attach button
        self._attach_btn = QPushButton("📎")
        self._attach_btn.setObjectName("AttachBtn")
        self._attach_btn.setFixedSize(32, 32)
        self._attach_btn.setCursor(Qt.PointingHandCursor)
        self._attach_btn.setToolTip("Attach file")
        self._attach_btn.clicked.connect(self._open_file_dialog)
        bottom_row.addWidget(self._attach_btn)

        # Voice / Stop button
        self._voice_btn = QPushButton("🎤")
        self._voice_btn.setObjectName("VoiceBtn")
        self._voice_btn.setFixedSize(36, 36)
        self._voice_btn.setCheckable(True)
        self._voice_btn.setCursor(Qt.PointingHandCursor)
        self._voice_btn.setToolTip("Voice input")
        self._voice_btn.clicked.connect(self._on_voice_toggle)
        bottom_row.addWidget(self._voice_btn)

        # Stop button (hidden, shown during generation)
        self._stop_btn = QPushButton("⬛")
        self._stop_btn.setObjectName("StopBtn")
        self._stop_btn.setFixedSize(36, 36)
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        self._stop_btn.setToolTip("Stop generating")
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setVisible(False)
        bottom_row.addWidget(self._stop_btn)

        card_layout.addLayout(bottom_row)
        outer.addWidget(self._card)

        # Hint text
        hint = QLabel("Holex can make mistakes. Verify important info.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(
            "color: #3a3a50; font-size: 10px; "
            "background: transparent; padding-top: 4px;"
        )
        outer.addWidget(hint)

    # Mode handling

    def _set_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._web_btn.setChecked(mode == "web")
        self._chat_btn.setChecked(mode == "chat")
        self._sparkle_btn.setChecked(mode == "sparkle")
        self.mode_changed.emit(mode)

    # Model handling

    def set_models(self, models_by_provider: Dict[str, List[str]]) -> None:
        """Populate model dropdown."""
        self._model_selector.blockSignals(True)
        self._model_selector.clear()
        for provider, models in models_by_provider.items():
            for model in models:
                display = model.replace("-", " ").title()
                if len(display) > 22:
                    display = display[:20] + "…"
                self._model_selector.addItem(
                    f"{display}", userData={"provider": provider, "model": model}
                )
        self._model_selector.blockSignals(False)

    def _on_model_changed(self) -> None:
        data = self._model_selector.currentData()
        if isinstance(data, dict):
            self.model_changed.emit(data["provider"], data["model"])

    # Submit / Stop

    def _on_submit(self) -> None:
        text = self._input.get_text()
        if self._pending_image:
            # Send image + text to vision handler
            self.image_attached.emit(text or "Describe this image.", self._pending_image)
            self._input.clear_text()
            self._remove_attachment()
        elif text:
            self.message_submitted.emit(text)
            self._input.clear_text()

    def _on_stop(self) -> None:
        self.stop_requested.emit()
        self.set_generating(False)

    def set_generating(self, generating: bool) -> None:
        """Switch between voice button and stop button."""
        self._is_generating = generating
        self._voice_btn.setVisible(not generating)
        self._stop_btn.setVisible(generating)
        if generating:
            self._input.setPlaceholderText("Ask a new question...")
        else:
            self._input.setPlaceholderText("Ask a new question...")

    # Voice

    def _on_voice_toggle(self) -> None:
        self._is_voice_active = self._voice_btn.isChecked()
        self.voice_toggled.emit(self._is_voice_active)

    # File

    def _open_file_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Attach File",  "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp);;"
            "Documents (*.pdf *.txt *.md *.docx *.csv *.json *.py *.html);;"
            "All Files (*)",
        )
        if file_path:
            from pathlib import Path
            ext = Path(file_path).suffix.lower()
            image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
            name = Path(file_path).name

            if ext in image_exts:
                self._pending_image = file_path
                self._attach_label.setText(f"\U0001f5bc {name}")
                self._attach_preview.setVisible(True)
                self._input.setPlaceholderText("Describe what you want to know about this image...")
            else:
                self._pending_image = None
                self._attach_label.setText(f"\U0001f4ce {name}")
                self._attach_preview.setVisible(True)
                self.file_attached.emit(file_path)

    def _remove_attachment(self) -> None:
        self._attach_preview.setVisible(False)
        self._pending_image = None
        self._input.setPlaceholderText("Ask a new question...")

    # Public API

    def set_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        if not enabled:
            self.set_generating(True)
        else:
            self.set_generating(False)

    def set_voice_active(self, active: bool) -> None:
        self._voice_btn.setChecked(active)
        self._is_voice_active = active

    def set_placeholder(self, text: str) -> None:
        self._input.setPlaceholderText(text)

    def focus_input(self) -> None:
        self._input.setFocus()
