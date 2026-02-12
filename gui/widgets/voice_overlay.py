"""
Full-screen voice assistant overlay with animated sphere video,
live transcription, and a floating mic button.

The sphere animation plays from a local mp4 video file
(ai animtion/ folder). Falls back to a QPainter-rendered
glowing orb if the video file is missing or PyQt5 multimedia
isn't available.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import (
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QRadialGradient,
)
from PyQt5.QtWidgets import (
    QComboBox,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# Video player imports (optional — falls back to QPainter sphere)
_HAS_MULTIMEDIA = False
try:
    from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QMediaPlaylist
    from PyQt5.QtMultimediaWidgets import QVideoWidget
    _HAS_MULTIMEDIA = True
except ImportError:
    pass

# Path to the sphere animation video
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SPHERE_VIDEO = _PROJECT_ROOT / "ai animtion" / "original-116c6ad11b9426f769574dd5e81f2415.mp4"


# Language display names
LANGUAGE_NAMES = {
    # International
    "en": "English",
    "cn": "Chinese (中文)",
    "ru": "Russian (Русский)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "es": "Spanish (Español)",
    "pt": "Portuguese (Português)",
    "tr": "Turkish (Türkçe)",
    "ja": "Japanese (日本語)",
    "ko": "Korean (한국어)",
    "ar": "Arabic (العربية)",
    "it": "Italian (Italiano)",
    "nl": "Dutch (Nederlands)",
    "uk": "Ukrainian (Українська)",
    "fa": "Persian (فارسی)",
    "vi": "Vietnamese (Tiếng Việt)",
    # Indian languages
    "en-in": "English (India)",
    "hi": "Hindi (हिन्दी)",
    "gu": "Gujarati (ગુજરાતી)",
    "te": "Telugu (తెలుగు)",
    "ta": "Tamil (தமிழ்)",
    "bn": "Bengali (বাংলা)",
    "mr": "Marathi (मराठी)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "ml": "Malayalam (മലയാളം)",
    "ur": "Urdu (اردو)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
}


# ---------------------------------------------------------------------------
# Animated Energy Sphere — the glowing orb that pulses to audio
# ---------------------------------------------------------------------------

class EnergySphere(QWidget):
    """
    A glowing animated sphere with orbiting wave lines.
    Reacts to audio input — louder audio = bigger pulse + faster waves.
    Uses QPainter with radial gradients and sine-wave paths.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._audio_level = 0.0
        self._target_level = 0.0
        self._phase = 0.0
        self._active = False
        self._idle_pulse = 0.0

        # Wave data — 3 layered wave lines with different frequencies
        self._waves = [
            {"freq": 1.8, "amp": 0.35, "speed": 1.2, "color": QColor(100, 140, 255, 140)},
            {"freq": 2.4, "amp": 0.28, "speed": 0.9, "color": QColor(140, 100, 255, 110)},
            {"freq": 3.0, "amp": 0.22, "speed": 1.5, "color": QColor(60, 180, 255, 90)},
        ]

        # Particles — small floating dots around the sphere
        self._particles = []
        for _ in range(24):
            self._particles.append({
                "angle": random.uniform(0, math.tau),
                "radius": random.uniform(0.55, 0.85),
                "speed": random.uniform(0.3, 0.9),
                "size": random.uniform(1.5, 3.5),
                "alpha": random.randint(40, 120),
            })

        # Animation timer — 60fps for smooth visuals
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_active(self, active: bool) -> None:
        self._active = active
        if not active:
            self._target_level = 0.0

    def set_audio_level(self, level: float) -> None:
        self._target_level = max(0.0, min(1.0, level))

    def _tick(self) -> None:
        # Smooth audio level transition
        diff = self._target_level - self._audio_level
        self._audio_level += diff * 0.2

        # Phase advance
        speed = 0.04 if self._active else 0.015
        self._phase += speed + self._audio_level * 0.08

        # Idle breathing
        self._idle_pulse = math.sin(self._phase * 0.5) * 0.5 + 0.5

        self.update()

    def paintEvent(self, event) -> None:
        is_active = self._active
        level = self._audio_level

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx, cy = w / 2, h / 2

        # Base radius
        base_r = min(w, h) * 0.25
        pulse_scale = 1.0 + (level * 0.3) + (self._idle_pulse * 0.05)
        r = base_r * pulse_scale

        # --- 1. Outer Glow (Soft ambience) ---
        glow_r = r * 3.5
        glow = QRadialGradient(cx, cy, glow_r)
        alpha = int(40 + level * 60) if is_active else 20
        glow.setColorAt(0.0, QColor(60, 100, 255, alpha))
        glow.setColorAt(0.5, QColor(40, 60, 200, int(alpha * 0.4)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # --- 2. 3D Particles Ring (Back) ---
        # We simulate 3D by drawing particles sorted by Z depth
        # For simplicity in this loop, we just draw "back" particles first

        # Orbital rings
        self._draw_rings(painter, cx, cy, r, front=False)

        # --- 3. Core Sphere (The "Energy Source") ---
        core_r = r * 0.9
        grad = QRadialGradient(cx - core_r * 0.3, cy - core_r * 0.3, core_r * 1.5)

        # Deep blue/purple gradient
        c1 = QColor(120, 180, 255) if is_active else QColor(100, 140, 255)
        c2 = QColor(60, 40, 200)
        c3 = QColor(10, 5, 40)

        grad.setColorAt(0.0, c1)
        grad.setColorAt(0.4, c2)
        grad.setColorAt(1.0, c3)

        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))

        # --- 4. 3D Particles Ring (Front) ---
        self._draw_rings(painter, cx, cy, r, front=True)

        # --- 5. Inner Highlight (Glass reflection) ---
        hl_r = core_r * 0.8
        hl = QRadialGradient(cx - hl_r * 0.5, cy - hl_r * 0.5, hl_r)
        hl.setColorAt(0.0, QColor(255, 255, 255, 90))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(hl))
        painter.drawEllipse(QRectF(cx - hl_r * 0.8, cy - hl_r * 0.8, hl_r * 1.4, hl_r * 1.4))

        painter.end()

    def _draw_rings(self, p: QPainter, cx: float, cy: float, r: float, front: bool):
        # Draw orbiting particles/lines
        # We use a simple pseudo-3D projection: y is compressed (tilt)
        tilt = 0.4
        num_rings = 3

        for i in range(num_rings):
            # Ring parameters
            ring_r = r * (1.4 + i*0.4)
            speed = (self._phase * (1.0 + i*0.5))
            angle_offset = i * 2.0

            # Use 'waves' config if available or defaults
            color_base = self._waves[i % len(self._waves)]["color"]

            # We draw arcs or particles
            # Let's draw dynamic particles orbiting
            num_particles = 12
            for j in range(num_particles):
                angle = (j / num_particles) * math.tau + speed + angle_offset

                # 3D coordinates
                x = math.cos(angle) * ring_r
                z = math.sin(angle) * ring_r  # Depth
                y = z * tilt

                # Z-sorting: only draw if z match front/back request
                is_front = z > 0
                if is_front != front:
                    continue

                # Perspective scaling
                scale = 1.0 + (z / ring_r) * 0.3
                alpha_factor = 0.5 + (z / ring_r) * 0.5

                # Draw particle
                size = 3.0 * scale + (self._audio_level * 5.0)
                alpha = int(color_base.alpha() * alpha_factor)

                col = QColor(color_base)
                col.setAlpha(min(255, alpha))
                p.setBrush(col)
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx + x, cy + y), size, size)


