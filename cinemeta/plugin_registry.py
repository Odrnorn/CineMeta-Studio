from __future__ import annotations
from typing import Any
from .plugin_interface import CineMetaPlugin


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, CineMetaPlugin] = {}
        self._active: list[str] = []   # ordered; preserves activation sequence

    def register(self, plugin: CineMetaPlugin) -> None:
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.name}' is already registered.")
        self._plugins[plugin.name] = plugin

    def activate(self, name: str, **init_kwargs: Any) -> None:
        """Activate a plugin by calling its initialize() with optional kwargs."""
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' is not registered.")
        if name not in self._active:
            self._plugins[name].initialize(**init_kwargs)
            self._active.append(name)

    def deactivate(self, name: str) -> None:
        if name in self._active:
            self._plugins[name].teardown()
            self._active.remove(name)

    def get(self, name: str) -> CineMetaPlugin | None:
        return self._plugins.get(name)

    @property
    def active_plugins(self) -> list[CineMetaPlugin]:
        """All currently-active plugins in activation order."""
        return [self._plugins[n] for n in self._active if n in self._plugins]

    @property
    def all_plugins(self) -> list[CineMetaPlugin]:
        return list(self._plugins.values())
