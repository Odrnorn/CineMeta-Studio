import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: root

    ColumnLayout {
        anchors { fill: parent; margins: 16 }
        spacing: 12

        // Toolbar
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

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
                color: "#888"
                font.pixelSize: 12
            }
        }

        // File list
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#0d0d1a"
            border.color: "#2a2a4a"
            radius: 4

            ListView {
                id: fileListView
                anchors { fill: parent; margins: 4 }
                model: localIngestPlugin.file_model
                clip: true

                delegate: Rectangle {
                    width: fileListView.width
                    height: 56
                    color: index % 2 === 0 ? "#13132a" : "#0d0d1a"

                    RowLayout {
                        anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
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
                                color: "#e0e0e0"
                                font.pixelSize: 13
                                elide: Text.ElideMiddle
                                width: parent.width
                            }
                            Text {
                                text: model.assetType
                                color: "#888"
                                font.pixelSize: 11
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
                    color: "#555"
                    font.pixelSize: 14
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
