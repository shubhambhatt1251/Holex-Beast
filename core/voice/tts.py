"""Text-to-speech with Edge TTS (primary) and pyttsx3 (offline fallback).

Supports auto-switching voices by language — when the user picks Hindi
in the voice overlay, TTS responds in a Hindi neural voice, etc.
"""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

from core.config import TTSEngine, get_settings
from core.events import EventType, get_event_bus

logger = logging.getLogger(__name__)


def strip_markdown(text: str) -> str:
    """Remove markdown formatting so TTS reads clean prose.

    Strips: bold, italic, code blocks, inline code, headers,
    blockquotes, horizontal rules, links, images, HTML tags,
    bullet/number markers, and excessive whitespace.
    """
    # Fenced code blocks — remove entirely (code isn't speakable)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Images ![alt](url)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # Links [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Headers ## text → text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Bold / italic
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Strikethrough
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    # Blockquotes
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    # Horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Bullet/number markers
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)
    # HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Newlines → period-space for sentence separation
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", ". ", text)
    # Collapse whitespace
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()

# Edge TTS neural voices per language code.
# Each entry is (female_voice, male_voice). We default to the first one.
EDGE_TTS_VOICES: dict[str, tuple[str, str]] = {
    # International
    "en": ("en-US-JennyNeural", "en-US-GuyNeural"),
    "cn": ("zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"),
    "ru": ("ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"),
    "fr": ("fr-FR-DeniseNeural", "fr-FR-HenriNeural"),
    "de": ("de-DE-KatjaNeural", "de-DE-ConradNeural"),
    "es": ("es-ES-ElviraNeural", "es-ES-AlvaroNeural"),
    "pt": ("pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"),
    "tr": ("tr-TR-EmelNeural", "tr-TR-AhmetNeural"),
    "ja": ("ja-JP-NanamiNeural", "ja-JP-KeitaNeural"),
    "ko": ("ko-KR-SunHiNeural", "ko-KR-InJoonNeural"),
    "ar": ("ar-SA-ZariyahNeural", "ar-SA-HamedNeural"),
    "it": ("it-IT-ElsaNeural", "it-IT-DiegoNeural"),
    "nl": ("nl-NL-ColetteNeural", "nl-NL-MaartenNeural"),
    "uk": ("uk-UA-PolinaNeural", "uk-UA-OstapNeural"),
    "fa": ("fa-IR-DilaraNeural", "fa-IR-FaridNeural"),
    "vi": ("vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"),
    # Indian languages
    "en-in": ("en-IN-NeerjaNeural", "en-IN-PrabhatNeural"),
    "hi": ("hi-IN-SwaraNeural", "hi-IN-MadhurNeural"),
    "gu": ("gu-IN-DhwaniNeural", "gu-IN-NiranjanNeural"),
    "te": ("te-IN-ShrutiNeural", "te-IN-MohanNeural"),
    "ta": ("ta-IN-PallaviNeural", "ta-IN-ValluvarNeural"),
    "bn": ("bn-IN-TanishaaNeural", "bn-IN-BashkarNeural"),
    "mr": ("mr-IN-AarohiNeural", "mr-IN-ManoharNeural"),
    "kn": ("kn-IN-SapnaNeural", "kn-IN-GaganNeural"),
    "ml": ("ml-IN-SobhanaNeural", "ml-IN-MidhunNeural"),
    "ur": ("ur-IN-GulNeural", "ur-IN-SalmanNeural"),
    "pa": ("pa-IN-OjasNeural", "pa-IN-OjasNeural"),  # limited availability
}


