import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import CineMeta 1.0

Item {
    id: root

    // ------------------------------------------------------------------
    // State
    // ------------------------------------------------------------------
    property int    selectedRow:   -1
    property string selectedId:    ""
    property string selectedTitle: ""
    property string selectedCluster: ""
    property var    selectedNeighbors: []

    // ------------------------------------------------------------------
    // Layout: canvas area (left) + detail panel (right)
    // ------------------------------------------------------------------
    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingL
        spacing: Theme.spacingL

        // ── Left: header + canvas ────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spacingM

            // Header row
            RowLayout {
                spacing: Theme.spacingM
                Text {
                    text: "Semantic Map"
                    font.pixelSize: Theme.fontSizeXL
                    font.bold: true
                    color: Theme.textPrimary
                }
                Item { Layout.fillWidth: true }
                Text {
                    visible: semanticPlugin.asset_model.rowCount() === 0
                    text: "Noch keine validierten Assets"
                    font.pixelSize: Theme.fontSizeS
                    color: Theme.textMuted
                }
                Button {
                    visible: root.selectedRow >= 0
                    text: "Auswahl aufheben"
                    font.pixelSize: Theme.fontSizeS
                    Material.background: Theme.bgPanel
                    onClicked: {
                        root.selectedRow = -1
                        root.selectedId = ""
                        root.selectedTitle = ""
                        root.selectedCluster = ""
                        root.selectedNeighbors = []
                        mapCanvas.requestPaint()
                    }
                }
            }

            // Canvas plot
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Theme.bgContainer
                radius: Theme.radius
                border.color: Theme.border
                clip: true

                Canvas {
                    id: mapCanvas
                    anchors.fill: parent
                    anchors.margins: Theme.spacingM

                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)

                        var count = semanticPlugin.asset_model.rowCount()
                        var UserRole = 0x0100  // Qt.UserRole = 256
                        for (var i = 0; i < count; i++) {
                            var idx = semanticPlugin.asset_model.index(i, 0)
                            var px = semanticPlugin.asset_model.data(idx, UserRole + 6) * width
                            var py = semanticPlugin.asset_model.data(idx, UserRole + 7) * height
                            var col = semanticPlugin.asset_model.data(idx, UserRole + 5)
                            var isSelected = (i === root.selectedRow)

                            ctx.beginPath()
                            ctx.arc(px, py, isSelected ? 10 : 7, 0, 2 * Math.PI)
                            ctx.fillStyle = col
                            ctx.globalAlpha = isSelected ? 1.0 : 0.75
                            ctx.fill()
                            if (isSelected) {
                                ctx.strokeStyle = "#ffffff"
                                ctx.lineWidth = 2
                                ctx.stroke()
                            }
                            ctx.globalAlpha = 1.0
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: function(mouse) {
                            var count = semanticPlugin.asset_model.rowCount()
                            var UserRole = 0x0100
                            var hit = -1
                            var bestDist = 999
                            for (var i = 0; i < count; i++) {
                                var idx = semanticPlugin.asset_model.index(i, 0)
                                var px = semanticPlugin.asset_model.data(idx, UserRole + 6) * mapCanvas.width
                                var py = semanticPlugin.asset_model.data(idx, UserRole + 7) * mapCanvas.height
                                var dist = Math.sqrt((mouse.x - px) * (mouse.x - px) + (mouse.y - py) * (mouse.y - py))
                                if (dist < bestDist && dist < 16) {
                                    bestDist = dist
                                    hit = i
                                }
                            }
                            if (hit >= 0) {
                                root.selectedRow = hit
                                var hitIdx = semanticPlugin.asset_model.index(hit, 0)
                                root.selectedId      = semanticPlugin.asset_model.data(hitIdx, UserRole + 1)
                                root.selectedTitle   = semanticPlugin.asset_model.data(hitIdx, UserRole + 2)
                                root.selectedCluster = semanticPlugin.asset_model.data(hitIdx, UserRole + 4)
                                var neighborJson     = semanticPlugin.asset_model.data(hitIdx, UserRole + 8)
                                root.selectedNeighbors = JSON.parse(neighborJson || "[]")
                            } else {
                                root.selectedRow = -1
                                root.selectedId = ""
                                root.selectedTitle = ""
                                root.selectedCluster = ""
                                root.selectedNeighbors = []
                            }
                            mapCanvas.requestPaint()
                        }
                    }
                }

                // Empty-state overlay
                Column {
                    anchors.centerIn: parent
                    spacing: Theme.spacingS
                    visible: semanticPlugin.asset_model.rowCount() === 0

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "🗺"
                        font.pixelSize: 48
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Karte füllt sich nach der Validierung"
                        font.pixelSize: Theme.fontSizeM
                        color: Theme.textMuted
                    }
                }
            }

            // Cluster legend
            RowLayout {
                spacing: Theme.spacingXL
                Repeater {
                    model: ListModel {
                        ListElement { clusterColor: "#7b2ff7"; clusterName: "Stummfilm Drama" }
                        ListElement { clusterColor: "#2196f3"; clusterName: "Komödie"         }
                        ListElement { clusterColor: "#4caf50"; clusterName: "Dokumentation"   }
                    }
                    delegate: RowLayout {
                        spacing: Theme.spacingS
                        Rectangle {
                            width: 10; height: 10; radius: 5
                            color: model.clusterColor
                        }
                        Text {
                            text: model.clusterName
                            font.pixelSize: Theme.fontSizeS
                            color: Theme.textSecondary
                        }
                    }
                }
            }
        }

        // ── Right: detail panel ──────────────────────────────────────
        Rectangle {
            Layout.preferredWidth: 220
            Layout.fillHeight: true
            color: Theme.bgPanel
            radius: Theme.radius
            border.color: Theme.border

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacingM
                spacing: Theme.spacingM

                Text {
                    text: "Auswahl"
                    font.pixelSize: Theme.fontSizeL
                    font.bold: true
                    color: Theme.textPrimary
                }

                Rectangle { height: 1; Layout.fillWidth: true; color: Theme.border }

                // No selection state
                ColumnLayout {
                    visible: root.selectedRow < 0
                    spacing: Theme.spacingS
                    Text {
                        text: "Klicken Sie auf einen\nPunkt im Cluster-Plot"
                        font.pixelSize: Theme.fontSizeS
                        color: Theme.textMuted
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                // Selection info
                ColumnLayout {
                    visible: root.selectedRow >= 0
                    spacing: Theme.spacingS
                    Layout.fillWidth: true

                    Text {
                        text: root.selectedTitle
                        font.pixelSize: Theme.fontSizeM
                        font.bold: true
                        color: Theme.textPrimary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    RowLayout {
                        spacing: Theme.spacingXS
                        Text {
                            text: "Cluster:"
                            font.pixelSize: Theme.fontSizeS
                            color: Theme.textMuted
                        }
                        Text {
                            text: root.selectedCluster
                            font.pixelSize: Theme.fontSizeS
                            color: Theme.textSecondary
                        }
                    }

                    Rectangle { height: 1; Layout.fillWidth: true; color: Theme.border }

                    Text {
                        visible: root.selectedNeighbors.length > 0
                        text: "Ähnliche Assets:"
                        font.pixelSize: Theme.fontSizeS
                        font.bold: true
                        color: Theme.textSecondary
                    }

                    Repeater {
                        model: root.selectedNeighbors
                        delegate: RowLayout {
                            spacing: Theme.spacingS
                            Layout.fillWidth: true
                            Text {
                                text: modelData.title || "(unbekannt)"
                                font.pixelSize: Theme.fontSizeS
                                color: Theme.textPrimary
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                text: Math.round((modelData.score || 0) * 100) + "%"
                                font.pixelSize: Theme.fontSizeS
                                color: Theme.colorGreen
                            }
                        }
                    }

                    Text {
                        visible: root.selectedNeighbors.length === 0 && root.selectedRow >= 0
                        text: "Noch keine Nachbarn —\nweitere Assets validieren"
                        font.pixelSize: Theme.fontSizeS
                        color: Theme.textMuted
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }
    }

    // Repaint canvas whenever the model changes
    Connections {
        target: semanticPlugin.asset_model
        function onRowsInserted() { mapCanvas.requestPaint() }
    }
}
