import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import "components"
import CineMeta 1.0

ApplicationWindow {
    id: root
    visible: true
    width: 1280
    height: 800
    title: "CineMeta Studio"
    Material.theme: Material.Dark
    Material.accent: Material.Purple

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Titlebar
        Rectangle {
            Layout.fillWidth: true
            height: 48
            color: Theme.bgApp

            Text {
                anchors.centerIn: parent
                text: "CineMeta Studio"
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeXL
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
            color: Theme.bgPanel

            PluginStatusBar {}
        }
    }
}
