import sys
from pathlib import Path

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


def main() -> None:
    app = QGuiApplication(sys.argv)

    db_path = Path.home() / ".cinemeta"
    db_path.mkdir(parents=True, exist_ok=True)
    db = Database(db_path / "catalog.sqlite")
    hierarchy = AssetHierarchy()

    registry = PluginRegistry()

    # local_ingest plugin
    ingest_plugin = LocalIngestPlugin()
    ingest_plugin.initialize(db=db, hierarchy=hierarchy)
    registry.register(ingest_plugin)
    registry.activate("local_ingest")

    # metadata_xmp plugin (no QML workbench — reacts to asset.created events)
    xmp_plugin = MetadataXmpPlugin()
    xmp_plugin.initialize(db=db)
    registry.register(xmp_plugin)
    registry.activate("metadata_xmp")

    # mock_ai plugin + validation workbench
    mock_ai = MockAiPlugin()
    mock_ai.initialize(db=db)
    registry.register(mock_ai)
    registry.activate("mock_ai")

    thumbnail_provider = ThumbnailImageProvider()

    engine = QQmlApplicationEngine()
    engine.addImageProvider("thumbnails", thumbnail_provider)
    engine.rootContext().setContextProperty("pluginRegistry", registry)
    engine.rootContext().setContextProperty("localIngestPlugin", ingest_plugin)
    engine.rootContext().setContextProperty("pluginModel", ingest_plugin.file_model)
    engine.rootContext().setContextProperty("mockAiPlugin", mock_ai)

    qml_path = Path(__file__).parent / "qml" / "main.qml"
    engine.load(str(qml_path))

    if not engine.rootObjects():
        db.close()
        sys.exit(1)

    # Default workbench: ValidationWorkbench (mock_ai)
    validation_qml = str(Path(__file__).parent / "plugins" / "mock_ai" / "qml" / "ValidationWorkbench.qml")
    root_obj = engine.rootObjects()[0]
    router_obj = root_obj.findChild(type(root_obj), "router")
    if router_obj is not None:
        router_obj.setProperty("activeWorkbenchUrl", validation_qml)

    # Wire thumbnail provider to ingest events so new assets get registered
    def _on_asset_created(asset_id: str, asset_type: str, **_) -> None:
        asset = db.load_asset(asset_id)
        if asset:
            thumbnail_provider.register_path(asset_id, asset.source_path)

    bus.subscribe("asset.created", _on_asset_created)

    # Activate the ingest workbench in the router
    root = engine.rootObjects()[0]
    router = root.findChild(type(root), "router") if root else None

    exit_code = app.exec()
    db.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
