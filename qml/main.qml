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

    // Active workbench URL — shared between sidebar and router
    property string activeWorkbenchUrl: ""

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Titlebar ───────────────────────────────────────────────────
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

        // ── Main area: Sidebar + Workbench ─────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // ── Sidebar ───────────────────────────────────────────────
            Rectangle {
                Layout.preferredWidth: 176
                Layout.fillHeight: true
                color: Theme.bgPanel
                // right border
                Rectangle {
                    anchors { top: parent.top; bottom: parent.bottom; right: parent.right }
                    width: 1
                    color: Theme.border
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingS
                    spacing: Theme.spacingXS

                    // Section label
                    Text {
                        text: "WORKBENCHES"
                        font.pixelSize: Theme.fontSizeXS
                        font.bold: true
                        color: Theme.textMuted
                        leftPadding: Theme.spacingS
                        topPadding: Theme.spacingS
                        bottomPadding: Theme.spacingXS
                        letterSpacing: 1
                    }

                    // Workbench nav buttons (dynamic)
                    Repeater {
                        model: workbenchModel
                        delegate: Rectangle {
                            Layout.fillWidth: true
                            height: 40
                            radius: Theme.radius
                            color: root.activeWorkbenchUrl === model.wbUrl
                                   ? "#2a2a4e"
                                   : "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacingM
                                anchors.rightMargin: Theme.spacingS
                                spacing: Theme.spacingS

                                // Active indicator strip
                                Rectangle {
                                    width: 3
                                    height: 20
                                    radius: 2
                                    color: root.activeWorkbenchUrl === model.wbUrl
                                           ? "#ce93d8"
                                           : "transparent"
                                }

                                Text {
                                    text: model.wbLabel
                                    font.pixelSize: Theme.fontSizeM
                                    color: root.activeWorkbenchUrl === model.wbUrl
                                           ? "#ce93d8"
                                           : Theme.textSecondary
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                onEntered: if (root.activeWorkbenchUrl !== model.wbUrl)
                                               parent.color = "#1e1e3a"
                                onExited:  parent.color = root.activeWorkbenchUrl === model.wbUrl
                                               ? "#2a2a4e" : "transparent"
                                onClicked: {
                                    root.activeWorkbenchUrl = model.wbUrl
                                    parent.color = "#2a2a4e"
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    // Plugin status at the bottom of the sidebar
                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: Theme.border
                    }
                    PluginStatusBar {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28
                    }
                }
            }

            // ── Workbench area ────────────────────────────────────────
            WorkbenchRouter {
                id: wbRouter
                objectName: "router"
                Layout.fillWidth: true
                Layout.fillHeight: true
                activeWorkbenchUrl: root.activeWorkbenchUrl
            }
        }
    }

    // Activate the first workbench once the model is ready
    Component.onCompleted: {
        if (workbenchModel.rowCount() > 0) {
            var idx = workbenchModel.index(0, 0)
            root.activeWorkbenchUrl = workbenchModel.data(idx, Qt.UserRole + 3)
        }
    }
}
