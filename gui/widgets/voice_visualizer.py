"""Real-time audio waveform visualizer with listening/speaking/idle states."""

from __future__ import annotations

import random
from typing import Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QLinearGradient, QPainter
from PyQt5.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


class WaveformBars(QWidget):
    """Animated vertical bars that react to audio level."""

    NUM_BARS = 32

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setMaximumHeight(100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._bar_heights = [0.0] * self.NUM_BARS
        self._target_heights = [0.0] * self.NUM_BARS
        self._audio_level = 0.0
        self._active = False

        # Smoothing timer
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 fps
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._active = True
        self._timer.start()

    def stop(self) -> None:
        self._active = False
        self._target_heights = [0.0] * self.NUM_BARS
        # Let timer run to animate bars down
        QTimer.singleShot(600, self._timer.stop)

    def set_audio_level(self, level: float) -> None:
        """Set normalized audio level 0.0-1.0."""
        self._audio_level = max(0.0, min(1.0, level))

    def _tick(self) -> None:
        """Update target heights & lerp current toward target."""
        if self._active:
            for i in range(self.NUM_BARS):
                center_factor = 1.0 - abs(i - self.NUM_BARS / 2) / (self.NUM_BARS / 2)
                noise = random.uniform(0.3, 1.0)
                self._target_heights[i] = (
                    self._audio_level * center_factor * noise * 0.9 + 0.05
                )
        else:
            self._target_heights = [0.0] * self.NUM_BARS

        # Smooth lerp
        for i in range(self.NUM_BARS):
            diff = self._target_heights[i] - self._bar_heights[i]
            self._bar_heights[i] += diff * 0.25

        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        bar_w = max(3, (w - (self.NUM_BARS - 1) * 2) / self.NUM_BARS)
        gap = 2
        total_w = self.NUM_BARS * bar_w + (self.NUM_BARS - 1) * gap
        offset_x = (w - total_w) / 2

        for i in range(self.NUM_BARS):
            bar_h = max(3, self._bar_heights[i] * h * 0.85)
            x = offset_x + i * (bar_w + gap)
            y = (h - bar_h) / 2

            # Gradient per bar
            gradient = QLinearGradient(x, y, x, y + bar_h)
            i / max(1, self.NUM_BARS - 1)
            if self._active:
                c1 = QColor("#6c5ce7")
                c2 = QColor("#a855f7")
                c1.setAlpha(int(180 + 75 * self._bar_heights[i]))
                c2.setAlpha(int(180 + 75 * self._bar_heights[i]))
            else:
                c1 = QColor("#3a3a50")
                c2 = QColor("#3a3a50")
                c1.setAlpha(60)
                c2.setAlpha(60)

            gradient.setColorAt(0, c1)
            gradient.setColorAt(1, c2)

            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(int(x), int(y), int(bar_w), int(bar_h), 2, 2)

        painter.end()


class VoiceVisualizer(QWidget):
    """
    Voice visualization panel combining:
    - WaveformBars (audio bars)
    - Status label (Listening / Speaking / Idle)
    - Pulse ring indicator
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("VoiceVisualizer")
        self._state = "idle"
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Waveform
        self._waveform = WaveformBars()
        layout.addWidget(self._waveform)

        # Status label
        self._status = QLabel("🎤  Idle")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet(
            "color: #6c6d80; font-size: 11px; font-weight: bold; "
            "background: transparent; letter-spacing: 0.5px;"
        )
        layout.addWidget(self._status)

    def set_state(self, state: str) -> None:
        """Set voice state: 'idle', 'listening', 'speaking', 'processing'."""
        self._state = state
        states_config = {
            "idle": ("🎤  Idle", "#6c6d80", False),
            "listening": ("🎙️  Listening...", "#6c5ce7", True),
            "speaking": ("🔊  Speaking...", "#22c55e", True),
            "processing": ("⏳  Processing...", "#f97316", False),
        }
        label, color, active = states_config.get(state, states_config["idle"])
        self._status.setText(label)
        self._status.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold; "
            f"background: transparent; letter-spacing: 0.5px;"
        )
        if active:
            self._waveform.start()
        else:
            self._waveform.stop()

    def set_audio_level(self, level: float) -> None:
        """Forward audio level to waveform."""
        self._waveform.set_audio_level(level)

    def show_visualizer(self) -> None:
        self.setVisible(True)
        self.set_state("listening")

    def hide_visualizer(self) -> None:
        self.set_state("idle")
        self.setVisible(False)
