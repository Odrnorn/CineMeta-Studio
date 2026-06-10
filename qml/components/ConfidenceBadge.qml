import QtQuick

Rectangle {
    id: badge

    // "GREEN" | "YELLOW" | "RED" | "PENDING"
    property string status: "PENDING"

    width: 14
    height: 14
    radius: 7

    color: {
        switch (status) {
        case "GREEN":   return "#4caf50"
        case "YELLOW":  return "#ffeb3b"
        case "RED":     return "#f44336"
        default:        return "#9e9e9e"
        }
    }

    ToolTip.visible: hovered
    ToolTip.text: status

    HoverHandler {}
}
