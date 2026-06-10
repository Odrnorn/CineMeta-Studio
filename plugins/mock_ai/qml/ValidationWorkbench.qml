import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    ColumnLayout {
        anchors { fill: parent; margins: 16 }
        spacing: 12

        // Header
        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "Validation Workbench"
                color: "#e0e0e0"
                font.pixelSize: 18
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Text {
                text: validationList.count + " offen"
                color: "#888"
                font.pixelSize: 13
            }
        }

        // Queue list
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#0d0d1a"
            border.color: "#2a2a4a"
            radius: 4

            ListView {
                id: validationList
                anchors { fill: parent; margins: 6 }
                model: mockAiPlugin.validation_model
                spacing: 6
                clip: true

                delegate: Rectangle {
                    id: card
                    width: validationList.width
                    height: cardContent.implicitHeight + 20
                    color: "#13132a"
                    border.color: statusBorderColor()
                    border.width: 1
                    radius: 4

                    function statusBorderColor() {
                        switch (model.ampelStatus) {
                        case "GREEN":  return "#4caf50"
                        case "YELLOW": return "#ffeb3b"
                        case "RED":    return "#f44336"
                        default:       return "#333"
                        }
                    }

                    ColumnLayout {
                        id: cardContent
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                        spacing: 8

                        // File name + badge
                        RowLayout {
                            spacing: 8
                            Rectangle {
                                width: 12; height: 12; radius: 6
                                color: card.statusBorderColor()
                            }
                            Text {
                                text: model.fileName
                                color: "#e0e0e0"
                                font.pixelSize: 13
                                font.bold: true
                                Layout.fillWidth: true
                                elide: Text.ElideMiddle
                            }
                            Text {
                                text: model.ampelStatus
                                color: "#888"
                                font.pixelSize: 11
                            }
                        }

                        // GREEN — single best candidate + accept button
                        RowLayout {
                            visible: model.ampelStatus === "GREEN"
                            spacing: 10
                            Text {
                                text: model.bestLabel + "  " + Math.round(model.bestScore * 100) + "%"
                                color: "#ccc"
                                font.pixelSize: 12
                                Layout.fillWidth: true
                            }
                            Button {
                                text: "Akzeptieren ✓"
                                onClicked: mockAiPlugin.accept(model.assetId, model.bestLabel)
                            }
                        }

                        // YELLOW — radio buttons for each option
                        ColumnLayout {
                            visible: model.ampelStatus === "YELLOW"
                            spacing: 4

                            Repeater {
                                model: JSON.parse(card.ListView.view.model.data(
                                    card.ListView.view.model.index(index, 0),
                                    Qt.UserRole + 6) || "[]")

                                delegate: RadioButton {
                                    id: radioBtn
                                    text: modelData.label + "  " + Math.round(modelData.score * 100) + "%"
                                    contentItem: Text {
                                        text: radioBtn.text
                                        color: "#ccc"
                                        font.pixelSize: 12
                                        leftPadding: radioBtn.indicator.width + 6
                                    }
                                    ButtonGroup.group: yellowGroup
                                    property string candidateLabel: modelData.label
                                }
                            }

                            ButtonGroup { id: yellowGroup }

                            Button {
                                text: "Bestätigen"
                                enabled: yellowGroup.checkedButton !== null
                                onClicked: {
                                    if (yellowGroup.checkedButton)
                                        mockAiPlugin.accept(model.assetId, yellowGroup.checkedButton.candidateLabel)
                                }
                            }
                        }

                        // RED — free text input
                        ColumnLayout {
                            visible: model.ampelStatus === "RED"
                            spacing: 6

                            Text {
                                text: "Kein zuverlässiger Treffer (<50 %). Bitte Titel manuell eingeben:"
                                color: "#f44336"
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }

                            RowLayout {
                                spacing: 8
                                TextField {
                                    id: manualInput
                                    placeholderText: model.currentTitle || "Filmtitel …"
                                    color: "#e0e0e0"
                                    background: Rectangle { color: "#1a1a3a"; radius: 3 }
                                    Layout.fillWidth: true
                                }
                                Button {
                                    text: "Eingabe bestätigen"
                                    enabled: manualInput.text.trim().length > 0
                                    onClicked: mockAiPlugin.accept(model.assetId, manualInput.text.trim())
                                }
                            }
                        }

                        // Bottom spacer
                        Item { height: 2 }
                    }
                }

                // Empty state
                Text {
                    anchors.centerIn: parent
                    visible: validationList.count === 0
                    text: "Keine Assets zur Validierung.\nIngestiere Dateien über den Ingest-Workbench."
                    color: "#555"
                    font.pixelSize: 14
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }
}
