import QtQuick
import QtQuick.Controls

Item {
    id: router

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
        spacing: 16
        visible: router.activeWorkbenchUrl === "" && workbenchLoader.status !== Loader.Ready

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Kein Workbench aktiv"
            color: "#888"
            font.pixelSize: 22
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Aktiviere ein Plugin über den Plugin-Manager."
            color: "#555"
            font.pixelSize: 14
        }
    }
}
