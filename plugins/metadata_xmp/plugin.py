from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from cinemeta.domain.assets import AssetType
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from cinemeta.plugin_interface import CineMetaPlugin, CineMetaWorkbench

_PLUGIN_DIR = Path(__file__).parent


class MetadataXmpPlugin(CineMetaPlugin):
    """Stub metadata plugin.

    Returns deterministic mock HFV data from mock_xmp_profiles.json.
    No lxml, python-xmp-toolkit, or real XMP files needed.
    The real backend will replace this stub while keeping the identical
    event contract (xmp.extracted with {asset_id, hfv_data, had_xmp}).
    """

    def __init__(self) -> None:
        self._db: Database | None = None
        data_path = _PLUGIN_DIR / "mock_xmp_profiles.json"
        self._profiles: list[dict] = json.loads(
            data_path.read_text(encoding="utf-8")
        )["profiles"]

    @property
    def name(self) -> str:
        return "metadata_xmp"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def workbenches(self) -> list[CineMetaWorkbench]:
        return []

    def initialize(self, db: Database | None = None) -> None:
        self._db = db
        bus.subscribe("asset.created", self._on_asset_created)

    def teardown(self) -> None:
        bus.unsubscribe("asset.created", self._on_asset_created)
        self._db = None

    def _on_asset_created(self, asset_id: str, asset_type: str, **_: Any) -> None:
        if asset_type in (AssetType.VIDEO.value, AssetType.VIDEO_FRAME.value):
            return  # VIDEO handled by video_analysis; VIDEO_FRAME has no XMP

        if self._db is None:
            return

        asset = self._db.load_asset(asset_id)
        if asset is None:
            return

        # Deterministic profile selection: same asset_id → same data
        profile = self._profiles[hash(asset_id) % len(self._profiles)]
        hfv_data: dict[str, Any] = dict(profile)

        asset.hfv_data = hfv_data
        self._db.save_asset(asset)

        bus.publish("xmp.extracted", asset_id=asset_id, hfv_data=hfv_data, had_xmp=True)
