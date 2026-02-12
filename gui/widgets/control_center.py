"""
Control Center Panel.

Contains:
1. `EnergySphere`: The custom 3D audio visualizer (PyQt painting).
2. `QuickActions`: Grid of buttons for fast system commands.
3. Microphone logic for the voice engine.
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


# ── Energy Sphere (Neural Nebula Engine) ──────────────────────────────

class EnergySphere(QWidget):
    """
    Volumetric Nebula Visualization.
    Renders soft gradient clouds and stars. No hard edges/lines.
    """

    # Modes
    MODE_IDLE = 0
    MODE_LISTENING = 1
    MODE_PROCESSING = 2
    MODE_AI_SPEAKING = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._mode = self.MODE_IDLE
        self._audio_level = 0.0
        self._target_level = 0.0
        self._phase = 0.0

        # Physics
        self._rotation_speed = 0.5
        self._pulse_speed = 0.05

        # Nebula Cloud Layers (Randomized but consistent)
        self._nebula_layers = []
        for i in range(5):
            self._nebula_layers.append({
                "angle": i * (360 / 5),
                "dist": random.uniform(0.2, 0.4),
                "size": random.uniform(0.6, 0.9),
                "speed": random.uniform(0.5, 1.5) * (1 if i % 2 == 0 else -1)
            })

        # Particles (Starfield)
        self._particles = []
        for _ in range(150):
            self._particles.append({
                "x": random.uniform(-1, 1),
                "y": random.uniform(-1, 1),
                "z": random.uniform(0.1, 1.0), # Depth speed
                "size": random.uniform(0.5, 2.0),
                "alpha": random.randint(100, 255),
            })

        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_mode(self, mode: int):
        self._mode = mode
        self.update()

    def set_audio_level(self, level: float):
        self._target_level = max(0.0, min(1.0, level))

    def _tick(self):
        # Smooth audio
        diff = self._target_level - self._audio_level
        self._audio_level += diff * 0.2

        # Animation Phase
        base_speed = 0.5
        if self._mode == self.MODE_LISTENING:
            base_speed = 1.0
        elif self._mode == self.MODE_PROCESSING:
            base_speed = 4.0
        elif self._mode == self.MODE_AI_SPEAKING:
            base_speed = 1.5

        self._phase += base_speed + (self._audio_level * 2.0)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        # Determine Palette based on Mode
        # Core Color, Outer Color
        if self._mode == self.MODE_PROCESSING:
            c_core = QColor(255, 255, 220)   # White/Gold
            c_outer = QColor(255, 180, 50)   # Orange
            pulse_rate = 10.0
        elif self._mode == self.MODE_AI_SPEAKING:
            c_core = QColor(255, 100, 255)   # Pink
            c_outer = QColor(100, 50, 255)   # Purple
            pulse_rate = 5.0
        elif self._mode == self.MODE_LISTENING:
            c_core = QColor(100, 255, 255)   # Cyan
            c_outer = QColor(0, 100, 255)    # Blue
            pulse_rate = 1.0
        else: # IDLE
            c_core = QColor(100, 150, 255)
            c_outer = QColor(50, 50, 150)
            pulse_rate = 0.5

        # Audio Pulse Logic
        audio_boost = self._audio_level * 0.5
        # Breathing sine wave
        breath = (math.sin(self._phase * 0.05 * pulse_rate) + 1.0) * 0.5

        # 1. Background Glow (Transparent Vignette)
        # Soft ambient glow behind everything
        glow_r = min(w, h) * 0.6
        bg_grad = QRadialGradient(cx, cy, glow_r)
        c_bg = QColor(c_outer)
        c_bg.setAlpha(40)
        bg_grad.setColorAt(0.0, c_bg)
        bg_grad.setColorAt(1.0, Qt.transparent)
        painter.setBrush(QBrush(bg_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r*2, glow_r*2))

        # 2. Nebula Clouds
        painter.save()
        painter.translate(cx, cy)

        # Rotate whole system slowly
        painter.rotate(self._phase * 0.2)

        cloud_base_r = min(w, h) * 0.35

        for layer in self._nebula_layers:
            painter.save()
            painter.rotate(layer["angle"] + self._phase * layer["speed"] * 0.1)

            # Distance oscilates with breath
            d = cloud_base_r * layer["dist"] * (1.0 + breath * 0.2 + audio_boost)

            # Draw gradient blob
            sz = cloud_base_r * layer["size"]

            grad = QRadialGradient(0, d, sz)
            c1 = QColor(c_outer)
            c1.setAlpha(60)
            c2 = QColor(c_outer)
            c2.setAlpha(0)

            grad.setColorAt(0.0, c1)
            grad.setColorAt(1.0, c2)

            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QRectF(-sz, d-sz, sz*2, sz*2))

            painter.restore()

        painter.restore()

        # 3. Core (The Star)
        core_r = min(w, h) * 0.15 * (1.0 + audio_boost * 0.5)
        core_grad = QRadialGradient(cx, cy, core_r)

        c_c1 = QColor(c_core)
        c_c1.setAlpha(255)
        c_c2 = QColor(c_outer)
        c_c2.setAlpha(100)

        core_grad.setColorAt(0.0, c_c1)
        core_grad.setColorAt(0.5, c_c2)
        core_grad.setColorAt(1.0, Qt.transparent)

        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r*2, core_r*2))

        # 4. Particles (Star Dust)
        painter.save()
        painter.translate(cx, cy)

        # Warp Effect: Particles stretch when speaking
        is_warping = self._mode in [self.MODE_AI_SPEAKING, self.MODE_PROCESSING]

        for p in self._particles:
            # 3D projection simulation
            # Move Z towards camera
            p["z"] -= 0.01 * (1.0 + self._audio_level * 5.0)
            if p["z"] <= 0.01:
                p["z"] = 1.0 # Reset
                p["x"] = random.uniform(-1, 1)
                p["y"] = random.uniform(-1, 1)

            # Project
            factor = 200.0 / p["z"]
            x = p["x"] * factor
            y = p["y"] * factor

            # Check bounds
            if x*x + y*y > (w*h):
                continue

            sz = p["size"] / p["z"]
            alpha = int(p["alpha"] * (1.0 - p["z"]))

            c = QColor(255, 255, 255, alpha)
            painter.setBrush(c)
            painter.setPen(Qt.NoPen)

            if is_warping and self._audio_level > 0.1:
                # Streak
                painter.setPen(QPen(c, sz))
                lx = x * 1.1
                ly = y * 1.1
                painter.drawLine(QPointF(x, y), QPointF(lx, ly))
            else:
                painter.drawEllipse(QPointF(x, y), sz, sz)

        painter.restore()

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

        # Header (Subtle)
        hdr = QLabel("HOLEX VOICE INTELLIGENCE")
        hdr.setAlignment(Qt.AlignCenter)
        hdr.setStyleSheet(
            "color: rgba(255,255,255,0.3); font-size: 10px; font-weight: 700; "
            "letter-spacing: 2px; margin-top: 10px;"
        )
        lay.addWidget(hdr)

        # Sphere Area (Center Stage)
        lay.addStretch(1)
        sc = QHBoxLayout()
        sc.setAlignment(Qt.AlignCenter)
        self._sphere = EnergySphere()
        self._sphere.setFixedSize(320, 320) # MASSIVE sphere
        sc.addWidget(self._sphere)
        lay.addLayout(sc)

        # Transcript Container (Below Sphere)
        trans_lay = QVBoxLayout()
        trans_lay.setSpacing(8)
        trans_lay.setAlignment(Qt.AlignCenter)

        # 1. User Input (The "Question")
        self._user_transcript = QLabel("")
        self._user_transcript.setWordWrap(True)
        self._user_transcript.setAlignment(Qt.AlignCenter)
        self._user_transcript.setMinimumHeight(60)
        self._user_transcript.setStyleSheet(
            "color: #ffffff; font-size: 26px; font-weight: 600; "
            "line-height: 1.3; font-family: 'Segoe UI', sans-serif; "
            "background: transparent; padding: 0px 20px;"
        )
        trans_lay.addWidget(self._user_transcript)

        # 2. AI Status (The "Answer")
        self._ai_status = QLabel("")
        self._ai_status.setAlignment(Qt.AlignCenter)
        self._ai_status.setWordWrap(True)
        self._ai_status.setStyleSheet(
            "color: #a29bfe; font-size: 16px; font-weight: 500; "
            "font-style: italic; background: transparent; letter-spacing: 0.5px;"
        )
        trans_lay.addWidget(self._ai_status)

        lay.addLayout(trans_lay)
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
        # MODE LISTENING (Cyan)
        self._sphere.set_mode(EnergySphere.MODE_LISTENING)
        self._user_transcript.setText("Listening...")
        self._ai_status.setText("")
        self._partial_text = ""
        self._final_text = ""
        self._status.setText("Listening… speak now")

    def deactivate_voice(self):
        self._is_listening = False
        self._mic_btn.setChecked(False)
        # MODE IDLE
        self._sphere.set_mode(EnergySphere.MODE_IDLE)
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

    def set_ai_text(self, text: str):
        """Display AI response in the status area and switch visual mode."""
        self._ai_status.setText(text)
        self._ai_status.setStyleSheet(
            "color: #a29bfe; font-size: 18px; font-weight: 500; "
            "line-height: 1.4; font-style: normal; background: transparent; "
            "padding: 10px 20px;"
        )
        # MODE AI SPEAKING (Purple)
        self._sphere.set_mode(EnergySphere.MODE_AI_SPEAKING)

    def set_status(self, text: str):
        self._status.setText(text)

    @property
    def is_listening(self) -> bool:
        return self._is_listening

    # ── Private ────────────────────────────────────────────────────

    def _update_transcript(self):
        # Update User Text
        display = ""
        if self._final_text:
            display = self._final_text
        if self._partial_text:
            if display:
                display += " "
            display += f"{self._partial_text}..."

        self._user_transcript.setText(display if display else (
            "Listening..." if self._is_listening else ""
        ))

        # Style user text based on state
        if not display and self._is_listening:
             self._user_transcript.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 22px;")
        else:
             self._user_transcript.setStyleSheet("color: #ffffff; font-size: 22px;")

    def _on_mic_toggle(self):
        self._is_listening = self._mic_btn.isChecked()
        if self._is_listening:
            self.activate_voice()
            self.voice_toggled.emit(True)
        else:
            self.deactivate_voice()
            if self._final_text.strip():
                self.text_submitted.emit(self._final_text.strip())
            self.voice_toggled.emit(False)

    def _on_silence_timeout(self):
        if self._final_text.strip() and self._is_listening:
            self.text_submitted.emit(self._final_text.strip())
            self._status.setText("Sent!")
            self._ai_status.setText("Processing command...")

            # MODE PROCESSING (Gold)
            self._sphere.set_mode(EnergySphere.MODE_PROCESSING)

            self._final_text = ""
            self._partial_text = ""
            self._user_transcript.setText("")

            # We don't reset to listening immediately here, the app logic might.
            # But the timer below does reset it.

            QTimer.singleShot(1500, lambda: (
                self.activate_voice() # Reset to listening state
            ) if self._is_listening else None)
