from __future__ import annotations
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Slot

from cinemeta.domain.assets import AssetType, MediaAsset
from cinemeta.domain.hierarchy import AssetHierarchy
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from cinemeta.plugin_interface import CineMetaPlugin, CineMetaWorkbench

_EXT_MAP: dict[str, AssetType] = {
    ".jpg": AssetType.IMAGE, ".jpeg": AssetType.IMAGE,
    ".png": AssetType.IMAGE, ".tif":  AssetType.IMAGE, ".tiff": AssetType.IMAGE,
    ".txt": AssetType.TEXT,  ".pdf":  AssetType.TEXT,
    ".mp4": AssetType.VIDEO, ".mov":  AssetType.VIDEO, ".avi":  AssetType.VIDEO,
    ".mkv": AssetType.VIDEO, ".mxf":  AssetType.VIDEO,
}

_PLUGIN_DIR = Path(__file__).parent


def _asset_type(path: str) -> AssetType:
    return _EXT_MAP.get(Path(path).suffix.lower(), AssetType.TEXT)


class IngestWorkbench(CineMetaWorkbench):
    @property
    def id(self) -> str:
        return "ingest"

    @property
    def label(self) -> str:
        return "Ingest"

    @property
    def qml_component(self) -> str:
        return str(_PLUGIN_DIR / "qml" / "IngestWorkbench.qml")


class IngestFileModel(QAbstractListModel):
    """QML list model exposing ingested assets."""

    _ROLES = {
        Qt.UserRole + 1: b"assetId",
        Qt.UserRole + 2: b"filePath",
        Qt.UserRole + 3: b"fileName",
        Qt.UserRole + 4: b"assetType",
        Qt.UserRole + 5: b"thumbnailUrl",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLES

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        key = self._ROLES.get(role, b"").decode()
        return item.get(key)

    def append(self, asset: MediaAsset) -> None:
        self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
        self._items.append({
            "assetId":      asset.id,
            "filePath":     asset.source_path,
            "fileName":     Path(asset.source_path).name,
            "assetType":    asset.type.value,
            "thumbnailUrl": f"image://thumbnails/{asset.id}",
        })
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()


class LocalIngestPlugin(CineMetaPlugin):
    def __init__(self) -> None:
        self._db: Database | None = None
        self._hierarchy: AssetHierarchy | None = None
        self.file_model = IngestFileModel()
        self._workbenches = [IngestWorkbench()]

    @property
    def name(self) -> str:
        return "local_ingest"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def workbenches(self) -> list[CineMetaWorkbench]:
        return self._workbenches

    def initialize(self, db: Database | None = None, hierarchy: AssetHierarchy | None = None) -> None:
        self._db = db
        self._hierarchy = hierarchy or AssetHierarchy()

    def teardown(self) -> None:
        self._db = None
        self._hierarchy = None

    @Slot(str, result="QVariant")
    def list_files(self, folder_url: str) -> list[str]:
        """Return supported file paths inside *folder_url* (QML file URL or plain path)."""
        folder = Path(str(folder_url).replace("file:///", "").replace("file://", ""))
        if not folder.is_dir():
            return []
        return [
            str(p) for p in sorted(folder.iterdir())
            if p.is_file() and p.suffix.lower() in _EXT_MAP
        ]

    @Slot(str, result="QVariant")
    def ingest_file(self, path: str) -> dict[str, Any]:
        asset = MediaAsset(
            id=str(uuid.uuid4()),
            type=_asset_type(path),
            source_path=str(Path(path).resolve()),
        )
        if self._db is not None:
            self._db.save_asset(asset)
        if self._hierarchy is not None:
            self._hierarchy.add(asset)
        bus.publish("asset.created", asset_id=asset.id, asset_type=asset.type.value)
        self.file_model.append(asset)
        return {"asset_id": asset.id, "asset_type": asset.type.value}
