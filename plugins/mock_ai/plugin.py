from __future__ import annotations
import json
from pathlib import Path
from typing import Any

try:
    from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Slot
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    class QAbstractListModel:  # type: ignore[no-redef]
        def __init__(self, parent=None): pass
        def beginInsertRows(self, *a): pass
        def endInsertRows(self): pass
        def beginRemoveRows(self, *a): pass
        def endRemoveRows(self): pass
    class QModelIndex:  # type: ignore[no-redef]
        pass
    class Qt:  # type: ignore[no-redef]
        DisplayRole = 0
        UserRole = 256
    def Slot(*args, **kwargs):  # type: ignore[no-redef]
        def decorator(fn): return fn
        return decorator

from cinemeta.domain.assets import AssetStatus, MediaAsset
from cinemeta.domain.confidence_logic import AmpelStatus, ConfidenceResult, classify
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from cinemeta.plugin_interface import AIModelPlugin, CineMetaWorkbench

_PLUGIN_DIR = Path(__file__).parent


class ValidationQueueModel(QAbstractListModel):
    """QML list model for assets awaiting human validation."""

    _ROLES = {
        Qt.UserRole + 1: b"assetId",
        Qt.UserRole + 2: b"fileName",
        Qt.UserRole + 3: b"ampelStatus",
        Qt.UserRole + 4: b"bestLabel",
        Qt.UserRole + 5: b"bestScore",
        Qt.UserRole + 6: b"allOptions",
        Qt.UserRole + 7: b"currentTitle",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[dict[str, Any]] = []
        self._db: Database | None = None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLES

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._items):
            return None
        key = self._ROLES.get(role, b"").decode()
        return self._items[index.row()].get(key)

    def enqueue(self, asset_id: str, result: ConfidenceResult, hfv_data: dict[str, Any]) -> None:
        file_name = ""
        if self._db:
            asset = self._db.load_asset(asset_id)
            if asset:
                file_name = Path(asset.source_path).name

        self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
        self._items.append({
            "assetId":      asset_id,
            "fileName":     file_name,
            "ampelStatus":  result.status.value,
            "bestLabel":    result.best["label"] if result.best else "",
            "bestScore":    round(result.best["score"], 3) if result.best else 0.0,
            "allOptions":   json.dumps(result.all_options),
            "currentTitle": hfv_data.get("title", ""),
        })
        self.endInsertRows()

    def _index_of(self, asset_id: str) -> int:
        for i, item in enumerate(self._items):
            if item["assetId"] == asset_id:
                return i
        return -1

    @Slot(str)
    def remove(self, asset_id: str) -> None:
        idx = self._index_of(asset_id)
        if idx == -1:
            return
        self.beginRemoveRows(QModelIndex(), idx, idx)
        self._items.pop(idx)
        self.endRemoveRows()


class MockAiPlugin(AIModelPlugin):
    def __init__(self) -> None:
        self._db: Database | None = None
        self._scenarios: list[dict[str, Any]] = []
        self.validation_model = ValidationQueueModel()

    @property
    def name(self) -> str:
        return "mock_ai"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def workbenches(self) -> list[CineMetaWorkbench]:
        return []

    def initialize(self, db: Database | None = None) -> None:
        self._db = db
        self.validation_model._db = db
        data = json.loads((_PLUGIN_DIR / "mock_data.json").read_text(encoding="utf-8"))
        self._scenarios = data["scenarios"]
        bus.subscribe("xmp.extracted", self._on_xmp_extracted)

    def teardown(self) -> None:
        bus.unsubscribe("xmp.extracted", self._on_xmp_extracted)
        self._db = None

    def analyze_asset(self, asset_id: str, xmp_data: dict[str, Any]) -> list[dict[str, Any]]:
        scenario = self._scenarios[hash(asset_id) % len(self._scenarios)]
        return list(scenario["candidates"])

    def _on_xmp_extracted(self, asset_id: str, hfv_data: dict[str, Any], **_: Any) -> None:
        if self._db is None:
            return

        candidates = self.analyze_asset(asset_id, hfv_data)
        result = classify(candidates)

        asset = self._db.load_asset(asset_id)
        if asset is not None:
            asset.status = AssetStatus[result.status.value]
            self._db.save_asset(asset)

        self.validation_model.enqueue(asset_id, result, hfv_data)
        bus.publish(
            "confidence.ready",
            asset_id=asset_id,
            status=result.status.value,
            best=result.best,
            all_options=result.all_options,
            distance=result.distance,
        )

    @Slot(str, str)
    def accept(self, asset_id: str, chosen_label: str) -> None:
        if self._db is None:
            return
        asset = self._db.load_asset(asset_id)
        if asset is not None:
            asset.status = AssetStatus.VALIDATED
            asset.hfv_data["title"] = chosen_label
            self._db.save_asset(asset)
        self.validation_model.remove(asset_id)
        bus.publish("asset.validated", asset_id=asset_id, chosen_label=chosen_label)
