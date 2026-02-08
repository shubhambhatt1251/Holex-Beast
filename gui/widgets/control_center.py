"""
Center control panel — premium voice sphere, mic button, live transcription,
and desktop quick-action grid.

The hero section: an animated 3D energy sphere reacts to voice audio,
a prominent mic button toggles STT, and quick desktop actions are a grid
of glowing buttons that send commands directly to the AI agent.
"""

from __future__ import annotations

import math
import random

from PyQt5.QtCore import (
    QPointF,
    QRectF,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# ── Quick Actions ───────────────────────────────────────────────────

QUICK_ACTIONS = [
    {"icon": "📸", "label": "Screenshot", "command": "Take a screenshot"},
    {"icon": "🌐", "label": "Browser",    "command": "Open Chrome browser"},
    {"icon": "⚙️", "label": "Settings",   "command": "Open Windows settings"},
    {"icon": "📁", "label": "Files",      "command": "Open file explorer"},
    {"icon": "🎵", "label": "Music",      "command": "Open Spotify"},
    {"icon": "🔒", "label": "Lock",       "command": "Lock the screen"},
    {"icon": "🌙", "label": "Night",      "command": "Turn on night light"},
    {"icon": "💻", "label": "Terminal",   "command": "Open terminal"},
    {"icon": "🔊", "label": "Volume",     "command": "Set volume to 50 percent"},
]


# ── Energy Sphere (3D animated QPainter) ────────────────────────────

class EnergySphere(QWidget):
    """
    Glowing animated sphere with orbiting wave arcs, particles,
    and a pulsing inner core. Reacts to microphone audio level.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._audio_level = 0.0
        self._target_level = 0.0
        self._phase = 0.0
        self._active = False
        self._idle_pulse = 0.0

        # Wave configs
        self._waves = [
            {"freq": 1.8, "amp": 0.35, "speed": 1.2,
             "color": QColor(100, 140, 255, 140)},
            {"freq": 2.4, "amp": 0.28, "speed": 0.9,
             "color": QColor(140, 100, 255, 110)},
            {"freq": 3.0, "amp": 0.22, "speed": 1.5,
             "color": QColor(60, 180, 255, 90)},
        ]

        # Particles
        self._particles = []
        for _ in range(35):
            self._particles.append({
                "angle": random.uniform(0, math.tau),
                "radius": random.uniform(0.45, 0.95),
                "speed": random.uniform(0.3, 1.2),
                "size": random.uniform(1.0, 3.5),
                "alpha": random.randint(25, 130),
            })

        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_active(self, active: bool):
        self._active = active
        if not active:
            self._target_level = 0.0

    def set_audio_level(self, level: float):
        self._target_level = max(0.0, min(1.0, level))

    def _tick(self):
        diff = self._target_level - self._audio_level
        self._audio_level += diff * 0.15
        speed = 0.03 if self._active else 0.012
        self._phase += speed + self._audio_level * 0.04
        self._idle_pulse = math.sin(self._phase * 0.8) * 0.5 + 0.5
        for p in self._particles:
            p["angle"] += p["speed"] * 0.02 * (1.0 + self._audio_level * 2.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        base_r = min(w, h) * 0.28

        pulse = (self._idle_pulse * 0.06 if not self._active
                 else self._audio_level * 0.20)
        sr = base_r * (1.0 + pulse)

        # Outer atmospheric glow
        gr = sr * 3.2
        glow = QRadialGradient(cx, cy, gr)
        ga = int(25 + self._audio_level * 70) if self._active else 14
        glow.setColorAt(0.0, QColor(80, 120, 255, ga))
        glow.setColorAt(0.25, QColor(100, 60, 220, int(ga * 0.6)))
        glow.setColorAt(0.5, QColor(60, 80, 200, int(ga * 0.3)))
        glow.setColorAt(1.0, QColor(20, 30, 80, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QRectF(cx - gr, cy - gr, gr * 2, gr * 2))

        # Core sphere with 3D gradient
        core = QRadialGradient(cx - sr * 0.22, cy - sr * 0.28, sr * 1.3)
        ca = int(170 + self._audio_level * 85) if self._active else 115
        core.setColorAt(0.0, QColor(110, 150, 255, ca))
        core.setColorAt(0.25, QColor(80, 105, 230, int(ca * 0.8)))
        core.setColorAt(0.5, QColor(55, 60, 180, int(ca * 0.5)))
        core.setColorAt(0.75, QColor(35, 40, 140, int(ca * 0.25)))
        core.setColorAt(1.0, QColor(15, 20, 60, 0))
        painter.setBrush(QBrush(core))
        painter.drawEllipse(QRectF(cx - sr, cy - sr, sr * 2, sr * 2))

        # Inner specular highlight — 3D glass effect
        hl = QRadialGradient(cx - sr * 0.18, cy - sr * 0.22, sr * 0.55)
        ha = int(100 + self._audio_level * 80) if self._active else 50
        hl.setColorAt(0.0, QColor(200, 220, 255, ha))
        hl.setColorAt(0.5, QColor(140, 170, 255, int(ha * 0.4)))
        hl.setColorAt(1.0, QColor(100, 140, 255, 0))
        painter.setBrush(QBrush(hl))
        painter.drawEllipse(QRectF(cx - sr * 0.55, cy - sr * 0.55,
                                   sr * 1.1, sr * 1.1))

        # Wave rings (only when active or transitioning)
        if self._active or self._audio_level > 0.02:
            for wi, wave in enumerate(self._waves):
                path = QPainterPath()
                pts = 80
                wr = sr * (1.12 + wi * 0.14)
                amp = wave["amp"] * sr * (0.3 + self._audio_level * 0.7)
                for i in range(pts + 1):
                    t = i / pts
                    angle = t * math.pi * 2
                    offset = math.sin(
                        angle * wave["freq"] + self._phase * wave["speed"]
                    ) * amp
                    fade = math.sin(t * math.pi) ** 0.6
                    offset *= fade
                    r = wr + offset
                    px = cx + math.cos(angle) * r
                    py = cy + math.sin(angle) * r
                    if i == 0:
                        path.moveTo(px, py)
                    else:
                        path.lineTo(px, py)
                color = QColor(wave["color"])
                alpha = int(color.alpha() * (0.3 + self._audio_level * 0.7))
                color.setAlpha(min(255, alpha))
                pen = QPen(color, 1.8)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(path)

        # Orbiting particles
        for p in self._particles:
            pr = sr * p["radius"] * (1.0 + self._audio_level * 0.4)
            px = cx + math.cos(p["angle"]) * pr
            py = cy + math.sin(p["angle"]) * pr
            alpha = (int(p["alpha"] * (0.5 + self._audio_level * 0.5))
                     if self._active else int(p["alpha"] * 0.2))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(120, 160, 255, alpha))
            size = p["size"] * (1.0 + self._audio_level * 0.5)
            painter.drawEllipse(QPointF(px, py), size, size)

        # Active ring pulse
        if self._active:
            ring_alpha = int(40 + self._audio_level * 60)
            ring_r = sr * (1.35 + self._idle_pulse * 0.08)
            painter.setPen(QPen(QColor(100, 140, 255, ring_alpha), 1.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QRectF(cx - ring_r, cy - ring_r,
                                       ring_r * 2, ring_r * 2))

        painter.end()


# ── Quick Action Button ────────────────────────────────────────────

class QuickActionButton(QFrame):
    """Small glass icon button for a desktop quick action."""

    clicked = pyqtSignal(str)

    def __init__(self, icon, label, command, parent=None):
        super().__init__(parent)
        self._command = command
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(70, 60)
        self.setObjectName("QuickAction")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 6, 4, 4)
        lay.setSpacing(2)
        lay.setAlignment(Qt.AlignCenter)

        ic = QLabel(icon)
        ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet("font-size: 18px; background: transparent;")
        lay.addWidget(ic)

        tl = QLabel(label)
        tl.setAlignment(Qt.AlignCenter)
        tl.setStyleSheet(
            "color: #6a6b85; font-size: 8px; font-weight: 500; "
            "background: transparent;"
        )
        lay.addWidget(tl)

    def mousePressEvent(self, event):
        self.clicked.emit(self._command)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setStyleSheet(
            "#QuickAction { background: rgba(108,92,231,0.12); "
            "border: 1px solid rgba(108,92,231,0.30); border-radius: 12px; }"
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(
            "#QuickAction { background: rgba(255,255,255,0.02); "
            "border: 1px solid rgba(255,255,255,0.04); border-radius: 12px; }"
        )
        super().leaveEvent(event)


# ── Control Center Widget ──────────────────────────────────────────

class ControlCenter(QWidget):
    """
    Center panel — the hero section.

    ┌────────────────────────────────────┐
    │      [Voice Transcript]            │
    │                                    │
    │     ┌────────────────────┐         │
    │     │  Energy Sphere     │         │
    │     │   (3D animated)    │         │
    │     └────────────────────┘         │
    │                                    │
    │      "Listening…" status           │
    │       [🎤 Mic Button]              │
    │                                    │
    │   ── Desktop Quick Actions ──      │
    │   [📸] [🌐] [⚙️] [📁] [🎵]        │
    │   [🔒] [🌙] [💻] [🔊]             │
    └────────────────────────────────────┘
    """

    voice_toggled = pyqtSignal(bool)
    command_submitted = pyqtSignal(str)
    text_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ControlCenter")
        self._is_listening = False
        self._partial_text = ""
        self._final_text = ""

        # Auto-submit on silence
        self._silence_timer = QTimer(self)
        self._silence_timer.setSingleShot(True)
        self._silence_timer.setInterval(2500)
        self._silence_timer.timeout.connect(self._on_silence_timeout)

        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 12, 20, 14)
        lay.setSpacing(0)

        # Transcript
        self._transcript = QLabel("")
        self._transcript.setWordWrap(True)
        self._transcript.setMinimumHeight(44)
        self._transcript.setMaximumHeight(72)
        self._transcript.setAlignment(Qt.AlignCenter)
        self._transcript.setStyleSheet(
            "color: rgba(220, 225, 250, 0.95); "
            "font-size: 15px; font-weight: 400; "
            "line-height: 1.5; background: transparent; "
            "padding: 6px 16px;"
        )
        lay.addWidget(self._transcript)

        # Sphere
        lay.addStretch(1)
        sc = QHBoxLayout()
        sc.setAlignment(Qt.AlignCenter)
        self._sphere = EnergySphere()
        self._sphere.setFixedSize(240, 240)
        sc.addWidget(self._sphere)
        lay.addLayout(sc)
        lay.addStretch(1)

        # Status
        self._status = QLabel('Say "Hey Holex" or tap the mic')
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet(
            "color: rgba(130, 140, 180, 0.55); font-size: 11px; "
            "background: transparent; letter-spacing: 0.3px;"
        )
        lay.addWidget(self._status)
        lay.addSpacing(8)

        # Mic Button
        mic_row = QHBoxLayout()
        mic_row.setAlignment(Qt.AlignCenter)

        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setFixedSize(56, 56)
        self._mic_btn.setCursor(Qt.PointingHandCursor)
        self._mic_btn.setCheckable(True)
        self._mic_btn.setObjectName("BigMicBtn")
        self._mic_btn.setStyleSheet("""
            #BigMicBtn {
                background: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.4,
                    stop:0 rgba(255,255,255,0.95),
                    stop:0.8 rgba(220,230,255,0.9),
                    stop:1 rgba(180,200,240,0.85)
                );
                border: 2px solid rgba(140,170,255,0.3);
                border-radius: 28px;
                font-size: 22px;
            }
            #BigMicBtn:checked {
                background: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.4,
                    stop:0 rgba(100,140,255,0.95),
                    stop:0.8 rgba(80,110,230,0.9),
                    stop:1 rgba(60,80,200,0.85)
                );
                border-color: rgba(100,160,255,0.6);
            }
            #BigMicBtn:hover { border-color: rgba(140,180,255,0.5); }
        """)
        shadow = QGraphicsDropShadowEffect(self._mic_btn)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(80, 120, 255, 80))
        shadow.setOffset(0, 0)
        self._mic_btn.setGraphicsEffect(shadow)
        self._mic_btn.clicked.connect(self._on_mic_toggle)
        mic_row.addWidget(self._mic_btn)

        lay.addLayout(mic_row)
        lay.addSpacing(14)

        # Quick Actions
        ah = QLabel("── Desktop Quick Actions ──")
        ah.setAlignment(Qt.AlignCenter)
        ah.setStyleSheet(
            "color: #353548; font-size: 9px; font-weight: 600; "
            "letter-spacing: 1.5px; background: transparent; "
            "padding-bottom: 6px;"
        )
        lay.addWidget(ah)

        grid = QGridLayout()
        grid.setSpacing(5)
        grid.setAlignment(Qt.AlignCenter)

        for idx, action in enumerate(QUICK_ACTIONS):
            btn = QuickActionButton(
                action["icon"], action["label"], action["command"],
            )
            btn.clicked.connect(self.command_submitted.emit)
            grid.addWidget(btn, idx // 5, idx % 5)

        lay.addLayout(grid)

    # ── Public API ─────────────────────────────────────────────────

    def activate_voice(self):
        self._is_listening = True
        self._mic_btn.setChecked(True)
        self._sphere.set_active(True)
        self._transcript.setText("")
        self._partial_text = ""
        self._final_text = ""
        self._status.setText("Listening… speak now")

    def deactivate_voice(self):
        self._is_listening = False
        self._mic_btn.setChecked(False)
        self._sphere.set_active(False)
        self._silence_timer.stop()
        self._status.setText('Say "Hey Holex" or tap the mic')

    def set_audio_level(self, level: float):
        self._sphere.set_audio_level(level)

    def set_partial_text(self, text: str):
        self._partial_text = text
        self._update_transcript()
        if self._is_listening and text.strip():
            self._silence_timer.start()

    def set_final_text(self, text: str):
        if text.strip():
            self._final_text = text.strip()
            self._partial_text = ""
            self._update_transcript()
            if self._is_listening:
                self._silence_timer.start()

    def set_status(self, text: str):
        self._status.setText(text)

    @property
    def is_listening(self) -> bool:
        return self._is_listening

    # ── Private ────────────────────────────────────────────────────

    def _update_transcript(self):
        display = ""
        if self._final_text:
            display = self._final_text
        if self._partial_text:
            if display:
                display += " "
            display += (
                f"<b>{self._partial_text}</b>"
                "<span style='color: rgba(100,140,255,0.8);'>…</span>"
            )
        if not display and self._is_listening:
            display = (
                "<span style='color: rgba(140,150,190,0.4);'>"
                "Listening…</span>"
            )
        self._transcript.setText(display)

    def _on_mic_toggle(self):
        self._is_listening = self._mic_btn.isChecked()
        if self._is_listening:
            self._sphere.set_active(True)
            self._status.setText("Listening… speak now")
            self._transcript.setText("")
            self._partial_text = ""
            self._final_text = ""
            self.voice_toggled.emit(True)
        else:
            self._sphere.set_active(False)
            self._status.setText('Say "Hey Holex" or tap the mic')
            if self._final_text.strip():
                self.text_submitted.emit(self._final_text.strip())
            self.voice_toggled.emit(False)

    def _on_silence_timeout(self):
        if self._final_text.strip() and self._is_listening:
            self.text_submitted.emit(self._final_text.strip())
            self._status.setText("Sent! Listening…")
            self._final_text = ""
            self._partial_text = ""
            self._update_transcript()
            QTimer.singleShot(1500, lambda: (
                self._status.setText("Listening… speak now")
                if self._is_listening else None
            ))
