# CineMeta Studio

Open-source desktop application for film history research — combining classical archival workflows with modern AI capabilities.

## What it does

- Ingest images, text documents, and video files
- Extract and map XMP metadata to a canonical HFV schema
- AI-assisted confidence scoring with traffic-light validation (green / yellow / red)
- Scene detection and frame extraction for video sources
- Semantic network analysis with vector embeddings (ChromaDB)
- Export to HFV-1.0 XML, CSV, and JSON-LD

## Tech stack

| Layer | Technology |
|---|---|
| UI | Qt 6 / QML |
| Backend | Python 3 + PySide6 |
| Scene detection | PySceneDetect |
| Video metadata | ffprobe |
| Frame extraction | OpenCV + ffmpeg |
| XMP parsing | python-xmp-toolkit |
| Vector DB | ChromaDB |
| Persistence | SQLite |
| Visualization | D3.js (WebView) / QtCharts |

## Architecture

The application follows a **microkernel pattern**: a stable core defines data contracts, validation rules, and schema — all business logic lives in plugins that communicate exclusively via an event bus.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full technical specification and [MASTERPLAN.md](MASTERPLAN.md) for the implementation roadmap (7 phases).

## Status

Planning phase complete. Implementation starts with Phase 1 (microkernel core).

## License

[GPLv3](LICENSE)
