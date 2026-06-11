from __future__ import annotations
import io
import json
import uuid
from pathlib import Path
from typing import Any

from cinemeta.domain.assets import AssetType, MediaAsset
from cinemeta.domain.hierarchy import AssetHierarchy
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from cinemeta.plugin_interface import CineMetaPlugin, CineMetaWorkbench

_PLUGIN_DIR = Path(__file__).parent
_MAX_FRAMES = 20
_FRAMES_ROOT = Path.home() / ".cinemeta" / "frames"

# ---------------------------------------------------------------------------
# Stub helper: generate a colored PNG thumbnail using Pillow only
# ---------------------------------------------------------------------------

def _make_frame_png(hue_degrees: int, size: tuple[int, int] = (320, 180)) -> bytes:
    """Return PNG bytes for a solid-colour thumbnail at the given HSV hue."""
    from PIL import Image
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(hue_degrees / 360.0, 0.7, 0.55)
    colour = (int(r * 255), int(g * 255), int(b * 255))
    img = Image.new("RGB", size, colour)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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
    """Stub video-analysis plugin.

    Uses deterministic mock data (mock_video_data.json) and Pillow to generate
    coloured thumbnail PNGs.  No ffprobe, scenedetect, or opencv required.
    The real backend will replace this stub while keeping the identical event
    contract.
    """

    def __init__(self) -> None:
        self._db: Database | None = None
        self._hierarchy: AssetHierarchy | None = None
        data_path = _PLUGIN_DIR / "mock_video_data.json"
        self._profiles: list[dict] = json.loads(data_path.read_text(encoding="utf-8"))["profiles"]

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

        # 1. Pick a deterministic mock profile
        profile = self._profiles[hash(asset_id) % len(self._profiles)]
        scene_count = min(profile["scene_count"], _MAX_FRAMES)

        # 2. Persist video metadata (same keys a real ffprobe backend would produce)
        meta = {k: profile[k] for k in ("fps", "duration", "width", "height", "codec")}
        asset.raw_metadata = meta
        self._db.save_asset(asset)

        # 3. Generate stub frames as coloured PNG thumbnails via Pillow
        frames_dir = _FRAMES_ROOT / asset_id
        frames_dir.mkdir(parents=True, exist_ok=True)

        asset_hash = hash(asset_id)
        frame_ids: list[str] = []

        for i in range(scene_count):
            hue = (asset_hash + i * 37) % 360
            frame_path = frames_dir / f"scene_{i:03d}.png"
            frame_path.write_bytes(_make_frame_png(hue))

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
            scene_count=scene_count,
        )
