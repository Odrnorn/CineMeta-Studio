# CineMeta Studio — Master-Projektplan (v3)

> **Open-Source Desktop-Anwendung für filmhistorische Forschung**
> Vereint klassische Archivarbeit mit modernen KI-Auswertungen (semantische Netzwerke, Szenerkennung, Konfidenzwerte).

---

## Architekturprinzip: Microkernel

> **Verträge in den Core, Ausführung in die Plugins.**

Ein rein extremer Plugin-Ansatz, bei dem Datenmodelle und Schemata in Plugins liegen, führt zu zirkulären Abhängigkeiten, weil Plugins dann untereinander kommunizieren müssten. Daher gilt:

| Ebene | Zuständigkeit |
|---|---|
| **Core** | Definiert Datenstrukturen, Schema-Vertrag, Konfidenz-Logik — die unveränderlichen Regeln |
| **Plugins** | Liefern Daten (Ingest, XMP, Video) oder konsumieren sie (Visualisierung, Export) |

Plugins kennen den Core. Plugins kennen sich **nicht** gegenseitig — Kommunikation läuft ausschließlich über den Event Bus.

---

## 1. Tech-Stack

| Komponente | Entscheidung |
|---|---|
| **Frontend** | Qt 6 / QML · Qt Quick |
| **Logikschicht** | Python + PySide6 |
| **Persistenz** | SQLite (Assets & Relationen) + ChromaDB (Semantik-Vektoren) |
| **Architekturmuster** | Microkernel: schlanker Core + optionale Plugins |
| **Lizenz** | GPLv3 |

---

## 2. Core-Package — `cinemeta/`

Der Core hat **keine eigenen Workbenches** und **keine Laufzeit-Abhängigkeiten zu Plugins**. Er stellt ausschließlich Infrastruktur und Verträge bereit.

### 2a. Infrastruktur

| Modul | Funktion |
|---|---|
| `plugin_interface.py` | ABCs: `CineMetaPlugin`, `CineMetaWorkbench`, `AIModelPlugin`, `ExportPlugin` |
| `plugin_registry.py` | Laden, Aktivieren, Deaktivieren, Versionsprüfung |
| `event_bus.py` | Qt-Signals-basierter Nachrichtenkanal (lose Kopplung zwischen Plugins) |
| `persistence.py` | SQLite-Verbindung + Basis-Tabellen für Assets & Relationen |

### 2b. Domain — `cinemeta/domain/`

Das zentrale Datenmodell. Ermöglicht, dass Plugins typunabhängig mit Assets arbeiten.

| Modul | Funktion |
|---|---|
| `assets.py` | `MediaAsset` — polymorphe Basisklasse für Bild, Text, Video-Frame. Trägt Typ, Pfad, Roh-Metadaten, HFV-Mapping-Status. |
| `hierarchy.py` | Parent-Child-Relationen: Film → Szene → Frame. Ein Bild-KI-Plugin kann transparent sowohl ein Standalone-Foto als auch einen extrahierten Video-Frame verarbeiten, ohne das Quell-Plugin zu kennen. |
| `confidence_logic.py` | Berechnet Konfidenz-Abstände zwischen KI-Vorschlägen. Klassifiziert in 🟢 🟡 🔴. **Ist Core-Logik**, weil das Ampelsystem das fundamentale UX-Versprechen der Anwendung ist. |

### 2c. Schema — `cinemeta/schema/`

Das HFV-1.0-Schema bestimmt das Zielformat für die SQLite-Persistenz. Es ist der unumstößliche Vertrag der Anwendung.

| Modul | Funktion |
|---|---|
| `schema_manager.py` | Liest XSD/JSON-Schemata dynamisch ein. Stellt Plugins eine Mapping-API zur Verfügung. |
| `definitions/hfv-1.0.xsd` | Kanonisches HFV-1.0 XML Schema (FilmRecord, VideoRecord, SceneRecord) |

---

## 3. Plugin-Ökosystem

Jedes Plugin registriert beim Start seine Workbenches beim Workbench Router. Workbenches erscheinen in der Navigation nur, wenn das zugehörige Plugin aktiv ist.

### Plugin: `local_ingest`
**Workbench:** *Ingest Workbench*
- Dateimanager: lokale Ordner durchsuchen, Verzeichnisse anlegen
- Lo-Fi-Rendering: Thumbnails via Lazy Load (Pillow + Qt ImageProvider)
- Liefert `MediaAsset`-Objekte in die Core-Hierarchie

**Austauschbarkeit:** Kann später durch ein Cloud-Ingest- oder IIIF-Server-Plugin ersetzt werden, ohne dass der Core berührt wird.

### Plugin: `metadata_xmp`
**Workbench:** keine eigene — ergänzt Ingest Workbench um XMP-Panel
- XMP-Engine: liest bekannte und unbekannte Tags aus Bild- und Textdateien (Passthrough, kein Datenverlust)
- Mappt extrahierte Felder auf HFV-1.0 via `schema_manager.py`

**Austauschbarkeit:** XMP-Bibliotheken sind updatesensibel. Als Plugin kann die Engine isoliert aktualisiert werden, ohne das Datenmodell zu gefährden.

### Plugin: `mock_ai` *(Entwicklungs-Plugin)*
**Workbench:** keine — konfigurierbar über Plugin Manager
- Simuliert `AIModelPlugin`-Output mit Konfidenzwerten aus JSON-Datei
- Schnittstelle identisch mit echten KI-Modell-Plugins → direkter Austausch in späteren Phasen

