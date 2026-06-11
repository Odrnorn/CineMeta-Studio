import QtQuick
import QtQuick.Controls
import CineMeta 1.0

Item {
    id: root

    Column {
        anchors.centerIn: parent
        spacing: Theme.spacingL

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Video Analysis"
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeXL
            font.bold: true
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Extrahierte Frames erscheinen im Validation Workbench."
            color: Theme.textMuted
            font.pixelSize: Theme.fontSizeL
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
