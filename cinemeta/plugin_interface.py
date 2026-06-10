from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class CineMetaWorkbench(ABC):
    @property
    @abstractmethod
    def id(self) -> str: ...

    @property
    @abstractmethod
    def label(self) -> str: ...

    @property
    @abstractmethod
    def qml_component(self) -> str:
        """Path or URL of the QML component file for this workbench."""
        ...


class CineMetaPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @property
    def workbenches(self) -> list[CineMetaWorkbench]:
        return []

    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def teardown(self) -> None: ...


class AIModelPlugin(CineMetaPlugin):
    @abstractmethod
    def analyze_asset(self, asset_id: str, xmp_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Return list of {label, score} dicts, sorted descending by score."""
        ...

    def analyze_frames(self, asset_id: str, frame_paths: list[str]) -> list[dict[str, Any]]:
        return []


class ExportPlugin(CineMetaPlugin):
    @abstractmethod
    def export(self, catalog_entries: list[dict[str, Any]], output_path: str) -> None: ...
