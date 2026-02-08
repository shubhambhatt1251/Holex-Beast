"""Sidebar with conversation history, search, theme toggle, and user profile."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ConversationItem(QFrame):
    """A single conversation in the sidebar list."""

    clicked = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(
        self,
        conv_id: str,
        title: str,
        preview: str = "",
        message_count: int = 0,
        is_active: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.conv_id = conv_id
        self.title_text = title
        self._is_active = is_active
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("ConvItemActive" if is_active else "ConvItem")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(8)

        # Chat icon
        icon = QLabel("💬")
        icon.setStyleSheet("font-size: 12px; background: transparent;")
        icon.setFixedWidth(16)
        layout.addWidget(icon)

        # Title
        title_label = QLabel(title[:28] + ("..." if len(title) > 28 else ""))
        title_label.setObjectName("ConvTitle")
        title_label.setStyleSheet("background: transparent;")
        layout.addWidget(title_label, 1)

        # Delete button (hidden)
        self._delete_btn = QPushButton("×")
        self._delete_btn.setFixedSize(18, 18)
        self._delete_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #5c5d72; "
            "border: none; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { color: #ef4444; }"
        )
        self._delete_btn.setCursor(Qt.PointingHandCursor)
        self._delete_btn.setVisible(False)
        self._delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.conv_id))
        layout.addWidget(self._delete_btn)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.conv_id)
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self._delete_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._delete_btn.setVisible(False)
        super().leaveEvent(event)


class Sidebar(QWidget):
    """
    Left sidebar:
    ┌─────────────────────────┐
    │ 🔍 Search conversations │
    │ [+ New chat]            │
    │                         │
    │ 🕐 History              │
    │ -- January --           │
    │  💬 Conversation 1      │
    │  💬 Conversation 2      │
    │                         │
    │ ─────────────────────── │
    │ 🖥️ ☀️ ✨  Theme         │
    │ 👤 shubhambhatt7938     │
    │    email@gmail.com      │
    └─────────────────────────┘
    """

    new_chat_requested = pyqtSignal()
    conversation_selected = pyqtSignal(str)
    conversation_deleted = pyqtSignal(str)
    settings_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal()
    theme_selected = pyqtSignal(str)  # "dark" | "light" | "auto"

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(260)
        self._items: dict[str, ConversationItem] = {}
        self._current_theme = "dark"
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search Bar
        search_frame = QFrame()
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(12, 12, 12, 6)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search conversations...")
        self._search.setObjectName("SidebarSearch")
        self._search.textChanged.connect(self._filter_conversations)
        search_layout.addWidget(self._search)
        layout.addWidget(search_frame)

        # New Chat Button
        self._new_chat_btn = QPushButton("✨  New chat")
        self._new_chat_btn.setObjectName("NewChatBtn")
        self._new_chat_btn.setCursor(Qt.PointingHandCursor)
        self._new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        layout.addWidget(self._new_chat_btn)

        # History Label
        history_frame = QFrame()
        hist_layout = QHBoxLayout(history_frame)
        hist_layout.setContentsMargins(14, 12, 14, 4)
        hist_layout.setSpacing(6)

        hist_icon = QLabel("🕐")
        hist_icon.setStyleSheet("font-size: 12px; background: transparent;")
        hist_layout.addWidget(hist_icon)

        hist_label = QLabel("History")
        hist_label.setObjectName("HistoryLabel")
        hist_label.setStyleSheet(
            "color: #9394a5; font-size: 12px; font-weight: 600; "
            "background: transparent; letter-spacing: 0.3px;"
        )
        hist_layout.addWidget(hist_label)
        hist_layout.addStretch()
        layout.addWidget(history_frame)

        # Conversation List
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(6, 2, 6, 2)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_container)
        layout.addWidget(self._scroll, 1)

        # Bottom Section
        bottom = QFrame()
        bottom.setObjectName("SidebarBottom")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 10)
        bottom_layout.setSpacing(8)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.06);")
        bottom_layout.addWidget(sep)

        # Theme toggle row (3 icons)
        theme_row = QHBoxLayout()
        theme_row.setSpacing(4)
        theme_row.setAlignment(Qt.AlignLeft)

        self._theme_dark_btn = QPushButton("🖥️")
        self._theme_dark_btn.setObjectName("ThemeBtn")
        self._theme_dark_btn.setFixedSize(32, 28)
        self._theme_dark_btn.setCursor(Qt.PointingHandCursor)
        self._theme_dark_btn.setToolTip("Dark theme")
        self._theme_dark_btn.setCheckable(True)
        self._theme_dark_btn.setChecked(True)
        self._theme_dark_btn.clicked.connect(lambda: self._on_theme_select("dark"))
        theme_row.addWidget(self._theme_dark_btn)

        self._theme_light_btn = QPushButton("☀️")
        self._theme_light_btn.setObjectName("ThemeBtn")
        self._theme_light_btn.setFixedSize(32, 28)
        self._theme_light_btn.setCursor(Qt.PointingHandCursor)
        self._theme_light_btn.setToolTip("Light theme")
        self._theme_light_btn.setCheckable(True)
        self._theme_light_btn.clicked.connect(lambda: self._on_theme_select("light"))
        theme_row.addWidget(self._theme_light_btn)

        self._theme_auto_btn = QPushButton("✨")
        self._theme_auto_btn.setObjectName("ThemeBtn")
        self._theme_auto_btn.setFixedSize(32, 28)
        self._theme_auto_btn.setCursor(Qt.PointingHandCursor)
        self._theme_auto_btn.setToolTip("Auto / Midnight theme")
        self._theme_auto_btn.setCheckable(True)
        self._theme_auto_btn.clicked.connect(lambda: self._on_theme_select("midnight"))
        theme_row.addWidget(self._theme_auto_btn)

        theme_row.addStretch()
        bottom_layout.addLayout(theme_row)

        # User profile
        profile_frame = QFrame()
        profile_layout = QHBoxLayout(profile_frame)
        profile_layout.setContentsMargins(0, 4, 0, 0)
        profile_layout.setSpacing(8)

        # Avatar circle
        avatar = QLabel("S")
        avatar.setObjectName("ProfileAvatar")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "QLabel { background: #6c5ce7; color: white; "
            "border-radius: 16px; font-size: 13px; font-weight: bold; }"
        )
        profile_layout.addWidget(avatar)

        # Name + email
        info_col = QVBoxLayout()
        info_col.setSpacing(0)

        name_label = QLabel("shubhambhatt7938")
        name_label.setStyleSheet(
            "color: #e4e4ed; font-size: 11px; font-weight: 600; "
            "background: transparent;"
        )
        info_col.addWidget(name_label)

        email_label = QLabel("shubhambhatt7938@gmail.com")
        email_label.setStyleSheet(
            "color: #5c5d72; font-size: 9px; background: transparent;"
        )
        info_col.addWidget(email_label)

        profile_layout.addLayout(info_col)
        profile_layout.addStretch()
        bottom_layout.addWidget(profile_frame)

        layout.addWidget(bottom)

    # Theme selection

    def _on_theme_select(self, theme: str) -> None:
        self._current_theme = theme
        self._theme_dark_btn.setChecked(theme == "dark")
        self._theme_light_btn.setChecked(theme == "light")
        self._theme_auto_btn.setChecked(theme == "midnight")
        self.theme_selected.emit(theme)
        self.theme_toggle_requested.emit()

    # Conversation management

    def add_conversation(
        self, conv_id: str, title: str, preview: str = "",
        message_count: int = 0, is_active: bool = False,
    ) -> None:
        item = ConversationItem(
            conv_id=conv_id, title=title, preview=preview,
            message_count=message_count, is_active=is_active,
        )
        item.clicked.connect(self.conversation_selected.emit)
        item.delete_requested.connect(self.conversation_deleted.emit)
        self._list_layout.insertWidget(0, item)
        self._items[conv_id] = item

    def add_date_header(self, text: str) -> None:
        """Add a date group header like 'January'."""
        header = QLabel(text)
        header.setStyleSheet(
            "color: #5c5d72; font-size: 10px; font-weight: 700; "
            "letter-spacing: 0.5px; padding: 8px 12px 4px 12px; "
            "background: transparent;"
        )
        count = self._list_layout.count()
        self._list_layout.insertWidget(max(count - 1, 0), header)

    def set_active(self, conv_id: str) -> None:
        for cid, item in self._items.items():
            item._is_active = cid == conv_id
            item.setObjectName("ConvItemActive" if cid == conv_id else "ConvItem")
            item.style().unpolish(item)
            item.style().polish(item)

    def remove_conversation(self, conv_id: str) -> None:
        if conv_id in self._items:
            item = self._items.pop(conv_id)
            self._list_layout.removeWidget(item)
            item.deleteLater()

    def clear_conversations(self) -> None:
        for item in self._items.values():
            self._list_layout.removeWidget(item)
            item.deleteLater()
        self._items.clear()

    def update_conversations(self, conversations: list[dict]) -> None:
        self.clear_conversations()
        for conv in conversations:
            self.add_conversation(
                conv_id=conv.get("id", ""),
                title=conv.get("title", "New Chat"),
                preview=conv.get("preview", ""),
                message_count=conv.get("message_count", 0),
                is_active=conv.get("is_active", False),
            )

    def _filter_conversations(self, text: str) -> None:
        for conv_id, item in self._items.items():
            visible = not text or text.lower() in item.title_text.lower()
            item.setVisible(visible)
