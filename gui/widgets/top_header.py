"""Minimal top header bar with logo, sidebar toggle, new-chat, and quick actions."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class TopHeader(QWidget):
    """
    Minimal top header bar:
    ┌──────────────────────────────────────────────────────────────┐
    │ ✳  ☰  +  │                 │ Free Plan │ Upgrade │ 🔍 ⚙ 🟣  │
    └──────────────────────────────────────────────────────────────┘
    """

    sidebar_toggled = pyqtSignal()
    new_chat_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    search_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("TopHeader")
        self.setFixedHeight(46)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(4)

        # Logo icon (purple sparkle)
        logo = QPushButton("✦")
        logo.setObjectName("HeaderLogo")
        logo.setFixedSize(30, 30)
        logo.setStyleSheet(
            "QPushButton { background: transparent; border: none; "
            "font-size: 18px; color: #6c5ce7; }"
        )
        layout.addWidget(logo)

        layout.addSpacing(2)

        # Sidebar toggle
        self._sidebar_btn = QPushButton("☰")
        self._sidebar_btn.setObjectName("HeaderBtn")
        self._sidebar_btn.setFixedSize(30, 30)
        self._sidebar_btn.setCursor(Qt.PointingHandCursor)
        self._sidebar_btn.setToolTip("Toggle sidebar")
        self._sidebar_btn.clicked.connect(self.sidebar_toggled.emit)
        layout.addWidget(self._sidebar_btn)

        # New chat button
        self._new_chat_btn = QPushButton("+")
        self._new_chat_btn.setObjectName("HeaderBtn")
        self._new_chat_btn.setFixedSize(30, 30)
        self._new_chat_btn.setCursor(Qt.PointingHandCursor)
        self._new_chat_btn.setToolTip("New chat")
        self._new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        layout.addWidget(self._new_chat_btn)

        # Spacer
        layout.addStretch()

        # "Free Plan" badge
        plan_badge = QLabel("Free Plan")
        plan_badge.setObjectName("PlanBadge")
        plan_badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(plan_badge)

        layout.addSpacing(4)

        # "Upgrade" button
        upgrade_btn = QPushButton("Upgrade")
        upgrade_btn.setObjectName("UpgradeBtn")
        upgrade_btn.setCursor(Qt.PointingHandCursor)
        upgrade_btn.setFixedHeight(26)
        layout.addWidget(upgrade_btn)

        layout.addSpacing(8)

        # Search icon
        search_btn = QPushButton("🔍")
        search_btn.setObjectName("HeaderBtn")
        search_btn.setFixedSize(30, 30)
        search_btn.setCursor(Qt.PointingHandCursor)
        search_btn.setToolTip("Search")
        search_btn.clicked.connect(self.search_requested.emit)
        layout.addWidget(search_btn)

        # Settings icon
        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("HeaderBtn")
        settings_btn.setFixedSize(30, 30)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(settings_btn)

        # User avatar
        avatar = QPushButton("S")
        avatar.setObjectName("HeaderAvatar")
        avatar.setFixedSize(30, 30)
        avatar.setCursor(Qt.PointingHandCursor)
        avatar.setToolTip("Profile")
        layout.addWidget(avatar)

    # Status (backward compat with toolbar.set_status)

    def set_status(self, text: str, color: str = "#9394a5") -> None:
        """Compatibility stub — status shown elsewhere now."""
        pass

    def set_provider(self, provider: str) -> None:
        """Compatibility stub — provider shown in input bar."""
        pass
