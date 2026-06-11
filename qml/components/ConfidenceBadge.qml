import QtQuick
import CineMeta 1.0

Rectangle {
    id: badge

    // "GREEN" | "YELLOW" | "RED" | "PENDING"
    property string status: "PENDING"

    width: 14
    height: 14
    radius: Theme.radiusBadge

    color: {
        switch (status) {
        case "GREEN":   return Theme.colorGreen
        case "YELLOW":  return Theme.colorYellow
        case "RED":     return Theme.colorRed
        default:        return Theme.colorPending
        }
    }

    ToolTip.visible: hovered
    ToolTip.text: status

    HoverHandler {}
}