# ---------------------------------------------------------------------------
# Video Sphere Player — plays the mp4 sphere animation on loop
# ---------------------------------------------------------------------------

class SphereVideoPlayer(QWidget):
    """Plays the AI sphere animation video on loop inside a dark container.

    Falls back to EnergySphere (QPainter) if video file is missing
    or PyQt5.QtMultimedia is not installed.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        # Fallback: QPainter sphere (always available)
        self._sphere_fallback = EnergySphere()
        self._stack.addWidget(self._sphere_fallback)

        # Try video player
        self._player = None
        self._video_widget = None

        if _HAS_MULTIMEDIA and _SPHERE_VIDEO.exists():
            try:
                self._video_widget = QVideoWidget()
                self._video_widget.setStyleSheet("background: black;")
                self._video_widget.setAspectRatioMode(Qt.KeepAspectRatio)
                self._stack.addWidget(self._video_widget)

                self._player = QMediaPlayer(self, QMediaPlayer.VideoSurface)
                self._player.setVideoOutput(self._video_widget)

                # Loop the video
                playlist = QMediaPlaylist(self)
                playlist.addMedia(QMediaContent(QUrl.fromLocalFile(str(_SPHERE_VIDEO))))
                playlist.setPlaybackMode(QMediaPlaylist.Loop)
                self._player.setPlaylist(playlist)
                self._player.setVolume(0)  # mute the video audio

                # Show video widget
                self._stack.setCurrentWidget(self._video_widget)
            except Exception:
                # Any failure → fall back to QPainter
                self._player = None
                self._stack.setCurrentWidget(self._sphere_fallback)
        else:
            self._stack.setCurrentWidget(self._sphere_fallback)

    def set_active(self, active: bool) -> None:
        self._sphere_fallback.set_active(active)
        if self._player:
            if active:
                self._player.play()
            else:
                self._player.pause()

    def set_audio_level(self, level: float) -> None:
        self._sphere_fallback.set_audio_level(level)

    @property
    def has_video(self) -> bool:
        return self._player is not None


# ---------------------------------------------------------------------------
# Voice Overlay — the full glassmorphism card
# ---------------------------------------------------------------------------

class VoiceOverlay(QWidget):
    """
    Full-width voice assistant overlay — shown over the chat area.
    Contains:
    - Close button (top-right)
    - Live transcription text (grows as user speaks)
    - Animated energy sphere
    - Big mic toggle button
    - Status label

    Signals:
        voice_stopped: emitted when user closes the overlay or taps mic off
        text_submitted(str): emitted when a final recognized sentence is ready
    """

    voice_stopped = pyqtSignal()
    text_submitted = pyqtSignal(str)
    language_changed = pyqtSignal(str)  # lang code like "en", "hi", etc.

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("VoiceOverlay")
        self._is_listening = False
        self._partial_text = ""
        self._final_text = ""

        # Silence auto-submit: fires 2.5s after the last speech update
        self._silence_timer = QTimer(self)
        self._silence_timer.setSingleShot(True)
        self._silence_timer.setInterval(2500)
        self._silence_timer.timeout.connect(self._on_silence_timeout)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            #VoiceOverlay {
                background: rgba(8, 10, 22, 0.92);
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Inner card (centered, max 480px wide)
        self._card = QWidget()
        self._card.setObjectName("VoiceCard")
        self._card.setMaximumWidth(480)
        self._card.setStyleSheet("""
            #VoiceCard {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(18, 22, 45, 0.95),
                    stop:1 rgba(12, 15, 35, 0.98)
                );
                border: 1px solid rgba(80, 120, 255, 0.15);
                border-radius: 20px;
            }
        """)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(28, 20, 28, 24)
        card_layout.setSpacing(12)

        # Top row — language selector + close button
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self._lang_combo = QComboBox()
        self._lang_combo.setFixedWidth(170)
        self._lang_combo.setCursor(Qt.PointingHandCursor)
        self._lang_combo.setStyleSheet("""
            QComboBox {
                color: rgba(180, 190, 230, 0.9);
                background: rgba(80, 120, 255, 0.08);
                border: 1px solid rgba(80, 120, 255, 0.15);
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
            QComboBox QAbstractItemView {
                background: rgba(18, 22, 45, 0.98);
                color: rgba(200, 210, 240, 0.9);
                border: 1px solid rgba(80, 120, 255, 0.2);
                selection-background-color: rgba(80, 120, 255, 0.2);
                font-size: 11px;
            }
        """)
        # Default: just English
        self._lang_combo.addItem("🌐  English", "en")
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        top_row.addWidget(self._lang_combo)
        top_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                color: rgba(200, 210, 240, 0.7);
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 80, 80, 0.15);
                color: #ff6b6b;
                border-color: rgba(255, 80, 80, 0.3);
            }
        """)
        close_btn.clicked.connect(self._on_close)
        top_row.addWidget(close_btn)
        card_layout.addLayout(top_row)

        # Transcription text — shows what the user is saying
        self._transcript = QLabel("")
        self._transcript.setWordWrap(True)
        self._transcript.setMinimumHeight(60)
        self._transcript.setMaximumHeight(120)
        self._transcript.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._transcript.setStyleSheet(
            "color: rgba(220, 225, 250, 0.95); "
            "font-size: 18px; font-weight: 400; "
            "line-height: 1.5; background: transparent; "
            "padding: 8px 4px;"
        )
        card_layout.addWidget(self._transcript)

        # Sphere animation — video player with QPainter fallback
        self._sphere = SphereVideoPlayer()
        self._sphere.setFixedHeight(280)
        card_layout.addWidget(self._sphere)

        # Mic button — big round toggle
        mic_row = QHBoxLayout()
        mic_row.setAlignment(Qt.AlignCenter)

        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setFixedSize(64, 64)
        self._mic_btn.setCursor(Qt.PointingHandCursor)
        self._mic_btn.setCheckable(True)
        self._mic_btn.setStyleSheet("""
            QPushButton {
                background: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.5,
                    fx:0.5, fy:0.4,
                    stop:0 rgba(255, 255, 255, 0.95),
                    stop:0.8 rgba(220, 230, 255, 0.9),
                    stop:1 rgba(180, 200, 240, 0.85)
                );
                border: 2px solid rgba(140, 170, 255, 0.3);
                border-radius: 32px;
                font-size: 24px;
            }
            QPushButton:checked {
                background: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.5,
                    fx:0.5, fy:0.4,
                    stop:0 rgba(100, 140, 255, 0.95),
                    stop:0.8 rgba(80, 110, 230, 0.9),
                    stop:1 rgba(60, 80, 200, 0.85)
                );
                border-color: rgba(100, 160, 255, 0.6);
            }
            QPushButton:hover {
                border-color: rgba(140, 180, 255, 0.5);
            }
        """)
        # Add a glow shadow
        shadow = QGraphicsDropShadowEffect(self._mic_btn)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(80, 120, 255, 80))
        shadow.setOffset(0, 0)
        self._mic_btn.setGraphicsEffect(shadow)
        self._mic_btn.clicked.connect(self._on_mic_toggle)
        mic_row.addWidget(self._mic_btn)
        card_layout.addLayout(mic_row)

        # Status label
        self._status = QLabel("Tap mic to start listening")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet(
            "color: rgba(140, 150, 190, 0.7); font-size: 11px; "
            "background: transparent; letter-spacing: 0.3px;"
        )
        card_layout.addWidget(self._status)

        # Add card centered in main layout
        main_layout.addStretch()
        h_center = QHBoxLayout()
        h_center.addStretch()
        h_center.addWidget(self._card)
        h_center.addStretch()
        main_layout.addLayout(h_center)
        main_layout.addStretch()

    # --- Public API ---

    def activate(self) -> None:
        """Show overlay and start in listening state."""
        self.setVisible(True)
        self._mic_btn.setChecked(True)
        self._is_listening = True
        self._sphere.set_active(True)
        self._transcript.setText("")
        self._partial_text = ""
        self._final_text = ""
        self._status.setText("Listening... speak in any language")

    def deactivate(self) -> None:
        """Hide overlay and stop."""
        self._is_listening = False
        self._mic_btn.setChecked(False)
        self._sphere.set_active(False)
        self._silence_timer.stop()
        self.setVisible(False)

    def set_audio_level(self, level: float) -> None:
        """Forward audio level to sphere."""
        self._sphere.set_audio_level(level)

    def set_partial_text(self, text: str) -> None:
        """Show partial (in-progress) transcription."""
        self._partial_text = text
        self._update_transcript_display()
        # Reset silence timer — speech is still happening
        if self._is_listening and text.strip():
            self._silence_timer.start()

    def set_final_text(self, text: str) -> None:
        """Append finalized text and emit."""
        if text.strip():
            self._final_text = text.strip()
            self._partial_text = ""
            self._update_transcript_display()
            # Start silence timer — if no new speech within 2.5s, auto-submit
            if self._is_listening:
                self._silence_timer.start()

    def _on_silence_timeout(self) -> None:
        """Auto-submit when user stops speaking for 2.5 seconds."""
        if self._final_text.strip() and self._is_listening:
            self.text_submitted.emit(self._final_text.strip())
            self._status.setText("Sent! Listening for next command...")
            self._final_text = ""
            self._partial_text = ""
            self._update_transcript_display()
            # Brief pause then reset status
            QTimer.singleShot(1500, lambda: (
                self._status.setText("Listening... speak in any language")
                if self._is_listening else None
            ))

    def set_available_languages(self, downloaded_codes: list[str]) -> None:
        """Populate the language dropdown.

        Shows all supported languages. Downloaded ones get a checkmark,
        others show a download icon so users know a fetch will happen.
        """
        self._lang_combo.blockSignals(True)
        self._lang_combo.clear()

        # Show downloaded languages first, then the rest
        all_codes = list(LANGUAGE_NAMES.keys())
        downloaded_set = set(downloaded_codes)

        for code in all_codes:
            name = LANGUAGE_NAMES.get(code, code.upper())
            if code in downloaded_set:
                self._lang_combo.addItem(f"✓  {name}", code)
            else:
                self._lang_combo.addItem(f"⬇  {name}", code)

        self._lang_combo.blockSignals(False)

    def set_language_detected(self, lang: str) -> None:
        """Update the language combo to show detected language."""
        for i in range(self._lang_combo.count()):
            if self._lang_combo.itemData(i) == lang:
                self._lang_combo.blockSignals(True)
                self._lang_combo.setCurrentIndex(i)
                self._lang_combo.blockSignals(False)
                break

    # --- Internals ---

    def _update_transcript_display(self) -> None:
        """Combine final + partial text with bold cursor effect."""
        display = ""
        if self._final_text:
            display = self._final_text
        if self._partial_text:
            if display:
                display += " "
            display += f"<b>{self._partial_text}</b><span style='color: rgba(100,140,255,0.8);'>...</span>"
        if not display and self._is_listening:
            display = "<span style='color: rgba(140,150,190,0.5);'>Listening...</span>"
        self._transcript.setText(display)

    def _on_language_changed(self) -> None:
        lang_code = self._lang_combo.currentData()
        if lang_code:
            self.language_changed.emit(lang_code)

    def _on_mic_toggle(self) -> None:
        self._is_listening = self._mic_btn.isChecked()
        if self._is_listening:
            self._sphere.set_active(True)
            self._status.setText("Listening... speak in any language")
            self._transcript.setText("")
            self._partial_text = ""
            self._final_text = ""
        else:
            self._sphere.set_active(False)
            self._status.setText("Mic off — tap to start")
            # If there's text, submit it
            if self._final_text.strip():
                self.text_submitted.emit(self._final_text.strip())
            self.voice_stopped.emit()

    def _on_close(self) -> None:
        """Close button — submit any pending text and hide."""
        if self._final_text.strip():
            self.text_submitted.emit(self._final_text.strip())
        self.deactivate()
        self.voice_stopped.emit()

    @property
    def is_listening(self) -> bool:
        return self._is_listening
