"""Plugin discovery, lifecycle management, and event dispatch."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

from core.events import EventType, get_event_bus
from core.plugins.base import BasePlugin

logger = logging.getLogger(__name__)


class PluginManager:
    """Discovers, loads, and manages plugins."""

    def __init__(self):
        self.bus = get_event_bus()
        self._plugins: dict[str, BasePlugin] = {}
        self._active: set[str] = set()

    async def discover_plugins(self, plugins_dir: str = "plugins") -> list[str]:
        """Auto-discover plugins from a directory."""
        found = []
        plugins_path = Path(plugins_dir)
        if not plugins_path.exists():
            return found

        for path in plugins_path.glob("*.py"):
            if path.name.startswith("_"):
                continue
            try:
                module_name = f"plugins.{path.stem}"
                module = importlib.import_module(module_name)

                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BasePlugin)
                        and attr is not BasePlugin
                    ):
                        plugin = attr()
                        self._plugins[plugin.name] = plugin
                        found.append(plugin.name)
                        logger.info(f"Discovered plugin: {plugin.name}")

            except Exception as e:
                logger.error(f"Failed to load plugin from {path}: {e}")

        return found

    async def activate(self, plugin_name: str) -> bool:
        """Activate a plugin."""
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            logger.warning(f"Plugin not found: {plugin_name}")
            return False
        try:
            await plugin.activate(self.bus)
            self._active.add(plugin_name)
            self.bus.emit(EventType.PLUGIN_LOADED, {
                "name": plugin_name,
                "description": plugin.description,
            })
            logger.info(f"Activated plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"Plugin activation failed: {plugin_name}: {e}")
            self.bus.emit(EventType.PLUGIN_ERROR, {
                "name": plugin_name, "error": str(e),
            })
            return False

    async def deactivate(self, plugin_name: str) -> bool:
        """Deactivate a plugin."""
        plugin = self._plugins.get(plugin_name)
        if plugin and plugin_name in self._active:
            try:
                await plugin.deactivate()
                self._active.discard(plugin_name)
                return True
            except Exception as e:
                logger.error(f"Plugin deactivation error: {e}")
        return False

    async def activate_all(self) -> None:
        """Activate all discovered plugins."""
        for name in self._plugins:
            await self.activate(name)

    def get_tools(self) -> list:
        """Get all tools from active plugins."""
        tools = []
        for name in self._active:
            plugin = self._plugins.get(name)
            if plugin:
                tools.extend(plugin.get_tools())
        return tools

    def list_plugins(self) -> list[dict]:
        """List all plugins with their status."""
        return [
            {
                "name": p.name,
                "description": p.description,
                "version": p.version,
                "author": p.author,
                "active": p.name in self._active,
            }
            for p in self._plugins.values()
        ]

    @property
    def active_count(self) -> int:
        return len(self._active)
