from __future__ import annotations
import uuid
from pathlib import Path
from typing import Any

from cinemeta.domain.assets import AssetType, MediaAsset
from cinemeta.domain.hierarchy import AssetHierarchy
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from cinemeta.plugin_interface import CineMetaPlugin, CineMetaWorkbench
from .ffprobe_engine import FfprobeEngine
from .frame_extractor import FrameExtractorEngine
from .scene_detector import SceneDetectorEngine

_PLUGIN_DIR = Path(__file__).parent
_MAX_FRAMES = 20
_FRAMES_ROOT = Path.home() / ".cinemeta" / "frames"


class VideoWorkbench(CineMetaWorkbench):
    @property
    def id(self) -> str:
        return "video_analysis"

    @property
    def label(self) -> str:
        return "Video Analysis"

    @property
    def qml_component(self) -> str:
        return str(_PLUGIN_DIR / "qml" / "VideoWorkbench.qml")


class VideoAnalysisPlugin(CineMetaPlugin):
    def __init__(self) -> None:
        self._db: Database | None = None
        self._hierarchy: AssetHierarchy | None = None
        self._ffprobe = FfprobeEngine()
        self._scenes = SceneDetectorEngine()
        self._frames = FrameExtractorEngine()

    @property
    def name(self) -> str:
        return "video_analysis"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def workbenches(self) -> list[CineMetaWorkbench]:
        return [VideoWorkbench()]

    def initialize(
        self,
        db: Database | None = None,
        hierarchy: AssetHierarchy | None = None,
    ) -> None:
        self._db = db
        self._hierarchy = hierarchy
        bus.subscribe("asset.created", self._on_asset_created)

    def teardown(self) -> None:
        bus.unsubscribe("asset.created", self._on_asset_created)
        self._db = None
        self._hierarchy = None

    def _on_asset_created(self, asset_id: str, asset_type: str, **_: Any) -> None:
        if asset_type != AssetType.VIDEO.value:
            return
        if self._db is None:
            return

        asset = self._db.load_asset(asset_id)
        if asset is None:
            return

        # 1. Extract and persist video metadata
        meta = self._ffprobe.extract(asset.source_path)
        if meta:
            asset.raw_metadata = meta
            self._db.save_asset(asset)

        # 2. Detect scene boundaries
        timestamps = self._scenes.detect(asset.source_path)[:_MAX_FRAMES]

        # 3. Extract one frame per scene
        frame_ids: list[str] = []
        for i, ts in enumerate(timestamps):
            frame_path = _FRAMES_ROOT / asset_id / f"scene_{i:03d}.png"
            self._frames.extract_frame(asset.source_path, ts, str(frame_path))

            frame_asset = MediaAsset(
                id=str(uuid.uuid4()),
                type=AssetType.VIDEO_FRAME,
                source_path=str(frame_path),
                parent_id=asset_id,
            )
            self._db.save_asset(frame_asset)
            if self._hierarchy is not None:
                self._hierarchy.add_child(asset_id, frame_asset)

            bus.publish(
                "asset.created",
                asset_id=frame_asset.id,
                asset_type=AssetType.VIDEO_FRAME.value,
            )
            bus.publish(
                "xmp.extracted",
                asset_id=frame_asset.id,
                hfv_data={},
                had_xmp=False,
            )
            frame_ids.append(frame_asset.id)

        bus.publish(
            "frames.extracted",
            asset_id=asset_id,
            frame_ids=frame_ids,
            scene_count=len(timestamps),
        )
