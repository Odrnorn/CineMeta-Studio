import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import CineMeta 1.0

Item {
    id: root

    ColumnLayout {
        anchors { fill: parent; margins: Theme.spacingL }
        spacing: Theme.spacingM

        // Toolbar
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingS

            Button {
                text: "Verzeichnis wählen …"
                onClicked: folderDialog.open()
            }

            Button {
                text: "Alle ingestieren"
                enabled: fileListView.count > 0 && !fileListView.allIngested
                onClicked: {
                    for (var i = 0; i < pendingFiles.count; i++) {
                        var path = pendingFiles.get(i).filePath
                        localIngestPlugin.ingest_file(path)
                    }
                    pendingFiles.clear()
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: fileListView.count + " Datei(en) gefunden"
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeS
            }
        }

        // File list
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgContainer
            border.color: Theme.border
            radius: Theme.radius

            ListView {
                id: fileListView
                anchors { fill: parent; margins: 4 }
                model: localIngestPlugin.file_model
                clip: true

                delegate: Rectangle {
                    width: fileListView.width
                    height: 56
                    color: index % 2 === 0 ? Theme.bgCard : Theme.bgContainer

                    RowLayout {
                        anchors { fill: parent; leftMargin: Theme.spacingS; rightMargin: Theme.spacingS }
                        spacing: 10

                        // Thumbnail
                        Image {
                            width: 40; height: 40
                            source: model.thumbnailUrl
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                        }

                        // File name + type
                        Column {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: model.fileName
                                color: Theme.textPrimary
                                font.pixelSize: Theme.fontSizeM
                                elide: Text.ElideMiddle
                                width: parent.width
                            }
                            Text {
                                text: model.assetType
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                            }
                        }

                        // Ingest button (single file)
                        Button {
                            text: "Ingest"
                            onClicked: localIngestPlugin.ingest_file(model.filePath)
                        }
                    }
                }

                // Empty state
                Text {
                    anchors.centerIn: parent
                    visible: fileListView.count === 0
                    text: "Wähle ein Verzeichnis, um Dateien zu laden."
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSizeL
                }
            }
        }
    }

    // Folder picker
    FolderDialog {
        id: folderDialog
        title: "Verzeichnis wählen"
        onAccepted: {
            pendingFiles.clear()
            folderScanner.scanFolder(folderDialog.selectedFolder)
        }
    }

    // Scans a folder and populates the pending list
    QtObject {
        id: folderScanner

        function scanFolder(folderUrl) {
            // Delegate to Python bridge for directory listing
            var files = localIngestPlugin.list_files(folderUrl)
            for (var i = 0; i < files.length; i++) {
                pendingFiles.append({ "filePath": files[i] })
            }
        }
    }

    ListModel { id: pendingFiles }
}
