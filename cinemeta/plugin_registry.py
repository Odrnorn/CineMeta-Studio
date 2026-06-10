from __future__ import annotations
from .plugin_interface import CineMetaPlugin


class PluginRegistry:
    def __init__(self) -> None:
        self._registered: dict[str, CineMetaPlugin] = {}
        self._active: set[str] = set()

    def register(self, plugin: CineMetaPlugin) -> None:
        if plugin.name in self._registered:
            raise ValueError(f"Plugin '{plugin.name}' is already registered.")
        self._registered[plugin.name] = plugin

    def activate(self, name: str) -> None:
        if name not in self._registered:
            raise KeyError(f"Plugin '{name}' is not registered.")
        if name not in self._active:
            self._registered[name].initialize()
            self._active.add(name)

    def deactivate(self, name: str) -> None:
        if name in self._active:
            self._registered[name].teardown()
            self._active.discard(name)

    def get(self, name: str) -> CineMetaPlugin | None:
        return self._registered.get(name)

    @property
    def active_plugins(self) -> list[CineMetaPlugin]:
        return [self._registered[n] for n in self._active]

    @property
    def all_plugins(self) -> list[CineMetaPlugin]:
        return list(self._registered.values())
