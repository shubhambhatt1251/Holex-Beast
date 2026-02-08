"""
Left tools panel — premium glassmorphism cards for all 10 AI tools.

Each tool card has a glowing accent dot, hover glow, and click
sends the example command directly to the AI agent for execution.
"""

from __future__ import annotations

from PyQt5.QtCore import (
    QRectF,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QPainter,
)
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# ── Tool Definitions ───────────────────────────────────────────────

TOOL_GROUPS = [
    {
        "name": "AI Intelligence",
        "icon": "🧠",
        "tools": [
            {
                "id": "web_search", "icon": "🔍", "name": "Web Search",
                "desc": "Real-time internet search",
                "example": "Search the web for latest AI news 2026",
                "color": "#3b82f6",
            },
            {
                "id": "calculator", "icon": "🧮", "name": "Calculator",
                "desc": "Math & equations",
                "example": "Calculate 15% of 2500",
                "color": "#f59e0b",
            },
            {
                "id": "wikipedia", "icon": "📚", "name": "Wikipedia",
                "desc": "Encyclopedia lookup",
                "example": "Search Wikipedia for quantum computing",
                "color": "#8b5cf6",
            },
            {
                "id": "weather", "icon": "🌤️", "name": "Weather",
                "desc": "Live forecasts",
                "example": "What's the weather in New York?",
                "color": "#06b6d4",
            },
        ],
    },
    {
        "name": "System Control",
        "icon": "⚡",
        "tools": [
            {
                "id": "system_control", "icon": "🖥️", "name": "System",
                "desc": "Apps, settings, media",
                "example": "Open Chrome browser",
                "color": "#10b981",
            },
            {
                "id": "code_runner", "icon": "💻", "name": "Code Runner",
                "desc": "Execute Python scripts",
                "example": "Run Python: print('Hello World')",
                "color": "#ef4444",
            },
        ],
    },
    {
        "name": "Productivity",
        "icon": "🚀",
        "tools": [
            {
                "id": "timer_alarm", "icon": "⏱️", "name": "Timer",
                "desc": "Timers & alarms",
                "example": "Set a timer for 5 minutes",
                "color": "#f97316",
            },
            {
                "id": "reminders", "icon": "🔔", "name": "Reminders",
                "desc": "Tasks & events",
                "example": "Remind me to call mom at 5pm",
                "color": "#ec4899",
            },
            {
                "id": "translate_convert", "icon": "🌐", "name": "Translate",
                "desc": "38 languages",
                "example": "Translate hello to Spanish",
                "color": "#14b8a6",
            },
            {
                "id": "notes", "icon": "📝", "name": "Notes",
                "desc": "Quick memos & todos",
                "example": "Add a note: Buy groceries tomorrow",
                "color": "#a855f7",
            },
        ],
    },
]


class _GlowDot(QWidget):
    """Tiny animated accent dot next to tool cards."""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(6, 6)
        self._color = QColor(color)
        self._alpha = 0.4
        self._dir = 1
        self._t = QTimer(self)
        self._t.setInterval(60)
        self._t.timeout.connect(self._pulse)
        self._t.start()

    def _pulse(self):
        self._alpha += 0.025 * self._dir
        if self._alpha > 0.92:
            self._dir = -1
        elif self._alpha < 0.3:
            self._dir = 1
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self._color)
        c.setAlphaF(self._alpha)
        p.setPen(Qt.NoPen)
        # glow halo
        gc = QColor(self._color)
        gc.setAlphaF(self._alpha * 0.25)
        p.setBrush(gc)
        p.drawEllipse(QRectF(-1, -1, 8, 8))
        # core dot
        p.setBrush(c)
        p.drawEllipse(QRectF(1, 1, 4, 4))
        p.end()


