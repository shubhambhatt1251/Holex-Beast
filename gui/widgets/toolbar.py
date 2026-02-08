"""Top toolbar with model selector, provider badge, RAG toggle, and clear-chat."""

from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class ProviderBadge(QLabel):
    """Shows current LLM provider as a coloured badge."""

    PROVIDER_COLORS = {
        "groq": "#f97316",
        "gemini": "#3b82f6",
        "ollama": "#22c55e",
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ProviderBadge")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(24)
        self.setMinimumWidth(56)
        self.set_provider("groq")

    def set_provider(self, provider: str) -> None:
        color = self.PROVIDER_COLORS.get(provider.lower(), "#6c5ce7")
        self.setText(provider.upper())
        self.setStyleSheet(
            f"QLabel {{ background: {color}; color: white; "
            f"border-radius: 12px; font-size: 10px; font-weight: bold; "
            f"padding: 2px 10px; letter-spacing: 0.5px; }}"
        )


class ModelSelector(QComboBox):
    """Dropdown to pick a model — grouped by provider."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ModelSelector")
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)
        self.setCursor(Qt.PointingHandCursor)

    def populate(self, models_by_provider: Dict[str, List[str]]) -> None:
        """Fill with models grouped by provider header."""
        self.clear()
        for provider, models in models_by_provider.items():
            # Add separator/header
            self.addItem(f"--- {provider.upper()} ---")
            idx = self.count() - 1
            self.model().item(idx).setEnabled(False)  # non-selectable header
            for model in models:
                self.addItem(f"  {model}", userData={"provider": provider, "model": model})

    def get_selection(self) -> Optional[Dict[str, str]]:
        data = self.currentData()
        return data if isinstance(data, dict) else None


class Toolbar(QWidget):
    """
    Top toolbar:
    ┌─────────────────────────────────────────────────────┐
    │ ☰  Model [selector ▾]  GROQ  │  🔗 RAG  🗑 Clear  │
    └─────────────────────────────────────────────────────┘
    """

    model_changed = pyqtSignal(str, str)   # provider, model
    rag_toggled = pyqtSignal(bool)
    chat_cleared = pyqtSignal()
    sidebar_toggled = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Toolbar")
        self.setFixedHeight(52)
        self._rag_active = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Sidebar toggle
        self._sidebar_btn = QPushButton("☰")
        self._sidebar_btn.setObjectName("ToolbarBtn")
        self._sidebar_btn.setFixedSize(34, 34)
        self._sidebar_btn.setCursor(Qt.PointingHandCursor)
        self._sidebar_btn.setToolTip("Toggle sidebar")
        self._sidebar_btn.clicked.connect(self.sidebar_toggled.emit)
        layout.addWidget(self._sidebar_btn)

        # Model selector
        model_label = QLabel("Model:")
        model_label.setStyleSheet(
            "color: #9394a5; font-size: 11px; font-weight: bold; "
            "background: transparent; letter-spacing: 0.5px;"
        )
        layout.addWidget(model_label)

        self._model_selector = ModelSelector()
        self._model_selector.currentIndexChanged.connect(self._on_model_changed)
        layout.addWidget(self._model_selector)

        # Provider badge
        self._provider_badge = ProviderBadge()
        layout.addWidget(self._provider_badge)

        # Spacer
        layout.addStretch()

        # Status label (streaming / thinking / idle)
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("StatusLabel")
        self._status_label.setStyleSheet(
            "color: #22c55e; font-size: 10px; font-weight: bold; "
            "background: transparent; letter-spacing: 0.5px;"
        )
        layout.addWidget(self._status_label)

        # RAG toggle
        self._rag_btn = QPushButton("📚 RAG")
        self._rag_btn.setObjectName("RAGToggle")
        self._rag_btn.setCheckable(True)
        self._rag_btn.setFixedHeight(30)
        self._rag_btn.setCursor(Qt.PointingHandCursor)
        self._rag_btn.setToolTip("Toggle RAG context")
        self._rag_btn.clicked.connect(self._on_rag_toggle)
        layout.addWidget(self._rag_btn)

        # Clear chat
        clear_btn = QPushButton("🗑 Clear")
        clear_btn.setObjectName("ToolbarBtn")
        clear_btn.setFixedHeight(30)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setToolTip("Clear current conversation")
        clear_btn.clicked.connect(self.chat_cleared.emit)
        layout.addWidget(clear_btn)

    def _on_model_changed(self) -> None:
        selection = self._model_selector.get_selection()
        if selection:
            self._provider_badge.set_provider(selection["provider"])
            self.model_changed.emit(selection["provider"], selection["model"])

    def _on_rag_toggle(self) -> None:
        self._rag_active = self._rag_btn.isChecked()
        self.rag_toggled.emit(self._rag_active)

    def set_models(self, models_by_provider: Dict[str, List[str]]) -> None:
        self._model_selector.populate(models_by_provider)

    def set_status(self, text: str, color: str = "#9394a5") -> None:
        self._status_label.setText(text)
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: bold; "
            f"background: transparent; letter-spacing: 0.5px;"
        )

    def set_provider(self, provider: str) -> None:
        self._provider_badge.set_provider(provider)
