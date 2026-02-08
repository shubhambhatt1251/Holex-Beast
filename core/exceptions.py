"""App-specific exceptions so we can catch them cleanly."""


class HolexError(Exception):
    """Base exception for all Holex Beast errors."""
    def __init__(self, message: str = "", code: str = "UNKNOWN"):
        self.message = message
        self.code = code
        super().__init__(self.message)


# LLM Errors

class LLMError(HolexError):
    """Base LLM error."""
    pass

class ProviderNotAvailableError(LLMError):
    """LLM provider is not configured or unreachable."""
    def __init__(self, provider: str):
        super().__init__(f"Provider '{provider}' is not available", "PROVIDER_UNAVAILABLE")

class AllProvidersFailedError(LLMError):
    """All LLM providers failed to respond."""
    def __init__(self):
        super().__init__("All LLM providers failed", "ALL_PROVIDERS_FAILED")

class ModelNotFoundError(LLMError):
    """Requested model not found on provider."""
    def __init__(self, model: str, provider: str):
        super().__init__(f"Model '{model}' not found on {provider}", "MODEL_NOT_FOUND")

class RateLimitError(LLMError):
    """API rate limit exceeded."""
    def __init__(self, provider: str, retry_after: float = 0):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded on {provider}", "RATE_LIMIT")

class TokenLimitError(LLMError):
    """Token/context limit exceeded."""
    def __init__(self, tokens: int, limit: int):
        super().__init__(f"Token limit exceeded: {tokens}/{limit}", "TOKEN_LIMIT")


# Agent Errors

class AgentError(HolexError):
    """Base agent error."""
    pass

class ToolExecutionError(AgentError):
    """Tool failed to execute."""
    def __init__(self, tool_name: str, reason: str):
        super().__init__(f"Tool '{tool_name}' failed: {reason}", "TOOL_EXEC_ERROR")

class ToolNotFoundError(AgentError):
    """Requested tool doesn't exist."""
    def __init__(self, tool_name: str):
        super().__init__(f"Tool '{tool_name}' not found", "TOOL_NOT_FOUND")

class MaxIterationsError(AgentError):
    """Agent exceeded maximum reasoning iterations."""
    def __init__(self, max_iter: int):
        super().__init__(f"Agent exceeded {max_iter} iterations", "MAX_ITERATIONS")


# Voice Errors

class VoiceError(HolexError):
    """Base voice error."""
    pass

class STTError(VoiceError):
    """Speech-to-text error."""
    def __init__(self, reason: str):
        super().__init__(f"STT failed: {reason}", "STT_ERROR")

class TTSError(VoiceError):
    """Text-to-speech error."""
    def __init__(self, reason: str):
        super().__init__(f"TTS failed: {reason}", "TTS_ERROR")

class WakeWordError(VoiceError):
    """Wake word detection error."""
    def __init__(self, reason: str):
        super().__init__(f"Wake word error: {reason}", "WAKE_WORD_ERROR")


# RAG Errors

class RAGError(HolexError):
    """Base RAG error."""
    pass

class DocumentParsingError(RAGError):
    """Failed to parse document for RAG."""
    def __init__(self, filename: str, reason: str):
        super().__init__(f"Cannot parse '{filename}': {reason}", "DOC_PARSE_ERROR")

class EmbeddingError(RAGError):
    """Failed to generate embeddings."""
    def __init__(self, reason: str):
        super().__init__(f"Embedding failed: {reason}", "EMBEDDING_ERROR")


# Firebase Errors

class FirebaseError(HolexError):
    """Base Firebase error."""
    pass

class AuthenticationError(FirebaseError):
    """Firebase authentication failed."""
    def __init__(self, reason: str):
        super().__init__(f"Auth failed: {reason}", "AUTH_ERROR")

class SyncError(FirebaseError):
    """Firebase sync failed."""
    def __init__(self, reason: str):
        super().__init__(f"Sync failed: {reason}", "SYNC_ERROR")


# Plugin Errors

class PluginError(HolexError):
    """Base plugin error."""
    pass

class PluginLoadError(PluginError):
    """Plugin failed to load."""
    def __init__(self, plugin_name: str, reason: str):
        super().__init__(f"Plugin '{plugin_name}' failed to load: {reason}", "PLUGIN_LOAD_ERROR")
