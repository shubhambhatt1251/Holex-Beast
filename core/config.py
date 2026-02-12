"""App config. Reads .env file and provides typed settings.

## Personality:
- Friendly, intelligent, and helpful
- Conversational and engaging
- Confident, honest about limitations
- eager to assist with detailed explanations
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    GROQ = "groq"
    GEMINI = "gemini"


class TTSEngine(str, Enum):
    """Supported TTS engines."""
    EDGE_TTS = "edge_tts"
    PIPER = "piper"
    PYTTSX3 = "pyttsx3"


class ThemeMode(str, Enum):
    """UI theme modes."""
    DARK = "dark"
    LIGHT = "light"
    MIDNIGHT = "midnight"


class GroqSettings(BaseSettings):
    """Groq cloud API settings."""
    model_config = SettingsConfigDict(
        env_prefix="GROQ_",
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = ""
    default_model: str = "moonshotai/kimi-k2-instruct"
    fast_model: str = "llama-3.1-8b-instant"
    base_url: str = "https://api.groq.com/openai/v1"
    max_tokens: int = 4096
    temperature: float = 0.7


class GeminiSettings(BaseSettings):
    """Google Gemini API settings."""
    model_config = SettingsConfigDict(
        env_prefix="GEMINI_",
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = ""
    default_model: str = "gemini-2.5-flash"
    pro_model: str = "gemini-2.5-pro"
    max_tokens: int = 8192
    temperature: float = 0.7


class OllamaSettings(BaseSettings):
    """Ollama local server settings."""
    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_",
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = "http://localhost:11434"
    default_model: str = "llama3.2:3b"
    embedding_model: str = "nomic-embed-text"
    timeout: int = 120


class FirebaseSettings(BaseSettings):
    """Firebase config (optional, falls back to SQLite)."""
    model_config = SettingsConfigDict(
        env_prefix="FIREBASE_",
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = ""
    auth_domain: str = ""
    project_id: str = ""
    storage_bucket: str = ""
    messaging_sender_id: str = ""
    app_id: str = ""
    database_url: str = ""
    service_account_path: Optional[str] = None


class VoiceSettings(BaseSettings):
    """Voice engine configuration."""
    model_config = SettingsConfigDict(env_prefix="")

    wake_word: str = "hey holex"
    stt_model_path: str = str(MODELS_DIR / "vosk-model-small-en-us-0.15")
    tts_voice: str = "en-US-GuyNeural"
    tts_engine: TTSEngine = TTSEngine.EDGE_TTS
    tts_rate: str = "+0%"
    tts_volume: str = "+0%"
    voice_activation: bool = True
    silence_threshold: float = 3.0
    sample_rate: int = 16000


class RAGSettings(BaseSettings):
    """RAG pipeline configuration."""
    model_config = SettingsConfigDict(env_prefix="")

    chroma_db_path: str = str(DATA_DIR / "chroma_db")
    embedding_model: str = "nomic-embed-text"
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5
    similarity_threshold: float = 0.7


class AppSettings(BaseSettings):
    """Main app settings. Sub-configs auto-load from .env."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App Metadata
    app_name: str = "Holex Beast"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # LLM Router
    default_provider: LLMProvider = LLMProvider.GROQ
    fallback_provider: LLMProvider = LLMProvider.GEMINI
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = True

    # Theme
    theme: ThemeMode = ThemeMode.DARK

    # Sub-configs
    groq: GroqSettings = Field(default_factory=GroqSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    firebase: FirebaseSettings = Field(default_factory=FirebaseSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)

    # Conversational Prompt
    conversational_prompt: str = (
        "You are a friendly, intelligent, and helpful AI assistant named Holex. "
        "Engage in natural, conversational dialogue. "
        "Explain your reasoning and provide helpful context. "
        "Use markdown for chat, but keep voice answers natural (avoid long lists if speaking). "
        "Use tools when you need real-time data or system control. "
        "If unsure, say so honestly. For complex questions, break down reasoning thoroughly. "
        "Cite sources when using web search."
    )

    @property
    def is_groq_configured(self) -> bool:
        return bool(self.groq.api_key and self.groq.api_key != "gsk_your_groq_key_here")

    @property
    def is_gemini_configured(self) -> bool:
        return bool(self.gemini.api_key and self.gemini.api_key != "your_gemini_key_here")

    @property
    def is_firebase_configured(self) -> bool:
        return bool(self.firebase.project_id and self.firebase.api_key)

    @property
    def is_ollama_available(self) -> bool:
        """Check if Ollama server is running."""
        try:
            import httpx
            resp = httpx.get(f"{self.ollama.base_url}/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def get_available_providers(self) -> list[LLMProvider]:
        """Return list of configured/available LLM providers."""
        providers = []
        if self.is_groq_configured:
            providers.append(LLMProvider.GROQ)
        if self.is_gemini_configured:
            providers.append(LLMProvider.GEMINI)
        if self.is_ollama_available:
            providers.append(LLMProvider.OLLAMA)
        return providers


# Singleton
_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """Get or create the singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


def reload_settings() -> AppSettings:
    """Force reload settings from .env file."""
    global _settings
    _settings = AppSettings()
    return _settings
