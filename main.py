import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from cinemeta.domain.hierarchy import AssetHierarchy
from cinemeta.event_bus import bus  # noqa: F401  — initialises singleton
from cinemeta.persistence import Database
from cinemeta.plugin_registry import PluginRegistry
from plugins.local_ingest.lo_fi_renderer import ThumbnailImageProvider
from plugins.local_ingest.plugin import LocalIngestPlugin
from plugins.metadata_xmp.plugin import MetadataXmpPlugin
from plugins.mock_ai.plugin import MockAiPlugin
from plugins.semantic_analysis.plugin import SemanticAnalysisPlugin
from plugins.universal_export.plugin import UniversalExportPlugin
from plugins.video_analysis.plugin import VideoAnalysisPlugin


# ---------------------------------------------------------------------------
# WorkbenchListModel — exposes registered workbenches to QML sidebar
# ---------------------------------------------------------------------------

class WorkbenchListModel(QAbstractListModel):
    """Static model populated once from all active plugins' workbenches."""

    _ROLES = {
        Qt.UserRole + 1: b"wbId",
        Qt.UserRole + 2: b"wbLabel",
        Qt.UserRole + 3: b"wbUrl",   # QUrl.fromLocalFile(...).toString()
    }

    def __init__(self, entries: list[dict[str, Any]]) -> None:
        super().__init__()
        self._items = entries

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLES

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._items):
            return None
        key = self._ROLES.get(role, b"").decode()
        return self._items[index.row()].get(key)


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------

def main() -> None:
    _conf = Path(__file__).parent / "qtquickcontrols2.conf"
    os.environ.setdefault("QT_QUICK_CONTROLS_CONF", str(_conf))

    app = QGuiApplication(sys.argv)

    db_path = Path.home() / ".cinemeta"
    db_path.mkdir(parents=True, exist_ok=True)
    db = Database(db_path / "catalog.sqlite")
    hierarchy = AssetHierarchy()

    registry = PluginRegistry()

    # Register and activate all plugins — in sidebar display order.
    # activate() calls initialize() exactly once with the right kwargs.

    ingest_plugin = LocalIngestPlugin()
    registry.register(ingest_plugin)
    registry.activate("local_ingest", db=db, hierarchy=hierarchy)

    xmp_plugin = MetadataXmpPlugin()
    registry.register(xmp_plugin)
    registry.activate("metadata_xmp", db=db)

    mock_ai = MockAiPlugin()
    registry.register(mock_ai)
    registry.activate("mock_ai", db=db)

    video_plugin = VideoAnalysisPlugin()
    registry.register(video_plugin)
    registry.activate("video_analysis", db=db, hierarchy=hierarchy)

    semantic_plugin = SemanticAnalysisPlugin()
    registry.register(semantic_plugin)
    registry.activate("semantic_analysis", db=db)

    export_plugin = UniversalExportPlugin()
    registry.register(export_plugin)
    registry.activate("universal_export", db=db)

    # Build workbench list model from all active plugins (in activation order)
    entries: list[dict[str, Any]] = []
    for plugin in registry.active_plugins:
        for wb in plugin.workbenches:
            url = QUrl.fromLocalFile(wb.qml_component).toString()
            entries.append({"wbId": wb.id, "wbLabel": wb.label, "wbUrl": url})
    wb_model = WorkbenchListModel(entries)

    thumbnail_provider = ThumbnailImageProvider()

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(Path(__file__).parent / "qml"))
    engine.addImageProvider("thumbnails", thumbnail_provider)
    engine.rootContext().setContextProperty("pluginRegistry", registry)
    engine.rootContext().setContextProperty("localIngestPlugin", ingest_plugin)
    engine.rootContext().setContextProperty("pluginModel", ingest_plugin.file_model)
    engine.rootContext().setContextProperty("mockAiPlugin", mock_ai)
    engine.rootContext().setContextProperty("semanticPlugin", semantic_plugin)
    engine.rootContext().setContextProperty("exportPlugin", export_plugin)
    engine.rootContext().setContextProperty("workbenchModel", wb_model)

    qml_path = Path(__file__).parent / "qml" / "main.qml"
    engine.load(str(qml_path))

    if not engine.rootObjects():
        db.close()
        sys.exit(1)

    # Wire thumbnail provider to ingest events so new assets get registered
    def _on_asset_created(asset_id: str, asset_type: str, **_: Any) -> None:
        asset = db.load_asset(asset_id)
        if asset:
            thumbnail_provider.register_path(asset_id, asset.source_path)

    bus.subscribe("asset.created", _on_asset_created)

    exit_code = app.exec()
    db.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