### Plugin: `video_analysis`
**Workbench:** *Video Workbench* (Timeline + Szenen-UI)
- Szenerkennung: PySceneDetect (Cut-Detection, Content-Detect, Fade)
- Frame-Extraktion: OpenCV + Frame-Cache-Manager
- Video-Metadaten: ffprobe (Codec, Auflösung, FPS, Bitrate, Tonspuren, Dauer)
- XMP-Sidecar Writer: schreibt `.xmp` neben jede Videodatei
- Extrahierte Keyframes → Core-Hierarchie als Kind-Elemente (SceneRecord unter VideoRecord)
- Szenen-Konfidenzwerte → Core `confidence_logic.py` → Ampelsystem

**Optionalität:** Nicht jeder filmhistorische Kontext erfordert Video-Auswertung. Die rechenintensive Pipeline (PySceneDetect, OpenCV, ffmpeg) bleibt optional und hat keine Auswirkung auf den Core.

### Plugin: `semantic_analysis`
**Workbench:** *Analysis Workbench*
- Reiner Konsument der Core-Datenbank — verändert das Datenmodell nicht
- Visualisiert: Zeitachsen-Slider, Semantik-Graph (D3.js / QtCharts), Szenensequenz-Analyse
- Konsumiert: validierte Assets + SceneRecords + Konfidenzwerte

### Plugin: `universal_export`
**Workbench:** keine — Export-Actions in anderen Workbenches
- Reiner Konsument der Core-Datenbank — verändert das Datenmodell nicht
- Exportiert validierte Einträge als HFV-1.0 XML, CSV, JSON-LD

---

## 4. Validierungs-Regelwerk (Ampelsystem)

Die Logik lebt in `cinemeta/domain/confidence_logic.py`. KI-Plugins liefern nur Roh-Scores.

**Plugin-Output (Rohformat):**
```json
[
  {"label": "Metropolis (1927)", "score": 0.82},
  {"label": "Nosferatu (1922)",  "score": 0.78}
]
```

**Core-Klassifikation:**

| Status | Kriterium | Verhalten |
|---|---|---|
| 🟢 **Grün** | Score > 85 % **UND** Abstand zur nächsten Option groß | Auto-Akzeptanz / 1-Klick |
| 🟡 **Gelb** | Mehrere Optionen nah beieinander | Automation blockiert — manuelle Auswahl |
| 🔴 **Rot** | Höchster Score < 50 % | Zwingende manuelle Eingabe |

---

## 5. Implementierungs-Roadmap (v3)

> Phasen **strikt sequenziell**.

### Phase 1 — Microkernel-Core
- Qt 6 / QML + PySide6 Setup
- `plugin_interface.py`: alle ABCs (`CineMetaPlugin`, `CineMetaWorkbench`, `AIModelPlugin`, `ExportPlugin`)
- `plugin_registry.py`: Laden / Aktivieren / Deaktivieren
- `event_bus.py`: Qt-Signals-Kanal
- `domain/assets.py`: `MediaAsset` Basisklasse
- `domain/hierarchy.py`: Parent-Child-Relation (Film → Szene → Frame)
- `domain/confidence_logic.py`: Score-Berechnung + Ampel-Klassifikation
- `schema/schema_manager.py` + `hfv-1.0.xsd`: Schema dynamisch laden
- `persistence.py`: SQLite mit Asset- und Relations-Tabellen
- QML-Shell: `main.qml`, `WorkbenchRouter.qml` (dynamisch, zeigt leeren State wenn keine Plugins)
- QML-Komponenten: `ConfidenceBadge.qml`, `PluginManager.qml`

### Phase 2 — `local_ingest` Plugin
- Ingest Workbench (File-Browser, Verzeichnisse anlegen)
- `lo_fi_renderer.py`: Thumbnails, Lazy Loading
- Erzeugt `MediaAsset`-Objekte → Core Persistence

### Phase 3 — `metadata_xmp` Plugin
- XMP-Engine (bekannte + unbekannte Tags, Passthrough)
- Mapping via `schema_manager.py` → HFV-1.0-Felder

### Phase 4 — `mock_ai` Plugin + Validation UI
- Mock-AI-Plugin (JSON-Konfidenzwerte)
- Validation Workbench: zeigt Core-Ampelstatus visuell an, manuelle Überschreibungs-Tools
- Anbindung: Plugin-Output → `confidence_logic.py` → UI

### Phase 5 — `video_analysis` Plugin
- Video Workbench (Timeline + Szenen-UI)
- `scene_detector.py`: PySceneDetect
- `frame_extractor.py`: OpenCV + Frame-Cache-Manager
- `video_metadata.py`: ffprobe
- `sidecar_writer.py`: .xmp Sidecar
- HFV-Schema-Erweiterung: VideoRecord + SceneRecord (im Core-XSD)

### Phase 6 — `semantic_analysis` Plugin
- Analysis Workbench
- D3.js (WebView) oder QtCharts
- Zeitachsen-Slider + Semantik-Graph
- ChromaDB-Integration (Vektor-Ähnlichkeit)

### Phase 7 — `universal_export` Plugin + Polish
- XML-Exporter (HFV-1.0), CSV-Exporter
- Plugin-Schnittstellen stabilisieren
- GPLv3-Lizenzheader, Dokumentation

---

## Entscheidungs-Log

| Datum | Entscheidung | Begründung |
|---|---|---|
| 2026-06-10 | Python + PySide6 | KI-Ökosystem, XMP-Bibliotheken |
| 2026-06-10 | QML / Qt Quick | Fließende UI, Lazy Loading |
| 2026-06-10 | GPLv3 | Qt Data Visualization |
| 2026-06-10 | Plugin-First: Workbenches aus Plugins | Maximale Modularität |
| 2026-06-10 | Video-Analysis als Plugin | Optional, rechenintensiv |
| 2026-06-10 | **Microkernel: domain/ + schema/ + confidence in Core** | Verhindert zirkuläre Plugin-Abhängigkeiten; Datenvertrag ist unveränderlich |
