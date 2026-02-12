"""Offline speech-to-text using Vosk with multi-language support."""

from __future__ import annotations

import json
import logging
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

from core.config import get_settings
from core.events import EventType, get_event_bus

logger = logging.getLogger(__name__)

# Available Vosk models — download from https://alphacephei.com/vosk/models
# Place in models/ directory. The key is the language code.
VOSK_MODEL_MAP = {
    # International
    "en": "vosk-model-small-en-us-0.15",
    "cn": "vosk-model-small-cn-0.22",
    "ru": "vosk-model-small-ru-0.22",
    "fr": "vosk-model-small-fr-0.22",
    "de": "vosk-model-small-de-0.15",
    "es": "vosk-model-small-es-0.42",
    "pt": "vosk-model-small-pt-0.3",
    "tr": "vosk-model-small-tr-0.3",
    "ja": "vosk-model-small-ja-0.22",
    "ko": "vosk-model-small-ko-0.22",
    "ar": "vosk-model-ar-mgb2-0.4",
    "it": "vosk-model-small-it-0.22",
    "nl": "vosk-model-small-nl-0.22",
    "uk": "vosk-model-small-uk-v3-nano",
    "fa": "vosk-model-small-fa-0.5",
    "vi": "vosk-model-small-vn-0.4",
    # Indian languages
    "en-in": "vosk-model-small-en-in-0.4",
    "hi": "vosk-model-small-hi-0.22",
    "gu": "vosk-model-small-gu-0.42",
    "te": "vosk-model-small-te-0.42",
    "ta": "vosk-model-small-ta-0.22",
    "bn": "vosk-model-small-bn-0.22",
    "mr": "vosk-model-small-mr-0.22",
    "kn": "vosk-model-small-kn-0.22",
    "ml": "vosk-model-small-ml-0.22",
    "ur": "vosk-model-small-ur-0.22",
    "pa": "vosk-model-small-pa-0.22",
}