class ToolCard(QFrame):
    """A single tool card with icon, name, description, and hover glow."""

    clicked = pyqtSignal(str, str)  # (tool_id, example_command)

    def __init__(self, tool_id, icon, name, desc, example, color, parent=None):
        super().__init__(parent)
        self._tool_id = tool_id
        self._example = example
        self._color = color
        self._hovered = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self.setObjectName("ToolCard")
        self.setStyleSheet(
            "#ToolCard { background: transparent; "
            "border: 1px solid transparent; border-radius: 8px; }"
        )
        self._build(icon, name, desc, color)

    def _build(self, icon, name, desc, color):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        self._dot = _GlowDot(color)
        lay.addWidget(self._dot, 0, Qt.AlignVCenter)

        ic = QLabel(icon)
        ic.setFixedSize(24, 24)
        ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet(
            f"background: {color}1a; border-radius: 12px; "
            f"font-size: 12px; border: 1px solid {color}22;"
        )
        lay.addWidget(ic)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        nl = QLabel(name)
        nl.setStyleSheet(
            "color: #c8c8e0; font-size: 11px; font-weight: 600; "
            "background: transparent;"
        )
        col.addWidget(nl)
        dl = QLabel(desc)
        dl.setStyleSheet(
            "color: #4a4b60; font-size: 8px; background: transparent;"
        )
        col.addWidget(dl)
        lay.addLayout(col, 1)

        ar = QLabel("›")
        ar.setStyleSheet(
            f"color: {color}44; font-size: 14px; font-weight: bold; "
            "background: transparent;"
        )
        lay.addWidget(ar)

    def mousePressEvent(self, e):
        self.clicked.emit(self._tool_id, self._example)
        self.setStyleSheet(
            f"#ToolCard {{ background: {self._color}28; "
            f"border: 1px solid {self._color}44; border-radius: 8px; }}"
        )
        QTimer.singleShot(200, self._reset_style)
        super().mousePressEvent(e)

    def _reset_style(self):
        if self._hovered:
            self.setStyleSheet(
                f"#ToolCard {{ background: {self._color}12; "
                f"border: 1px solid {self._color}28; border-radius: 8px; }}"
            )
        else:
            self.setStyleSheet(
                "#ToolCard { background: transparent; "
                "border: 1px solid transparent; border-radius: 8px; }"
            )

    def enterEvent(self, e):
        self._hovered = True
        self.setStyleSheet(
            f"#ToolCard {{ background: {self._color}12; "
            f"border: 1px solid {self._color}28; border-radius: 8px; }}"
        )
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self.setStyleSheet(
            "#ToolCard { background: transparent; "
            "border: 1px solid transparent; border-radius: 8px; }"
        )
        super().leaveEvent(e)


class ToolsPanel(QWidget):
    """Left sidebar with premium tool cards grouped by category."""

    tool_activated = pyqtSignal(str, str)  # (tool_id, example_command)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolsPanel")
        self.setFixedWidth(210)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(48)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 14, 0)
        hl.setSpacing(8)

        logo = QLabel("⚡")
        logo.setStyleSheet("font-size: 16px; background: transparent;")
        hl.addWidget(logo)

        title = QLabel("HOLEX TOOLS")
        title.setStyleSheet(
            "color: #6a6b85; font-size: 9px; font-weight: 800; "
            "letter-spacing: 2.5px; background: transparent;"
        )
        hl.addWidget(title)
        hl.addStretch()

        count = sum(len(g["tools"]) for g in TOOL_GROUPS)
        badge = QLabel(str(count))
        badge.setFixedSize(18, 18)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            "background: rgba(108,92,231,0.15); color: #6c5ce7; "
            "border-radius: 9px; font-size: 9px; font-weight: 700;"
        )
        hl.addWidget(badge)
        layout.addWidget(hdr)

        # Sep
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.03);")
        layout.addWidget(sep)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(6, 6, 6, 6)
        cl.setSpacing(1)

        for group in TOOL_GROUPS:
            gh = QLabel(f"  {group['icon']}  {group['name']}")
            gh.setStyleSheet(
                "color: #525370; font-size: 8px; font-weight: 700; "
                "letter-spacing: 1.2px; padding: 10px 0 3px 2px; "
                "background: transparent; text-transform: uppercase;"
            )
            cl.addWidget(gh)

            for tool in group["tools"]:
                card = ToolCard(
                    tool["id"], tool["icon"], tool["name"],
                    tool["desc"], tool["example"], tool["color"],
                )
                card.clicked.connect(self.tool_activated.emit)
                cl.addWidget(card)

        cl.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # Bottom shortcuts
        bottom = QFrame()
        bottom.setObjectName("ToolsPanelBottom")
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(12, 6, 12, 8)
        bl.setSpacing(3)

        for key, lbl in [("Ctrl+M", "🎤 Voice"), ("Ctrl+N", "💬 New Chat"),
                         ("Ctrl+/", "📌 Toggle")]:
            row = QHBoxLayout()
            row.setSpacing(6)
            kl = QLabel(key)
            kl.setStyleSheet(
                "color: #3a3b50; font-size: 8px; font-weight: 600; "
                "background: rgba(255,255,255,0.03); border-radius: 3px; "
                "padding: 1px 5px;"
            )
            kl.setFixedWidth(48)
            kl.setAlignment(Qt.AlignCenter)
            row.addWidget(kl)
            ll = QLabel(lbl)
            ll.setStyleSheet(
                "color: #3a3b50; font-size: 8px; background: transparent;"
            )
            row.addWidget(ll)
            row.addStretch()
            bl.addLayout(row)

        layout.addWidget(bottom)
