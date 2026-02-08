"""Welcome/landing screen shown when no conversation is active."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QGraphicsOpacityEffect,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_SUGGESTIONS = [
    ("Write a Python script", "to sort a list of dictionaries by key"),
    ("What's the weather", "in New York today?"),
    ("Explain how", "async/await works in Python"),
    ("Search the web", "for the latest AI news"),
    ("Summarize this topic", "using Wikipedia: quantum computing"),
    ("Open an app", "launch Notepad on my PC"),
]


class _SuggestionCard(QPushButton):
    """Clickable suggestion chip."""

    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self._full_text = f"{title} {subtitle}"
        self.setText(f"{title}\n{subtitle}")
        self.setObjectName("SuggestionCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(64)
        self.setStyleSheet("""
            #SuggestionCard {
                background: rgba(108,92,231,0.06);
                border: 1px solid rgba(108,92,231,0.15);
                border-radius: 12px;
                padding: 10px 16px;
                text-align: left;
                font-size: 12px;
                color: #9a9ab0;
            }
            #SuggestionCard:hover {
                background: rgba(108,92,231,0.14);
                border-color: rgba(108,92,231,0.35);
                color: #c0c0d0;
            }
        """)


class WelcomeScreen(QWidget):
    """
    Landing screen with a title and 6 suggestion cards.
    Emits `prompt_selected` when a suggestion is clicked.
    """

    prompt_selected = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("WelcomeScreen")
        self._build_ui()
        self._fade_in()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(60, 0, 60, 60)
        root.setSpacing(0)

        root.addStretch(2)

        title = QLabel("Ask Holex anything")
        title.setObjectName("WelcomeTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 30px; font-weight: 600; "
            "color: #7a7a8e; background: transparent; "
            "letter-spacing: -0.3px;"
        )
        root.addWidget(title)

        root.addSpacing(32)

        # Suggestion grid — 3 columns × 2 rows
        grid = QGridLayout()
        grid.setSpacing(12)
        for idx, (t, sub) in enumerate(_SUGGESTIONS):
            card = _SuggestionCard(t, sub)
            card.clicked.connect(lambda _, text=f"{t} {sub}": self.prompt_selected.emit(text))
            grid.addWidget(card, idx // 3, idx % 3)

        root.addLayout(grid)
        root.addStretch(3)

    def _fade_in(self) -> None:
        fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(fx)
        self._anim = QPropertyAnimation(fx, b"opacity")
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(600)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()
