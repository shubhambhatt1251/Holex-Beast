"""Base classes and ABC for the plugin system."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.events import EventBus


class BasePlugin(ABC):
    """
    Base class for all Holex Beast plugins.

    Plugins can:
    - Register new tools for the agent
    - Subscribe to events
    - Add GUI elements
    - Extend configuration
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """What this plugin does."""
        ...

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def author(self) -> str:
        return "Holex Beast"

    @abstractmethod
    async def activate(self, bus: EventBus) -> None:
        """Called when plugin is activated. Register event handlers here."""
        ...

    async def deactivate(self) -> None:
        """Called when plugin is deactivated. Cleanup here."""
        pass

    def get_tools(self) -> list:
        """Return any tools this plugin provides."""
        return []

    def get_config_schema(self) -> dict:
        """Return JSON schema for plugin configuration."""
        return {}

    def __repr__(self) -> str:
        return f"Plugin({self.name} v{self.version})"
