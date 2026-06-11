from __future__ import annotations
import uuid

import pytest

from cinemeta.domain.assets import AssetType, MediaAsset
from cinemeta.domain.hierarchy import AssetHierarchy
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from plugins.video_analysis.plugin import VideoAnalysisPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db_with_video() -> tuple[Database, MediaAsset]:
    db = Database(":memory:")
    asset = MediaAsset(id=str(uuid.uuid4()), type=AssetType.VIDEO, source_path="/fake/video.mp4")
    db.save_asset(asset)
    return db, asset


def _plugin(
    db: Database,
    hierarchy: AssetHierarchy | None = None,
    frames_root=None,
    monkeypatch=None,
) -> VideoAnalysisPlugin:
    p = VideoAnalysisPlugin()
    if frames_root is not None and monkeypatch is not None:
        monkeypatch.setattr("plugins.video_analysis.plugin._FRAMES_ROOT", frames_root)
    p.initialize(db=db, hierarchy=hierarchy or AssetHierarchy())
    return p


# ---------------------------------------------------------------------------
# D — Plugin lifecycle
# ---------------------------------------------------------------------------

def test_plugin_subscribes_on_initialize(tmp_path, monkeypatch):
    db, _ = _db_with_video()
    p = _plugin(db, frames_root=tmp_path, monkeypatch=monkeypatch)
    assert p._on_asset_created in bus._handlers.get("asset.created", [])
    p.teardown()


def test_plugin_unsubscribes_on_teardown(tmp_path, monkeypatch):
    db, _ = _db_with_video()
    p = _plugin(db, frames_root=tmp_path, monkeypatch=monkeypatch)
    p.teardown()
    assert p._on_asset_created not in bus._handlers.get("asset.created", [])


def test_plugin_skips_image_assets(tmp_path, monkeypatch):
    db = Database(":memory:")
    p = _plugin(db, frames_root=tmp_path, monkeypatch=monkeypatch)
    called: list[str] = []
    bus.subscribe("frames.extracted", lambda **kw: called.append(kw))
    bus.publish("asset.created", asset_id="x", asset_type=AssetType.IMAGE.value)
    bus.unsubscribe("frames.extracted", called.append)
    assert called == []
    p.teardown()


# ---------------------------------------------------------------------------
# E — Core pipeline
# ---------------------------------------------------------------------------

def test_stores_video_metadata_in_raw_metadata(tmp_path, monkeypatch):
    db, video = _db_with_video()
    p = _plugin(db, frames_root=tmp_path, monkeypatch=monkeypatch)
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    loaded = db.load_asset(video.id)
    assert set(loaded.raw_metadata.keys()) == {"fps", "duration", "width", "height", "codec"}
    assert isinstance(loaded.raw_metadata["fps"], float)
    assert isinstance(loaded.raw_metadata["duration"], float)
    p.teardown()


def test_creates_frame_assets_in_db(tmp_path, monkeypatch):
    db, video = _db_with_video()
    p = _plugin(db, frames_root=tmp_path, monkeypatch=monkeypatch)
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    frames = [a for a in db.all_assets() if a.type == AssetType.VIDEO_FRAME]
    assert len(frames) >= 1
    assert all(f.parent_id == video.id for f in frames)
    p.teardown()


def test_caps_at_max_frames(tmp_path, monkeypatch):
    db, video = _db_with_video()
    # Override profiles so this asset always gets a 25-scene profile
    p = VideoAnalysisPlugin()
    monkeypatch.setattr("plugins.video_analysis.plugin._FRAMES_ROOT", tmp_path)
    p._profiles = [{"fps": 24.0, "duration": 200.0, "width": 1920, "height": 1080, "codec": "h264", "scene_count": 25}]
    p.initialize(db=db, hierarchy=AssetHierarchy())
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    frames = [a for a in db.all_assets() if a.type == AssetType.VIDEO_FRAME]
    assert len(frames) == 20
    p.teardown()


def test_registers_frames_in_hierarchy(tmp_path, monkeypatch):
    db, video = _db_with_video()
    hierarchy = AssetHierarchy()
    hierarchy.add(video)
    p = _plugin(db, hierarchy=hierarchy, frames_root=tmp_path, monkeypatch=monkeypatch)
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    children = hierarchy.get_children(video.id)
    assert len(children) >= 1
    assert all(c.type == AssetType.VIDEO_FRAME for c in children)
    p.teardown()


def test_publishes_frames_extracted(tmp_path, monkeypatch):
    db, video = _db_with_video()
    p = _plugin(db, frames_root=tmp_path, monkeypatch=monkeypatch)
    events: list[dict] = []
    bus.subscribe("frames.extracted", lambda **kw: events.append(kw))
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    bus.unsubscribe("frames.extracted", events.append)
    assert len(events) == 1
    assert events[0]["asset_id"] == video.id
    assert events[0]["scene_count"] >= 1
    assert len(events[0]["frame_ids"]) == events[0]["scene_count"]
    p.teardown()


def test_publishes_xmp_extracted_per_frame(tmp_path, monkeypatch):
    db, video = _db_with_video()
    p = _plugin(db, frames_root=tmp_path, monkeypatch=monkeypatch)
    xmp_events: list[dict] = []
    bus.subscribe("xmp.extracted", lambda **kw: xmp_events.append(kw))
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    bus.unsubscribe("xmp.extracted", xmp_events.append)
    frame_events = [e for e in xmp_events if e["hfv_data"] == {} and not e["had_xmp"]]
    assert len(frame_events) >= 1
    p.teardown()


# ---------------------------------------------------------------------------
# F — Edge cases & stub-specific behaviour
# ---------------------------------------------------------------------------

def test_deterministic_profile_selection(tmp_path, monkeypatch):
    """Same asset_id must always produce the same scene_count (within one run)."""
    db, video = _db_with_video()
    p = _plugin(db, frames_root=tmp_path, monkeypatch=monkeypatch)
    events: list[dict] = []
    bus.subscribe("frames.extracted", lambda **kw: events.append(kw))
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    count_first = events[-1]["scene_count"]

    # Second plugin instance, same asset_id
    db2, video2 = _db_with_video()
    video2.id = video.id  # force same ID
    db2.save_asset(video2)
    p2 = _plugin(db2, frames_root=tmp_path, monkeypatch=monkeypatch)
    bus.publish("asset.created", asset_id=video2.id, asset_type=AssetType.VIDEO.value)
    count_second = events[-1]["scene_count"]

    bus.unsubscribe("frames.extracted", events.append)
    assert count_first == count_second
    p.teardown(); p2.teardown()


def test_frame_png_files_are_created(tmp_path, monkeypatch):
    """Pillow-generated thumbnails must exist as valid PNG files."""
    db, video = _db_with_video()
    p = _plugin(db, frames_root=tmp_path, monkeypatch=monkeypatch)
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    frame_assets = [a for a in db.all_assets() if a.type == AssetType.VIDEO_FRAME]
    assert len(frame_assets) >= 1
    for fa in frame_assets:
        from pathlib import Path
        png = Path(fa.source_path)
        assert png.exists(), f"Frame file missing: {png}"
        assert png.read_bytes()[:4] == b"\x89PNG", f"Not a valid PNG: {png}"
    p.teardown()


def test_skips_when_db_is_none():
    """Plugin must not crash when no db is wired."""
    p = VideoAnalysisPlugin()
    p.initialize(db=None, hierarchy=None)
    # Should not raise
    bus.publish("asset.created", asset_id="test-id", asset_type=AssetType.VIDEO.value)
    p.teardown()