class SpeechToText:
    """
    Vosk-based speech-to-text engine.
    Supports multiple languages — set the model path to the matching
    Vosk model for your language. The default English model ships with
    the project. Other models can be downloaded from alphacephei.com/vosk/models.
    """

    def __init__(self):
        self.settings = get_settings()
        self.bus = get_event_bus()
        self._recognizer = None
        self._model = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._is_listening = False
        self._listen_thread: Optional[threading.Thread] = None
        self._stream = None
        self._audio_interface = None
        self._current_language = "en"

    def initialize(self, model_path: Optional[str] = None) -> bool:
        """Load Vosk model and initialize audio.

        Args:
            model_path: Override path to a specific Vosk model directory.
                        If None, uses the path from settings.
        """
        try:
            from vosk import KaldiRecognizer, Model

            path = model_path or self.settings.voice.stt_model_path
            if not Path(path).exists():
                logger.error(f"Vosk model not found at: {path}")
                logger.info("Download from: https://alphacephei.com/vosk/models")
                return False

            self._model = Model(path)
            self._recognizer = KaldiRecognizer(
                self._model, self.settings.voice.sample_rate
            )
            self._recognizer.SetWords(True)

            logger.info(f"Speech-to-Text initialized (Vosk, model: {Path(path).name})")
            return True

        except ImportError:
            logger.error("vosk not installed. Run: pip install vosk")
            return False
        except Exception as e:
            logger.error(f"STT init failed: {e}")
            return False

    def switch_language(self, lang_code: str) -> bool:
        """Switch to a different language model at runtime.

        Args:
            lang_code: Language code like 'en', 'hi', 'es', etc.
                       See VOSK_MODEL_MAP for available options.

        Returns:
            True if the model was loaded successfully.
        """
        model_name = VOSK_MODEL_MAP.get(lang_code)
        if not model_name:
            logger.warning(f"No Vosk model mapped for language: {lang_code}")
            return False

        models_dir = Path(self.settings.voice.stt_model_path).parent
        model_path = models_dir / model_name

        if not model_path.exists():
            logger.warning(
                f"Model not found: {model_path}. "
                f"Download it from https://alphacephei.com/vosk/models"
            )
            return False

        was_listening = self._is_listening
        if was_listening:
            self.stop_listening()

        success = self.initialize(str(model_path))
        if success:
            self._current_language = lang_code
            logger.info(f"Switched STT to: {lang_code} ({model_name})")

        return success

    @property
    def current_language(self) -> str:
        return self._current_language

    @property
    def available_languages(self) -> list[str]:
        """Return language codes that have models downloaded locally."""
        models_dir = Path(self.settings.voice.stt_model_path).parent
        available = []
        for code, model_name in VOSK_MODEL_MAP.items():
            if (models_dir / model_name).exists():
                available.append(code)
        if not available:
            available.append("en")  # default always "available"
        return available

    def start_listening(
        self,
        on_result: Optional[Callable[[str], None]] = None,
        on_partial: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Start continuous listening in background thread."""
        if self._is_listening:
            return

        self._is_listening = True
        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            args=(on_result, on_partial),
            daemon=True,
        )
        self._listen_thread.start()
        self.bus.emit(EventType.VOICE_LISTENING_START, {})
        logger.info("Listening started")

    def stop_listening(self) -> None:
        """Stop listening."""
        self._is_listening = False
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._audio_interface:
            try:
                self._audio_interface.terminate()
            except Exception:
                pass
            self._audio_interface = None

        self.bus.emit(EventType.VOICE_LISTENING_STOP, {})
        logger.info("Listening stopped")

    def _listen_loop(
        self,
        on_result: Optional[Callable] = None,
        on_partial: Optional[Callable] = None,
    ) -> None:
        """Main listening loop (runs in background thread)."""
        try:
            import pyaudio

            self._audio_interface = pyaudio.PyAudio()
            self._stream = self._audio_interface.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.settings.voice.sample_rate,
                input=True,
                frames_per_buffer=1024,
            )

            logger.debug("Audio stream opened")

            while self._is_listening:
                try:
                    data = self._stream.read(1024, exception_on_overflow=False)
                except Exception:
                    continue

                # Calculate audio level for visualization
                import struct
                samples = struct.unpack(f"{len(data)//2}h", data)
                rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
                level = min(1.0, rms / 32768.0 * 5)
                self.bus.emit(EventType.VOICE_AUDIO_LEVEL, {"level": level})

                if self._recognizer.AcceptWaveform(data):
                    result = json.loads(self._recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        logger.info(f"Recognized: {text}")
                        self.bus.emit(EventType.VOICE_STT_RESULT, {"text": text})
                        if on_result:
                            on_result(text)
                else:
                    partial = json.loads(self._recognizer.PartialResult())
                    text = partial.get("partial", "").strip()
                    if text:
                        self.bus.emit(EventType.VOICE_STT_PARTIAL, {"text": text})
                        if on_partial:
                            on_partial(text)

        except ImportError:
            logger.error("pyaudio not installed. Run: pip install pyaudio")
        except Exception as e:
            logger.error(f"Listen loop error: {e}")
        finally:
            self.stop_listening()

    def recognize_once(self, timeout: float = 5.0) -> Optional[str]:
        """Listen for a single utterance and return text."""
        try:
            import pyaudio

            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.settings.voice.sample_rate,
                input=True,
                frames_per_buffer=4096,
            )

            import time
            start = time.time()
            silence_start = None
            text = ""

            while time.time() - start < timeout:
                data = stream.read(4096, exception_on_overflow=False)

                if self._recognizer.AcceptWaveform(data):
                    result = json.loads(self._recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        break

                # Check for silence (end of speech)
                import struct
                samples = struct.unpack(f"{len(data)//2}h", data)
                rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
                if rms < 150:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > self.settings.voice.silence_threshold:
                        # Silence detected, get final result
                        final = json.loads(self._recognizer.FinalResult())
                        text = final.get("text", "").strip()
                        break
                else:
                    silence_start = None

            stream.stop_stream()
            stream.close()
            audio.terminate()
            return text or None

        except Exception as e:
            logger.error(f"Recognize once failed: {e}")
            return None

    @property
    def is_listening(self) -> bool:
        return self._is_listening
