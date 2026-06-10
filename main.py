import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from cinemeta.plugin_registry import PluginRegistry
from cinemeta.event_bus import bus  # noqa: F401  — initialises singleton
from cinemeta.persistence import Database


def main() -> None:
    app = QGuiApplication(sys.argv)

    registry = PluginRegistry()
    db = Database(Path.home() / ".cinemeta" / "catalog.sqlite")

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("pluginRegistry", registry)

    qml_path = Path(__file__).parent / "qml" / "main.qml"
    engine.load(str(qml_path))

    if not engine.rootObjects():
        db.close()
        sys.exit(1)

    exit_code = app.exec()
    db.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