class TextToSpeech:
    """
    Multi-engine text-to-speech.
    Primary: Edge TTS (neural voices, requires internet)
    Fallback: pyttsx3 (offline, basic quality)
    """

    def __init__(self):
        self.settings = get_settings()
        self.bus = get_event_bus()
        self._engine_type = self.settings.voice.tts_engine
        self._is_speaking = False
        self._stop_flag = False
        self._current_language = "en"

    def set_language(self, lang_code: str) -> None:
        """Switch TTS voice to match the given language.

        The right Edge TTS neural voice is picked automatically.
        """
        self._current_language = lang_code
        logger.info(f"TTS language set to: {lang_code}")

    def _get_voice_for_language(self, voice_override: Optional[str] = None) -> str:
        """Return the Edge TTS voice name for the current language."""
        if voice_override:
            return voice_override
        pair = EDGE_TTS_VOICES.get(self._current_language)
        if pair:
            return pair[0]  # female voice by default
        return self.settings.voice.tts_voice  # fallback to config default

    async def speak(self, text: str, voice: Optional[str] = None) -> None:
        """Speak text using configured TTS engine.

        Voice is auto-selected based on the current language unless
        an explicit override is passed. Markdown is stripped so TTS
        reads clean prose.
        """
        if not text.strip():
            return

        # Clean markdown / formatting before speaking
        text = strip_markdown(text)
        if not text:
            return

        self._is_speaking = True
        self._stop_flag = False
        self.bus.emit(EventType.VOICE_TTS_START, {"text": text[:100]})

        try:
            if self._engine_type == TTSEngine.EDGE_TTS:
                await self._speak_edge_tts(text, voice)
            elif self._engine_type == TTSEngine.PYTTSX3:
                await self._speak_pyttsx3(text)
            else:
                await self._speak_edge_tts(text, voice)
        except Exception as e:
            logger.error(f"TTS failed with {self._engine_type}: {e}")
            # Fallback to pyttsx3
            if self._engine_type != TTSEngine.PYTTSX3:
                logger.info("Falling back to pyttsx3...")
                try:
                    await self._speak_pyttsx3(text)
                except Exception as e2:
                    logger.error(f"Fallback TTS also failed: {e2}")
                    self.bus.emit(EventType.VOICE_TTS_ERROR, {"error": str(e2)})
        finally:
            self._is_speaking = False
            self.bus.emit(EventType.VOICE_TTS_END, {})

    async def _speak_edge_tts(self, text: str, voice: Optional[str] = None) -> None:
        """Speak using Microsoft Edge TTS (good quality, needs internet)."""
        try:
            import edge_tts
            import pygame

            voice = self._get_voice_for_language(voice)

            # Generate audio
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=self.settings.voice.tts_rate,
                volume=self.settings.voice.tts_volume,
            )

            # Save to temp file and play
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name

            await communicate.save(tmp_path)

            if self._stop_flag:
                return

            # Play audio
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                if self._stop_flag:
                    pygame.mixer.music.stop()
                    break
                await asyncio.sleep(0.1)

            pygame.mixer.music.unload()

            # Cleanup
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass

        except ImportError as e:
            raise ImportError(f"Required package missing: {e}. Run: pip install edge-tts pygame")

    async def _speak_pyttsx3(self, text: str) -> None:
        """Speak using pyttsx3 (offline fallback)."""
        try:
            import pyttsx3

            def _run():
                engine = pyttsx3.init()
                voices = engine.getProperty("voices")
                # Try to find a good voice
                for v in voices:
                    if "zira" in v.name.lower() or "david" in v.name.lower():
                        engine.setProperty("voice", v.id)
                        break
                engine.setProperty("rate", 180)
                engine.setProperty("volume", 0.9)
                engine.say(text)
                engine.runAndWait()
                engine.stop()

            # Run in thread to avoid blocking
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _run)

        except ImportError:
            raise ImportError("pyttsx3 not installed. Run: pip install pyttsx3")

    def stop(self) -> None:
        """Stop current speech."""
        self._stop_flag = True
        try:
            import pygame
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
        except Exception:
            pass
        self._is_speaking = False

    @staticmethod
    async def list_voices() -> list[dict]:
        """List available Edge TTS voices."""
        try:
            import edge_tts
            voices = await edge_tts.list_voices()
            return [
                {
                    "id": v["ShortName"],
                    "name": v["FriendlyName"],
                    "language": v["Locale"],
                    "gender": v["Gender"],
                }
                for v in voices
            ]
        except Exception:
            return []

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
