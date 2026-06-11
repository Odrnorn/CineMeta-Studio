import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import CineMeta 1.0

Item {
    id: root

    property string formatId:    "json-ld"
    property string outputPath:  ""
    property string statusText:  ""
    property bool   statusOk:    false

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingL
        spacing: Theme.spacingL

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            spacing: Theme.spacingM
            Text {
                text: "Export"
                font.pixelSize: Theme.fontSizeXL
                font.bold: true
                color: Theme.textPrimary
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                radius: Theme.radiusBadge
                color: Theme.bgCard
                border.color: Theme.border
                padding: 6
                Text {
                    anchors.centerIn: parent
                    text: exportPlugin.catalog_model.rowCount() + " Assets validiert"
                    font.pixelSize: Theme.fontSizeS
                    color: Theme.textSecondary
                    leftPadding: Theme.spacingS
                    rightPadding: Theme.spacingS
                }
            }
        }

        Rectangle { height: 1; Layout.fillWidth: true; color: Theme.border }

        // ── Format selection ────────────────────────────────────────
        RowLayout {
            spacing: Theme.spacingXL
            Text {
                text: "Format:"
                font.pixelSize: Theme.fontSizeM
                color: Theme.textSecondary
                Layout.alignment: Qt.AlignVCenter
            }
            Repeater {
                model: ListModel {
                    ListElement { fmtId: "hfv-xml";  fmtLabel: "HFV-1.0 XML" }
                    ListElement { fmtId: "csv";       fmtLabel: "CSV"         }
                    ListElement { fmtId: "json-ld";   fmtLabel: "JSON-LD"     }
                }
                delegate: RadioButton {
                    text: model.fmtLabel
                    checked: root.formatId === model.fmtId
                    font.pixelSize: Theme.fontSizeM
                    Material.accent: Material.Purple
                    onCheckedChanged: if (checked) root.formatId = model.fmtId
                }
            }
        }

        // ── Output path ─────────────────────────────────────────────
        RowLayout {
            spacing: Theme.spacingM
            Text {
                text: "Ausgabepfad:"
                font.pixelSize: Theme.fontSizeM
                color: Theme.textSecondary
                Layout.alignment: Qt.AlignVCenter
            }
            Rectangle {
                Layout.fillWidth: true
                height: 34
                color: Theme.bgInput
                radius: Theme.radius
                border.color: Theme.border

                TextInput {
                    id: pathInput
                    anchors.fill: parent
                    anchors.margins: Theme.spacingS
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeM
                    clip: true
                    onTextChanged: root.outputPath = text
                    placeholderText: "z.B. C:/Exporte/katalog.json"

                    // QML does not have a native property called placeholderText
                    // on TextInput — use a Label behind it instead
                    Text {
                        visible: parent.text.length === 0
                        text: "z.B. C:/Exporte/katalog.json"
                        color: Theme.textMuted
                        font.pixelSize: parent.font.pixelSize
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }

        // ── Asset list ──────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgContainer
            radius: Theme.radius
            border.color: Theme.border
            clip: true

            ListView {
                id: assetList
                anchors.fill: parent
                anchors.margins: Theme.spacingS
                model: exportPlugin.catalog_model
                clip: true

                // Empty state
                Text {
                    visible: exportPlugin.catalog_model.rowCount() === 0
                    anchors.centerIn: parent
                    text: "Noch keine validierten Assets —\nbitte zuerst in der Validierungs-Workbench validieren."
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSizeM
                    horizontalAlignment: Text.AlignHCenter
                }

                delegate: Rectangle {
                    width: assetList.width
                    height: 42
                    color: index % 2 === 0 ? Theme.bgCard : Theme.bgContainer
                    radius: Theme.radius

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingS
                        spacing: Theme.spacingM

                        CheckBox {
                            checked: model.selected
                            Material.accent: Material.Purple
                            onCheckedChanged: exportPlugin.catalog_model.set_selected(model.assetId, checked)
                        }

                        Text {
                            text: model.title || model.fileName || "—"
                            font.pixelSize: Theme.fontSizeM
                            color: Theme.textPrimary
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Text {
                            text: model.year || ""
                            font.pixelSize: Theme.fontSizeS
                            color: Theme.textMuted
                            Layout.preferredWidth: 40
                        }

                        // Ampel badge
                        Rectangle {
                            width: 10; height: 10; radius: 5
                            Layout.alignment: Qt.AlignVCenter
                            color: {
                                var s = model.ampelStatus
                                if (s === "GREEN")   return Theme.colorGreen
                                if (s === "YELLOW")  return Theme.colorYellow
                                if (s === "RED")     return Theme.colorRed
                                return Theme.colorPending
                            }
                        }
                        Text {
                            text: model.ampelStatus || "—"
                            font.pixelSize: Theme.fontSizeS
                            color: Theme.textMuted
                            Layout.preferredWidth: 70
                        }
                    }
                }
            }
        }

        // ── Bottom bar: select-all + export button ──────────────────
        RowLayout {
            spacing: Theme.spacingM

            Button {
                text: "Alle auswählen"
                font.pixelSize: Theme.fontSizeS
                Material.background: Theme.bgPanel
                onClicked: {
                    var count = exportPlugin.catalog_model.rowCount()
                    for (var i = 0; i < count; i++) {
                        var idx = exportPlugin.catalog_model.index(i, 0)
                        var aid = exportPlugin.catalog_model.data(idx, Qt.UserRole + 1)
                        exportPlugin.catalog_model.set_selected(aid, true)
                    }
                }
            }

            Item { Layout.fillWidth: true }

            Button {
                id: exportBtn
                text: "Exportieren"
                font.pixelSize: Theme.fontSizeM
                enabled: root.outputPath.length > 0 && exportPlugin.catalog_model.rowCount() > 0
                Material.background: Material.Purple
                onClicked: {
                    exportPlugin.export_to(root.formatId, root.outputPath)
                    root.statusText = exportPlugin.last_status()
                    root.statusOk = root.statusText.startsWith("✓")
                }
            }
        }

        // ── Status line ─────────────────────────────────────────────
        Text {
            visible: root.statusText.length > 0
            text: root.statusText
            font.pixelSize: Theme.fontSizeS
            color: root.statusOk ? Theme.colorGreen : Theme.colorRed
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
}
