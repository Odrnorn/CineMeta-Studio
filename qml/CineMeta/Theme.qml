pragma Singleton
import QtQuick

QtObject {
    // Backgrounds
    readonly property color bgApp:       "#1a1a2e"
    readonly property color bgPanel:     "#16213e"
    readonly property color bgContainer: "#0d0d1a"
    readonly property color bgCard:      "#13132a"
    readonly property color bgInput:     "#1a1a3a"

    // Text
    readonly property color textPrimary:   "#e0e0e0"
    readonly property color textSecondary: "#aaaaaa"
    readonly property color textMuted:     "#666666"

    // Ampel (traffic light)
    readonly property color colorGreen:   "#4caf50"
    readonly property color colorYellow:  "#ffeb3b"
    readonly property color colorRed:     "#f44336"
    readonly property color colorPending: "#9e9e9e"

    // Structure
    readonly property color border:    "#2a2a4a"
    readonly property int   radius:    4
    readonly property int   radiusBadge: 7

    // Spacing
    readonly property int spacingXS: 4
    readonly property int spacingS:  8
    readonly property int spacingM:  12
    readonly property int spacingL:  16
    readonly property int spacingXL: 24

    // Typography
    readonly property int fontSizeXS: 11
    readonly property int fontSizeS:  12
    readonly property int fontSizeM:  13
    readonly property int fontSizeL:  16
    readonly property int fontSizeXL: 18
}
