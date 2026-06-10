from __future__ import annotations
from typing import Any, Callable


class EventBus:
    """Lightweight synchronous event bus for plugin communication.

    Plugins must not import each other directly — all cross-plugin
    communication goes through this bus via string event names.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., None]]] = {}

    def subscribe(self, event: str, handler: Callable[..., None]) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def unsubscribe(self, event: str, handler: Callable[..., None]) -> None:
        handlers = self._handlers.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event: str, **payload: Any) -> None:
        for handler in list(self._handlers.get(event, [])):
            handler(**payload)


# Module-level singleton used by all plugins and core modules.
bus = EventBus()
