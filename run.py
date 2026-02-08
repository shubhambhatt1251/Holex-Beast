"""Entry point - parses args, sets up services, launches the window."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Holex Beast AI Assistant")
    parser.add_argument("--theme", choices=["dark", "midnight", "light"], default="dark",
                        help="Initial theme (default: dark)")
    parser.add_argument("--offline", action="store_true",
                        help="Start in offline mode (Ollama only)")
    parser.add_argument("--no-voice", action="store_true",
                        help="Disable voice features")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    return parser.parse_args()


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(name)-24s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(ROOT / "logs" / "holex.log", encoding="utf-8"),
        ],
    )


def init_services(args: argparse.Namespace) -> dict:
    """Initialize all backend services. Returns dict of service references."""
    from core.config import get_settings
    from core.events import get_event_bus

    services = {}
    settings = get_settings()
    event_bus = get_event_bus()  # use the singleton so all modules share it
    services["event_bus"] = event_bus
    services["settings"] = settings

    logger = logging.getLogger("holex.init")
    logger.info("Initializing services...")

    # LLM Router
    try:
        from core.llm.router import LLMRouter
        router = LLMRouter(settings)
        # CRITICAL: Must call async initialize() to connect providers
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(router.initialize())
        finally:
            loop.close()
        if router.available_providers:
            services["llm_router"] = router
            logger.info(
                f"LLM Router ready - "
                f"providers: {router.available_providers}, "
                f"active: {router.current_provider}/{router.current_model}"
            )
        else:
            services["llm_router"] = router  # keep for later re-init
            logger.warning("LLM Router: no providers available (check API keys)")
    except Exception as e:
        logger.warning(f"LLM Router init failed: {e}")
        services["llm_router"] = None

    # Agent
    try:
        from core.agent.agent import HolexAgent
        if services.get("llm_router"):
            agent = HolexAgent(services["llm_router"])
            services["agent"] = agent
            logger.info(f"Agent initialized with {agent.tool_count} tools")
        else:
            services["agent"] = None
    except Exception as e:
        logger.warning(f"Agent init failed: {e}")
        services["agent"] = None

    # Storage (Firebase / SQLite)
    try:
        from services.firebase_service import LocalStorageService
        storage = LocalStorageService()
        services["storage_service"] = storage
        logger.info("Local storage initialized (SQLite)")

        # Try Firebase if credentials exist
        if settings.firebase.project_id:
            try:
                from services.firebase_service import FirebaseService
                fb = FirebaseService(settings)
                services["storage_service"] = fb
                logger.info("Firebase Firestore connected")
            except Exception as e:
                logger.info(f"Firebase not available, using local: {e}")
    except Exception as e:
        logger.warning(f"Storage init failed: {e}")
        services["storage_service"] = None

    # Conversation Manager
    try:
        from core.memory.conversation import ConversationManager
        cm = ConversationManager()
        services["conversation_manager"] = cm
        logger.info("Conversation manager ready")
    except Exception as e:
        logger.warning(f"ConversationManager init failed: {e}")
        services["conversation_manager"] = None

    # RAG Pipeline
    try:
        from core.rag.pipeline import RAGPipeline
        rag = RAGPipeline()
        if hasattr(rag, 'initialize'):
            try:
                rag.initialize()
            except Exception as e:
                logger.warning(f"RAG initialize call failed: {e}")
        services["rag_pipeline"] = rag
        logger.info("RAG pipeline ready (ChromaDB)")
    except Exception as e:
        logger.warning(f"RAG init failed: {e}")
        services["rag_pipeline"] = None

    # Voice (optional)
    if not args.no_voice:
        try:
            from core.voice.stt import SpeechToText
            stt = SpeechToText()
            if stt.initialize():
                services["stt"] = stt
                logger.info("Speech-to-Text ready (Vosk)")
            else:
                services["stt"] = None
                logger.warning("STT: Vosk model not found, voice input disabled")
        except Exception as e:
            logger.warning(f"STT init failed: {e}")
            services["stt"] = None

        try:
            from core.voice.tts import TextToSpeech
            tts = TextToSpeech()
            services["tts"] = tts
            logger.info("Text-to-Speech ready (Edge TTS)")
        except Exception as e:
            logger.warning(f"TTS init failed: {e}")
            services["tts"] = None

        try:
            from core.voice.wake_word import WakeWordDetector
            wake = WakeWordDetector()  # reads model path from settings
            services["wake_word"] = wake
            logger.info("Wake word detector ready ('Hey Holex')")
        except Exception as e:
            logger.warning(f"Wake word init failed: {e}")
            services["wake_word"] = None
    else:
        services["stt"] = None
        services["tts"] = None
        services["wake_word"] = None
        logger.info("Voice features disabled (--no-voice)")

    # Plugins
    try:
        from core.plugins.manager import PluginManager
        pm = PluginManager()
        if hasattr(pm, 'discover_plugins'):
            try:
                import asyncio as _aio
                _loop = _aio.new_event_loop()
                try:
                    _loop.run_until_complete(pm.discover_plugins())
                finally:
                    _loop.close()
            except Exception as e:
                logger.warning(f"Plugin discovery failed: {e}")
        services["plugin_manager"] = pm
        logger.info(f"Plugin manager ready ({pm.active_count} plugins loaded)")
    except Exception as e:
        logger.warning(f"PluginManager init failed: {e}")
        services["plugin_manager"] = None

    logger.info("All services initialized")
    return services


def main() -> None:
    args = parse_args()

    # Ensure dirs exist
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "temp").mkdir(exist_ok=True)
    (ROOT / "plugins").mkdir(exist_ok=True)

    setup_logging(args.debug)
    logger = logging.getLogger("holex.main")

    # PyQt5 Application
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

    # High-DPI support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Holex Beast")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("HolexBeast")

    # Apply theme
    from gui.styles import get_palette
    from gui.styles.stylesheet import generate_stylesheet

    palette = get_palette(args.theme)
    app.setStyleSheet(generate_stylesheet(palette))

    # Init services
    services = init_services(args)

    # Create main window
    from gui.app import HolexBeastApp

    window = HolexBeastApp()

    # Wire backend to GUI
    window.llm_router = services.get("llm_router")
    window.agent = services.get("agent")
    window.stt = services.get("stt")
    window.tts = services.get("tts")
    window.wake_word = services.get("wake_word")
    window.rag_pipeline = services.get("rag_pipeline")
    window.conversation_manager = services.get("conversation_manager")
    window.storage_service = services.get("storage_service")
    window.event_bus = services.get("event_bus")
    window._current_theme = args.theme

    # Reload model selector now that router is wired
    window._load_models()

    # Start wake word detection if available
    if services.get("wake_word"):
        try:
            services["wake_word"].start(
                on_wake=lambda: window._on_voice_toggle(True)
            )
            logger.info("Wake word listening: 'Hey Holex'")
        except Exception as e:
            logger.warning(f"Wake word start failed: {e}")

    window.show()
    logger.info(f"Holex Beast launched (theme: {args.theme})")

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
