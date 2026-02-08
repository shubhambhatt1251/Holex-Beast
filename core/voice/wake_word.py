"""Wake-word detection ("Hey Holex") using Vosk keyword spotting."""

from __future__ import annotations

import json
import logging
import threading
from typing import Callable, Optional

from core.config import get_settings
from core.events import EventType, get_event_bus

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """
    Continuously listens for the wake word "Hey Holex".
    Uses Vosk's keyword detection in a low-power mode.
    """

    def __init__(self):
        self.settings = get_settings()
        self.bus = get_event_bus()
        self.wake_word = self.settings.voice.wake_word.lower()
        self._is_active = False
        self._thread: Optional[threading.Thread] = None
        self._model = None

    def start(self, on_wake: Optional[Callable] = None) -> None:
        """Start listening for wake word in background."""
        if self._is_active:
            return

        self._is_active = True
        self._thread = threading.Thread(
            target=self._detect_loop,
            args=(on_wake,),
            daemon=True,
        )
        self._thread.start()
        logger.info(f'Wake word detector active: "{self.wake_word}"')

    def stop(self) -> None:
        """Stop wake word detection."""
        self._is_active = False
        logger.info("Wake word detector stopped")

    def _detect_loop(self, on_wake: Optional[Callable] = None) -> None:
        """Main detection loop."""
        try:
            import pyaudio
            from vosk import KaldiRecognizer, Model

            model_path = self.settings.voice.stt_model_path
            model = Model(model_path)
            rec = KaldiRecognizer(model, self.settings.voice.sample_rate)

            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.settings.voice.sample_rate,
                input=True,
                frames_per_buffer=4096,
            )

            while self._is_active:
                data = stream.read(4096, exception_on_overflow=False)
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").lower().strip()

                    if self._match_wake_word(text):
                        logger.info(f"Wake word detected! ({text})")
                        self.bus.emit(EventType.VOICE_WAKE_WORD, {"text": text})
                        if on_wake:
                            on_wake()
                else:
                    partial = json.loads(rec.PartialResult())
                    text = partial.get("partial", "").lower().strip()
                    if self._match_wake_word(text):
                        logger.info(f"Wake word detected (partial)! ({text})")
                        self.bus.emit(EventType.VOICE_WAKE_WORD, {"text": text})
                        if on_wake:
                            on_wake()
                        # Reset recognizer after wake word
                        rec = KaldiRecognizer(model, self.settings.voice.sample_rate)

            stream.stop_stream()
            stream.close()
            audio.terminate()

        except Exception as e:
            logger.error(f"Wake word detection error: {e}")
            self._is_active = False

    def _match_wake_word(self, text: str) -> bool:
        """Check if text contains the wake word."""
        if not text:
            return False
        # Fuzzy matching for wake word
        wake_words = self.wake_word.split()
        return all(w in text for w in wake_words)

    @property
    def is_active(self) -> bool:
        return self._is_active
