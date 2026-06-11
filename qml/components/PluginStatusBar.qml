import QtQuick
import QtQuick.Layouts
import CineMeta 1.0

Item {
    anchors.fill: parent

    RowLayout {
        anchors { fill: parent; leftMargin: Theme.spacingM; rightMargin: Theme.spacingM }
        spacing: Theme.spacingS

        Text {
            text: "Plugins:"
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeXS
        }

        // Populated at runtime by the Python bridge
        Repeater {
            model: pluginModel  // exposed from Python via QAbstractListModel

            delegate: Row {
                spacing: Theme.spacingXS
                Text {
                    text: model.pluginName
                    color: model.active ? Theme.textPrimary : Theme.textMuted
                    font.pixelSize: Theme.fontSizeXS
                }
            }
        }

        Item { Layout.fillWidth: true }
    }
}
