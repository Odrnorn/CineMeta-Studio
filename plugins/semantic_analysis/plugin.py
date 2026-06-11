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
        def beginResetModel(self): pass
        def endResetModel(self): pass

    class QModelIndex:  # type: ignore[no-redef]
        pass

    class Qt:  # type: ignore[no-redef]
        DisplayRole = 0
        UserRole = 256

    def Slot(*args, **kwargs):  # type: ignore[no-redef]
        def decorator(fn): return fn
        return decorator


from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from cinemeta.plugin_interface import CineMetaPlugin, CineMetaWorkbench

_PLUGIN_DIR = Path(__file__).parent


class SemanticAssetModel(QAbstractListModel):
    """QML list model exposing validated assets with their 2-D cluster position."""

    _ROLES = {
        Qt.UserRole + 1: b"assetId",
        Qt.UserRole + 2: b"title",
        Qt.UserRole + 3: b"clusterId",
        Qt.UserRole + 4: b"clusterLabel",
        Qt.UserRole + 5: b"clusterColor",
        Qt.UserRole + 6: b"posX",   # float 0-1
        Qt.UserRole + 7: b"posY",   # float 0-1
        Qt.UserRole + 8: b"neighbors",  # JSON string: [{assetId, title, score}]
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
        key = self._ROLES.get(role, b"").decode()
        return self._items[index.row()].get(key)

    def add_point(self, entry: dict[str, Any]) -> None:
        self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
        self._items.append(entry)
        self.endInsertRows()

    def all_items(self) -> list[dict[str, Any]]:
        return list(self._items)


class SemanticWorkbench(CineMetaWorkbench):
    @property
    def id(self) -> str:
        return "semantic_analysis"

    @property
    def label(self) -> str:
        return "Semantic Map"

    @property
    def qml_component(self) -> str:
        return str(_PLUGIN_DIR / "qml" / "SemanticMapWorkbench.qml")


class SemanticAnalysisPlugin(CineMetaPlugin):
    """Stub semantic-analysis plugin.

    Subscribes to ``asset.validated``, assigns each asset to one of three
    mock clusters and generates a deterministic 2-D position.  Publishes
    ``similarity.ready`` with the same payload structure the real embedding
    backend will produce.
    """

    def __init__(self) -> None:
        self._db: Database | None = None
        data_path = _PLUGIN_DIR / "mock_semantic_data.json"
        self._clusters: list[dict] = json.loads(
            data_path.read_text(encoding="utf-8")
        )["clusters"]
        self.asset_model = SemanticAssetModel()

    @property
    def name(self) -> str:
        return "semantic_analysis"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def workbenches(self) -> list[CineMetaWorkbench]:
        return [SemanticWorkbench()]

    def initialize(self, db: Database | None = None) -> None:
        self._db = db
        bus.subscribe("asset.validated", self._on_asset_validated)

    def teardown(self) -> None:
        bus.unsubscribe("asset.validated", self._on_asset_validated)
        self._db = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _stable_hash(text: str) -> int:
        """FNV-1a 32-bit hash — stable across processes (no PYTHONHASHSEED)."""
        h = 0x811C9DC5
        for ch in text.encode():
            h ^= ch
            h = (h * 0x01000193) & 0xFFFFFFFF
        return h

    def _compute_position(self, asset_id: str, cluster: dict) -> tuple[float, float]:
        """Place the asset near the cluster centre with a small deterministic offset."""
        h = self._stable_hash(asset_id)
        dx = ((h & 0xFF) - 128) / 1200        # ±0.10 spread
        h2 = self._stable_hash(asset_id + "y")
        dy = ((h2 & 0xFF) - 128) / 1200
        x = max(0.03, min(0.97, cluster["cx"] + dx))
        y = max(0.03, min(0.97, cluster["cy"] + dy))
        return x, y

    def _build_neighbors(self, asset_id: str, cluster_id: int) -> list[dict]:
        """Return up to 3 mock neighbours from the same cluster already in the model."""
        same_cluster = [
            item for item in self.asset_model.all_items()
            if item["clusterId"] == cluster_id and item["assetId"] != asset_id
        ]
        neighbors = []
        for item in same_cluster[:3]:
            h = self._stable_hash(asset_id + item["assetId"])
            score = round(0.70 + (h % 28) / 100.0, 2)  # 0.70–0.97
            neighbors.append({
                "assetId": item["assetId"],
                "title":   item["title"],
                "score":   score,
            })
        return neighbors

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    def _on_asset_validated(self, asset_id: str, chosen_label: str, **_: Any) -> None:
        cluster_idx = self._stable_hash(asset_id) % len(self._clusters)
        cluster = self._clusters[cluster_idx]
        x, y = self._compute_position(asset_id, cluster)
        neighbors = self._build_neighbors(asset_id, cluster["id"])

        # Persist semantic coordinates alongside HFV data
        if self._db is not None:
            asset = self._db.load_asset(asset_id)
            if asset is not None:
                asset.hfv_data["semantic"] = {
                    "cluster_id": cluster["id"],
                    "x": x,
                    "y": y,
                }
                self._db.save_asset(asset)

        entry: dict[str, Any] = {
            "assetId":      asset_id,
            "title":        chosen_label,
            "clusterId":    cluster["id"],
            "clusterLabel": cluster["label"],
            "clusterColor": cluster["color"],
            "posX":         x,
            "posY":         y,
            "neighbors":    json.dumps(neighbors),
        }
        self.asset_model.add_point(entry)

        bus.publish(
            "similarity.ready",
            asset_id=asset_id,
            cluster_id=cluster["id"],
            cluster_label=cluster["label"],
            x=x,
            y=y,
            neighbors=neighbors,
        )
