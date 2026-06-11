import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CineMeta 1.0

Item {
    id: root

    ColumnLayout {
        anchors { fill: parent; margins: Theme.spacingL }
        spacing: Theme.spacingM

        // Header
        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "Validation Workbench"
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeXL
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Text {
                text: validationList.count + " offen"
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeM
            }
        }

        // Queue list
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgContainer
            border.color: Theme.border
            radius: Theme.radius

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
                    color: Theme.bgCard
                    border.color: statusBorderColor()
                    border.width: 1
                    radius: Theme.radius

                    function statusBorderColor() {
                        switch (model.ampelStatus) {
                        case "GREEN":  return Theme.colorGreen
                        case "YELLOW": return Theme.colorYellow
                        case "RED":    return Theme.colorRed
                        default:       return Theme.border
                        }
                    }

                    ColumnLayout {
                        id: cardContent
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                        spacing: Theme.spacingS

                        // File name + badge
                        RowLayout {
                            spacing: Theme.spacingS
                            Rectangle {
                                width: 12; height: 12; radius: 6
                                color: card.statusBorderColor()
                            }
                            Text {
                                text: model.fileName
                                color: Theme.textPrimary
                                font.pixelSize: Theme.fontSizeM
                                font.bold: true
                                Layout.fillWidth: true
                                elide: Text.ElideMiddle
                            }
                            Text {
                                text: model.ampelStatus
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                            }
                        }

                        // GREEN — single best candidate + accept button
                        RowLayout {
                            visible: model.ampelStatus === "GREEN"
                            spacing: 10
                            Text {
                                text: model.bestLabel + "  " + Math.round(model.bestScore * 100) + "%"
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeS
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
                            spacing: Theme.spacingXS

                            Repeater {
                                model: JSON.parse(card.ListView.view.model.data(
                                    card.ListView.view.model.index(index, 0),
                                    Qt.UserRole + 6) || "[]")

                                delegate: RadioButton {
                                    id: radioBtn
                                    text: modelData.label + "  " + Math.round(modelData.score * 100) + "%"
                                    contentItem: Text {
                                        text: radioBtn.text
                                        color: Theme.textSecondary
                                        font.pixelSize: Theme.fontSizeS
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
                            spacing: Theme.spacingS

                            Text {
                                text: "Kein zuverlässiger Treffer (<50 %). Bitte Titel manuell eingeben:"
                                color: Theme.colorRed
                                font.pixelSize: Theme.fontSizeXS
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }

                            RowLayout {
                                spacing: Theme.spacingS
                                TextField {
                                    id: manualInput
                                    placeholderText: model.currentTitle || "Filmtitel …"
                                    color: Theme.textPrimary
                                    background: Rectangle { color: Theme.bgInput; radius: 3 }
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
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSizeL
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }
}
