"""
Chat bubble widgets — premium markdown rendering, code blocks with
copy button, typing animation, and glass-style action buttons.
"""

from __future__ import annotations

import html
import re
from typing import Optional

from PyQt5.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class MessageBubble(QWidget):
    """
    A single chat message bubble.
    - User: right-aligned purple gradient bubble with avatar
    - AI: left-aligned with "Holex AI" header, copy + regen buttons
    """

    regenerate_requested = pyqtSignal()

    def __init__(
        self,
        text: str,
        is_user: bool = True,
        avatar: str = "",
        timestamp: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.is_user = is_user
        self._full_text = text
        self._current_text = text
        self._char_index = 0
        self._typing_timer: Optional[QTimer] = None

        self._build_ui(text, avatar, timestamp)
        self._animate_entrance()

    def _build_ui(self, text: str, avatar: str, timestamp: str) -> None:
        # Use a vertical outer layout for AI (bubble row + action row)
        # or a horizontal layout for user (stretch + bubble + avatar)

        if self.is_user:
            self._build_user(text, avatar, timestamp)
        else:
            self._build_ai(text, avatar, timestamp)

    def _build_user(self, text, avatar, timestamp):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(10)
        layout.addStretch()

        # Bubble
        bubble = QFrame()
        bubble.setObjectName("UserBubble")
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)

        self._content = QLabel()
        self._content.setWordWrap(True)
        self._content.setTextFormat(Qt.RichText)
        self._content.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        self._content.setOpenExternalLinks(True)
        self._content.setStyleSheet(
            "background: transparent; padding: 2px; "
            "line-height: 1.5; font-size: 14px; color: #ffffff;"
        )
        self._content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._content.setText(self._render_markdown(text))
        bl.addWidget(self._content)

        layout.addWidget(bubble)

        # Avatar
        av = QLabel("👤")
        av.setFixedSize(28, 28)
        av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet(
            "font-size: 14px; background: rgba(255,255,255,0.06); "
            "border-radius: 14px;"
        )
        layout.addWidget(av, 0, Qt.AlignTop)

    def _build_ai(self, text, avatar, timestamp):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # Message row
        msg_row = QHBoxLayout()
        msg_row.setContentsMargins(16, 4, 16, 4)
        msg_row.setSpacing(10)

        bubble = QFrame()
        bubble.setObjectName("AIBubble")
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(4)

        # AI header
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        name = QLabel("✦ Holex AI")
        name.setObjectName("AIName")
        name.setStyleSheet(
            "font-size: 13px; font-weight: 700; "
            "color: #e4e4ed; background: transparent;"
        )
        hdr.addWidget(name)
        hdr.addStretch()
        bl.addLayout(hdr)

        # Content
        self._content = QLabel()
        self._content.setWordWrap(True)
        self._content.setTextFormat(Qt.RichText)
        self._content.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        self._content.setOpenExternalLinks(True)
        self._content.setStyleSheet(
            "background: transparent; padding: 2px; "
            "line-height: 1.5; font-size: 14px;"
        )
        self._content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._content.setText(self._render_markdown(text))
        bl.addWidget(self._content)

        msg_row.addWidget(bubble)
        msg_row.addStretch()
        outer.addLayout(msg_row)

        # Action buttons row
        action_row = QHBoxLayout()
        action_row.setContentsMargins(20, 0, 20, 0)
        action_row.setSpacing(6)

        # Copy button
        self._copy_btn = QPushButton("📋 Copy")
        self._copy_btn.setObjectName("BubbleActionBtn")
        self._copy_btn.setFixedHeight(24)
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        self._copy_btn.clicked.connect(self._copy_text)
        action_row.addWidget(self._copy_btn)

        # Regenerate button
        self._regen_btn = QPushButton("↻ Retry")
        self._regen_btn.setObjectName("BubbleActionBtn")
        self._regen_btn.setFixedHeight(24)
        self._regen_btn.setCursor(Qt.PointingHandCursor)
        self._regen_btn.clicked.connect(self.regenerate_requested.emit)
        action_row.addWidget(self._regen_btn)

        action_row.addStretch()

        self._action_widget = QWidget()
        self._action_widget.setLayout(action_row)
        self._action_widget.setVisible(True)
        outer.addWidget(self._action_widget)

    def _render_markdown(self, text: str) -> str:
        """Convert markdown to premium HTML for QLabel."""
        if not text:
            return ""

        text = html.escape(text)

        # Code blocks
        def _code_block(m):
            lang = m.group(1) or ""
            code = m.group(2)
            lang_badge = (
                f'<span style="color: #6c5ce7; font-size: 10px; '
                f'font-weight: 600;">{lang}</span> '
                if lang else ""
            )
            return (
                f'<div style="background: #0c0c14; border: 1px solid #1a1a2e; '
                f'border-radius: 8px; padding: 10px 12px; margin: 8px 0; '
                f'font-family: \'JetBrains Mono\', \'Cascadia Code\', monospace; '
                f'font-size: 12px;">'
                f'{lang_badge}'
                f'<pre style="margin: 2px 0 0 0; white-space: pre-wrap; '
                f'color: #c0c0e0;">{code}</pre></div>'
            )

        text = re.sub(r"```(\w*)\n(.*?)```", _code_block, text, flags=re.DOTALL)

        # Inline code
        text = re.sub(
            r"`([^`]+)`",
            r'<code style="background: rgba(108,92,231,0.15); padding: 1px 6px; '
            r'border-radius: 4px; font-family: monospace; font-size: 12px; '
            r'color: #b0b0d0;">\1</code>',
            text,
        )

        # Bold & Italic
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)

        # Headers
        text = re.sub(
            r"^### (.+)$",
            r'<div style="margin: 10px 0 4px 0; font-size: 14px; '
            r'font-weight: 700; color: #d0d0e8;">\1</div>',
            text, flags=re.MULTILINE,
        )
        text = re.sub(
            r"^## (.+)$",
            r'<div style="margin: 12px 0 6px 0; font-size: 16px; '
            r'font-weight: 700; color: #e4e4f0;">\1</div>',
            text, flags=re.MULTILINE,
        )
        text = re.sub(
            r"^# (.+)$",
            r'<div style="margin: 14px 0 8px 0; font-size: 18px; '
            r'font-weight: 800; color: #e8e8f4;">\1</div>',
            text, flags=re.MULTILINE,
        )

        # Bullet lists
        text = re.sub(
            r"^- (.+)$",
            r'<div style="padding-left: 14px; margin: 2px 0;">'
            r'<span style="color: #6c5ce7;">•</span> \1</div>',
            text, flags=re.MULTILINE,
        )
        text = re.sub(
            r"^(\d+)\. (.+)$",
            r'<div style="padding-left: 14px; margin: 2px 0;">'
            r'<span style="color: #6c5ce7;">\1.</span> \2</div>',
            text, flags=re.MULTILINE,
        )

        # Links
        text = re.sub(
            r"\[([^\]]+)\]\(([^\)]+)\)",
            r'<a href="\2" style="color: #818cf8; text-decoration: none;">\1</a>',
            text,
        )

        # Tables
        lines = text.split("\n")
        in_table = False
        result = []
        for line in lines:
            if "|" in line and not line.strip().startswith("<"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if all(set(c) <= {"-", " ", ":"} for c in cells):
                    continue
                if not in_table:
                    result.append(
                        '<table style="border-collapse: collapse; margin: 8px 0; '
                        'font-size: 12px; width: 100%;">'
                    )
                    in_table = True
                row = "".join(
                    f'<td style="padding: 5px 10px; border: 1px solid #1e1e2e; '
                    f'background: rgba(108,92,231,0.04);">{c}</td>'
                    for c in cells
                )
                result.append(f"<tr>{row}</tr>")
            else:
                if in_table:
                    result.append("</table>")
                    in_table = False
                result.append(line)
        if in_table:
            result.append("</table>")

        text = "\n".join(result)
        text = text.replace("\n", "<br>")

        return text

    def start_typing_animation(self, speed_ms: int = 8) -> None:
        if self.is_user:
            return
        self._char_index = 0
        self._current_text = ""
        self._typing_timer = QTimer(self)
        self._typing_timer.timeout.connect(self._type_next_char)
        self._typing_timer.start(speed_ms)

    def _type_next_char(self) -> None:
        if self._char_index >= len(self._full_text):
            if self._typing_timer:
                self._typing_timer.stop()
            self._show_action_buttons()
            return
        chunk_size = 3
        end = min(self._char_index + chunk_size, len(self._full_text))
        self._current_text = self._full_text[:end]
        self._char_index = end
        self._content.setText(self._render_markdown(self._current_text))

    def _show_action_buttons(self) -> None:
        if hasattr(self, "_action_widget"):
            self._action_widget.setVisible(True)

    def append_text(self, text: str) -> None:
        self._full_text += text
        self._current_text = self._full_text
        self._content.setText(self._render_markdown(self._current_text))
        self._show_action_buttons()

    def set_text(self, text: str) -> None:
        self._full_text = text
        self._current_text = text
        self._content.setText(self._render_markdown(text))
        self._show_action_buttons()

    def _copy_text(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self._full_text)
        if hasattr(self, "_copy_btn"):
            self._copy_btn.setText("✅ Copied!")
            QTimer.singleShot(1500, lambda: self._copy_btn.setText("📋 Copy"))

    def _animate_entrance(self) -> None:
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self._fade_anim = QPropertyAnimation(effect, b"opacity")
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.start()

    def enterEvent(self, event):
        super().enterEvent(event)

    def leaveEvent(self, event):
        super().leaveEvent(event)


class TypingIndicator(QWidget):
    """Animated 'Analyzing' indicator with pulsing sparkle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dots = 0
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 8, 24, 8)
        lay.setSpacing(8)

        sparkle = QLabel("✦")
        sparkle.setStyleSheet(
            "font-size: 16px; color: #6c5ce7; background: transparent;"
        )
        lay.addWidget(sparkle)

        self._label = QLabel("Analyzing")
        self._label.setObjectName("ThinkingLabel")
        lay.addWidget(self._label)
        lay.addStretch()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(400)

    def _animate(self):
        self._dots = (self._dots + 1) % 4
        self._label.setText(f"Analyzing{'.' * self._dots}")

    def set_status(self, text: str):
        self._label.setText(text)

    def stop(self):
        self._timer.stop()


class ToolCallBadge(QWidget):
    """Badge showing which tool the agent is using."""

    def __init__(self, tool_name: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 2, 24, 2)

        ICONS = {
            "web_search": "🔍", "calculator": "🧮", "weather": "🌤️",
            "wikipedia": "📚", "system_control": "🖥️", "code_runner": "💻",
            "timer_alarm": "⏱️", "reminders": "🔔",
            "translate_convert": "🌐", "notes": "📝",
        }
        icon = ICONS.get(tool_name, "🔧")

        badge = QLabel(f"{icon} Using: {tool_name}")
        badge.setObjectName("ToolBadge")
        lay.addWidget(badge)
        lay.addStretch()

        fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(fx)
        anim = QPropertyAnimation(fx, b"opacity")
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        self._anim = anim
