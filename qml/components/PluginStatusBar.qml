import QtQuick
import QtQuick.Layouts

Item {
    anchors.fill: parent

    RowLayout {
        anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
        spacing: 8

        Text {
            text: "Plugins:"
            color: "#888"
            font.pixelSize: 11
        }

        // Populated at runtime by the Python bridge
        Repeater {
            model: pluginModel  // exposed from Python via QAbstractListModel

            delegate: Row {
                spacing: 4
                Text {
                    text: model.pluginName
                    color: model.active ? "#e0e0e0" : "#555"
                    font.pixelSize: 11
                }
            }
        }

        Item { Layout.fillWidth: true }
    }
}
