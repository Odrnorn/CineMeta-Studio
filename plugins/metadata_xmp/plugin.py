from __future__ import annotations
from typing import Any

from cinemeta.domain.assets import AssetType
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from cinemeta.plugin_interface import CineMetaPlugin, CineMetaWorkbench
from .xmp_engine import XmpEngine


class MetadataXmpPlugin(CineMetaPlugin):
    def __init__(self) -> None:
        self._db: Database | None = None
        self._engine = XmpEngine()

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
        if asset_type == AssetType.VIDEO.value:
            return  # video metadata handled in Phase 5

        if self._db is None:
            return

        asset = self._db.load_asset(asset_id)
        if asset is None:
            return

        raw_xmp = self._engine.extract(asset.source_path)
        hfv = self._engine.map_to_hfv(raw_xmp)

        asset.raw_metadata = raw_xmp
        asset.hfv_data = hfv
        self._db.save_asset(asset)

        bus.publish("xmp.extracted", asset_id=asset_id, hfv_data=hfv, had_xmp=bool(raw_xmp))
