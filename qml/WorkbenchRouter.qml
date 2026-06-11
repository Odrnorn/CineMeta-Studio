import QtQuick
import QtQuick.Controls
import CineMeta 1.0

Item {
    id: router
    objectName: "router"

    // Filled by PluginRegistry bridge when a plugin activates a workbench.
    property string activeWorkbenchUrl: ""

    Loader {
        id: workbenchLoader
        anchors.fill: parent
        source: router.activeWorkbenchUrl
    }

    // Empty state shown when no plugin is active
    Column {
        anchors.centerIn: parent
        spacing: Theme.spacingL
        visible: router.activeWorkbenchUrl === "" && workbenchLoader.status !== Loader.Ready

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Kein Workbench aktiv"
            color: Theme.textSecondary
            font.pixelSize: 22
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Aktiviere ein Plugin über den Plugin-Manager."
            color: Theme.textMuted
            font.pixelSize: Theme.fontSizeL
        }
    }
}
