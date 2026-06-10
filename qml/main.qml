import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

ApplicationWindow {
    id: root
    visible: true
    width: 1280
    height: 800
    title: "CineMeta Studio"

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Titlebar / toolbar
        Rectangle {
            Layout.fillWidth: true
            height: 48
            color: "#1a1a2e"

            Text {
                anchors.centerIn: parent
                text: "CineMeta Studio"
                color: "#e0e0e0"
                font.pixelSize: 18
                font.bold: true
            }
        }

        // Main workbench area
        WorkbenchRouter {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        // Plugin status bar
        Rectangle {
            Layout.fillWidth: true
            height: 28
            color: "#16213e"

            PluginStatusBar {}
        }
    }
}
