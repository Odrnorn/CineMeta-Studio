from __future__ import annotations
import json
from pathlib import Path
from typing import Any

try:
    from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Slot, Signal
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

    class QAbstractListModel:  # type: ignore[no-redef]
        def __init__(self, parent=None): pass
        def beginInsertRows(self, *a): pass
        def endInsertRows(self): pass

    class QModelIndex:  # type: ignore[no-redef]
        pass

    class Qt:  # type: ignore[no-redef]
        DisplayRole = 0
        UserRole = 256

    def Slot(*args, **kwargs):  # type: ignore[no-redef]
        def decorator(fn): return fn
        return decorator

    def Signal(*args, **kwargs):  # type: ignore[no-redef]
        return None


from cinemeta.domain.assets import AssetStatus, MediaAsset
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from cinemeta.plugin_interface import CineMetaWorkbench, ExportPlugin

_PLUGIN_DIR = Path(__file__).parent


class CatalogModel(QAbstractListModel):
    """QML list model for validated assets ready to export."""

    _ROLES = {
        Qt.UserRole + 1: b"assetId",
        Qt.UserRole + 2: b"fileName",
        Qt.UserRole + 3: b"title",
        Qt.UserRole + 4: b"year",
        Qt.UserRole + 5: b"ampelStatus",
        Qt.UserRole + 6: b"selected",    # bool — user-toggled checkbox
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

    def add_asset(self, asset: MediaAsset) -> None:
        # Avoid duplicates
        if any(item["assetId"] == asset.id for item in self._items):
            return
        self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
        self._items.append({
            "assetId":    asset.id,
            "fileName":   Path(asset.source_path).name,
            "title":      asset.hfv_data.get("title", "—"),
            "year":       asset.hfv_data.get("year", ""),
            "ampelStatus": asset.status.value,
            "selected":   True,
        })
        self.endInsertRows()

    @Slot(str, bool)
    def set_selected(self, asset_id: str, selected: bool) -> None:
        for i, item in enumerate(self._items):
            if item["assetId"] == asset_id:
                item["selected"] = selected
                break

    def selected_entries(self) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in item.items() if k != "selected"}
            for item in self._items
            if item.get("selected", True)
        ]

    def all_entries(self) -> list[dict[str, Any]]:
        return list(self._items)


class ExportWorkbenchDef(CineMetaWorkbench):
    @property
    def id(self) -> str:
        return "universal_export"

    @property
    def label(self) -> str:
        return "Export"

    @property
    def qml_component(self) -> str:
        return str(_PLUGIN_DIR / "qml" / "ExportWorkbench.qml")


class UniversalExportPlugin(ExportPlugin):
    """Stub universal-export plugin.

    Listens for ``asset.validated`` to keep the catalog model current.
    The ``export_to`` slot is called from QML; ``export()`` implements the
    ``ExportPlugin`` ABC and writes a JSON stub file — real format writers
    (HFV-1.0 XML, CSV, JSON-LD) will replace the stub body.
    """

    def __init__(self) -> None:
        self._db: Database | None = None
        self.catalog_model = CatalogModel()
        self._last_status: str = ""

    @property
    def name(self) -> str:
        return "universal_export"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def workbenches(self) -> list[CineMetaWorkbench]:
        return [ExportWorkbenchDef()]

    def initialize(self, db: Database | None = None) -> None:
        self._db = db
        # Pre-populate with already-validated assets
        if db is not None:
            for asset in db.all_assets():
                if asset.status == AssetStatus.VALIDATED:
                    self.catalog_model.add_asset(asset)
        bus.subscribe("asset.validated", self._on_asset_validated)

    def teardown(self) -> None:
        bus.unsubscribe("asset.validated", self._on_asset_validated)
        self._db = None

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    def _on_asset_validated(self, asset_id: str, **_: Any) -> None:
        if self._db is None:
            return
        asset = self._db.load_asset(asset_id)
        if asset is not None:
            self.catalog_model.add_asset(asset)

    # ------------------------------------------------------------------
    # ExportPlugin ABC
    # ------------------------------------------------------------------

    def export(self, catalog_entries: list[dict[str, Any]], output_path: str) -> None:
        """Stub export: writes entries as pretty-printed JSON.

        Real backend will interpret ``format_id`` and emit HFV-1.0 XML /
        CSV / JSON-LD.  The stub always writes JSON for UI development.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format":  "stub-json",
            "version": "0.1.0",
            "assets":  catalog_entries,
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # QML-callable slot
    # ------------------------------------------------------------------

    @Slot(str, str)
    def export_to(self, format_id: str, output_path: str) -> None:
        """Called from ExportWorkbench.qml Export button."""
        if not output_path:
            self._last_status = "Fehler: Kein Ausgabepfad angegeben."
            return

        entries = self.catalog_model.selected_entries()
        if not entries:
            self._last_status = "Fehler: Keine Assets ausgewählt."
            return

        try:
            self.export(entries, output_path)
            self._last_status = (
                f"✓ Exportiert: {output_path} ({len(entries)} Asset{'s' if len(entries) != 1 else ''})"
            )
            bus.publish(
                "export.completed",
                output_path=output_path,
                asset_count=len(entries),
                format_id=format_id,
            )
        except Exception as exc:  # noqa: BLE001
            self._last_status = f"Fehler: {exc}"

    @Slot(result=str)
    def last_status(self) -> str:
        return self._last_status
