from __future__ import annotations
import uuid

import pytest

from cinemeta.domain.assets import AssetType, MediaAsset
from cinemeta.event_bus import EventBus, bus
from cinemeta.persistence import Database
from plugins.metadata_xmp.plugin import MetadataXmpPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_with_asset(asset_type: AssetType = AssetType.IMAGE) -> tuple[Database, MediaAsset]:
    db = Database(":memory:")
    asset = MediaAsset(id=str(uuid.uuid4()), type=asset_type, source_path="/fake/file.jpg")
    db.save_asset(asset)
    return db, asset


def _plugin(db: Database) -> MetadataXmpPlugin:
    p = MetadataXmpPlugin()
    p.initialize(db=db)
    return p


# ---------------------------------------------------------------------------
# A — Plugin lifecycle
# ---------------------------------------------------------------------------

def test_plugin_subscribes_on_initialize():
    db, _ = _make_db_with_asset()
    plugin = _plugin(db)
    assert plugin._on_asset_created in bus._handlers.get("asset.created", [])
    plugin.teardown()


def test_plugin_unsubscribes_on_teardown():
    db, _ = _make_db_with_asset()
    plugin = _plugin(db)
    plugin.teardown()
    assert plugin._on_asset_created not in bus._handlers.get("asset.created", [])


def test_plugin_has_no_workbenches():
    db, _ = _make_db_with_asset()
    plugin = _plugin(db)
    assert plugin.workbenches == []
    plugin.teardown()


# ---------------------------------------------------------------------------
# B — Skip rules
# ---------------------------------------------------------------------------

def test_plugin_skips_video_assets():
    db, asset = _make_db_with_asset(AssetType.VIDEO)
    plugin = _plugin(db)
    events: list[dict] = []
    bus.subscribe("xmp.extracted", lambda **kw: events.append(kw))
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.VIDEO.value)
    bus.unsubscribe("xmp.extracted", events.append)
    assert events == []
    plugin.teardown()


def test_plugin_skips_video_frame_assets():
    db, asset = _make_db_with_asset(AssetType.VIDEO_FRAME)
    plugin = _plugin(db)
    events: list[dict] = []
    bus.subscribe("xmp.extracted", lambda **kw: events.append(kw))
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.VIDEO_FRAME.value)
    bus.unsubscribe("xmp.extracted", events.append)
    assert events == []
    plugin.teardown()


# ---------------------------------------------------------------------------
# C — Stub data & DB persistence
# ---------------------------------------------------------------------------

def test_plugin_processes_image_asset_and_saves_hfv():
    db, asset = _make_db_with_asset(AssetType.IMAGE)
    plugin = _plugin(db)
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.IMAGE.value)
    loaded = db.load_asset(asset.id)
    assert set(loaded.hfv_data.keys()) == {"title", "year", "country", "director"}
    assert loaded.hfv_data["title"] in (
        "Metropolis", "Nosferatu", "Battleship Potemkin", "The General", "Der Golem"
    )
    plugin.teardown()


def test_plugin_processes_text_asset():
    db, asset = _make_db_with_asset(AssetType.TEXT)
    plugin = _plugin(db)
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.TEXT.value)
    loaded = db.load_asset(asset.id)
    assert "title" in loaded.hfv_data
    plugin.teardown()


def test_hfv_year_is_string():
    db, asset = _make_db_with_asset(AssetType.IMAGE)
    plugin = _plugin(db)
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.IMAGE.value)
    loaded = db.load_asset(asset.id)
    assert isinstance(loaded.hfv_data["year"], str)
    plugin.teardown()


# ---------------------------------------------------------------------------
# D — Event publishing
# ---------------------------------------------------------------------------

def test_plugin_publishes_xmp_extracted():
    db, asset = _make_db_with_asset(AssetType.IMAGE)
    plugin = _plugin(db)
    events: list[dict] = []
    bus.subscribe("xmp.extracted", lambda **kw: events.append(kw))
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.IMAGE.value)
    bus.unsubscribe("xmp.extracted", events.append)
    assert len(events) == 1
    assert events[0]["asset_id"] == asset.id
    assert events[0]["had_xmp"] is True
    assert "title" in events[0]["hfv_data"]
    plugin.teardown()


def test_event_hfv_data_matches_db():
    db, asset = _make_db_with_asset(AssetType.IMAGE)
    plugin = _plugin(db)
    events: list[dict] = []
    bus.subscribe("xmp.extracted", lambda **kw: events.append(kw))
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.IMAGE.value)
    bus.unsubscribe("xmp.extracted", events.append)
    loaded = db.load_asset(asset.id)
    assert events[0]["hfv_data"] == loaded.hfv_data
    plugin.teardown()


# ---------------------------------------------------------------------------
# E — Determinism & edge cases
# ---------------------------------------------------------------------------

def test_deterministic_profile_selection():
    """Same asset_id must produce same profile within one process run."""
    db, asset = _make_db_with_asset(AssetType.IMAGE)
    plugin = _plugin(db)

    # First trigger
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.IMAGE.value)
    title1 = db.load_asset(asset.id).hfv_data["title"]

    # Reset and re-trigger with same asset_id
    a = db.load_asset(asset.id)
    a.hfv_data = {}
    db.save_asset(a)
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.IMAGE.value)
    title2 = db.load_asset(asset.id).hfv_data["title"]

    assert title1 == title2
    plugin.teardown()


def test_different_assets_can_get_different_profiles():
    """With enough IDs, more than one profile should appear."""
    db = Database(":memory:")
    plugin = MetadataXmpPlugin()
    plugin.initialize(db=db)
    seen_titles: set[str] = set()
    for _ in range(20):
        asset = MediaAsset(id=str(uuid.uuid4()), type=AssetType.IMAGE, source_path="/f.jpg")
        db.save_asset(asset)
        bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.IMAGE.value)
        loaded = db.load_asset(asset.id)
        if loaded and loaded.hfv_data.get("title"):
            seen_titles.add(loaded.hfv_data["title"])
    plugin.teardown()
    assert len(seen_titles) > 1, "All 20 assets got the same profile — hash distribution broken"


def test_skips_when_db_is_none():
    """Plugin must not crash when no db is wired."""
    plugin = MetadataXmpPlugin()
    plugin.initialize(db=None)
    bus.publish("asset.created", asset_id="test-id", asset_type=AssetType.IMAGE.value)
    plugin.teardown()
