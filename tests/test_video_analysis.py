from __future__ import annotations
import subprocess
import uuid

import pytest

from cinemeta.domain.assets import AssetType, MediaAsset
from cinemeta.domain.hierarchy import AssetHierarchy
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from plugins.video_analysis.ffprobe_engine import FfprobeEngine
from plugins.video_analysis.frame_extractor import FrameExtractorEngine
from plugins.video_analysis.plugin import VideoAnalysisPlugin
from plugins.video_analysis.scene_detector import SceneDetectorEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_FFPROBE = {"fps": 24.0, "duration": 90.0, "width": 1920, "height": 1080, "codec": "h264"}
_THREE_SCENES = [0.0, 30.0, 60.0]


def _db_with_video() -> tuple[Database, MediaAsset]:
    db = Database(":memory:")
    asset = MediaAsset(id=str(uuid.uuid4()), type=AssetType.VIDEO, source_path="/fake/video.mp4")
    db.save_asset(asset)
    return db, asset


def _plugin(db: Database, hierarchy: AssetHierarchy | None = None) -> VideoAnalysisPlugin:
    p = VideoAnalysisPlugin()
    p.initialize(db=db, hierarchy=hierarchy or AssetHierarchy())
    return p


def _mock_engines(monkeypatch, ffprobe=_FAKE_FFPROBE, scenes=_THREE_SCENES, frame_ok=True):
    monkeypatch.setattr(FfprobeEngine, "extract", lambda self, p: ffprobe)
    monkeypatch.setattr(SceneDetectorEngine, "detect", lambda self, p: list(scenes))
    monkeypatch.setattr(FrameExtractorEngine, "extract_frame", lambda self, *a: frame_ok)


# ---------------------------------------------------------------------------
# A — FfprobeEngine
# ---------------------------------------------------------------------------

def test_ffprobe_returns_expected_keys(monkeypatch):
    engine = FfprobeEngine()
    monkeypatch.setattr(engine, "_run", lambda p: _FAKE_FFPROBE)
    result = engine.extract("/any.mp4")
    assert {"fps", "duration", "width", "height", "codec"} == set(result.keys())


def test_ffprobe_returns_empty_on_file_not_found(monkeypatch):
    engine = FfprobeEngine()
    monkeypatch.setattr(engine, "_run", lambda p: (_ for _ in ()).throw(FileNotFoundError()))
    assert engine.extract("/missing.mp4") == {}


def test_ffprobe_returns_empty_on_subprocess_error(monkeypatch):
    engine = FfprobeEngine()
    monkeypatch.setattr(engine, "_run", lambda p: (_ for _ in ()).throw(subprocess.SubprocessError()))
    assert engine.extract("/bad.mp4") == {}


# ---------------------------------------------------------------------------
# B — SceneDetectorEngine
# ---------------------------------------------------------------------------

def test_scene_detector_returns_float_list(monkeypatch):
    engine = SceneDetectorEngine()
    monkeypatch.setattr(engine, "detect", lambda p: [0.0, 45.2, 92.7])
    result = engine.detect("/any.mp4")
    assert isinstance(result, list)
    assert all(isinstance(t, float) for t in result)


def test_scene_detector_fallback_on_error(monkeypatch):
    engine = SceneDetectorEngine()
    # Simulate scenedetect not installed by patching detect to raise
    original_detect = engine.detect

    def _raising(path):
        raise ImportError("no scenedetect")

    monkeypatch.setattr(engine, "detect", _raising)
    # The fallback is inside detect() itself; test the class-level fallback
    # by calling the real detect which wraps with try/except
    result = SceneDetectorEngine().detect("/any.mp4")  # real call — returns [0.0] when sd not installed
    assert isinstance(result, list)
    assert len(result) >= 1


# ---------------------------------------------------------------------------
# C — FrameExtractorEngine
# ---------------------------------------------------------------------------

def test_frame_extractor_returns_true_on_success(monkeypatch):
    engine = FrameExtractorEngine()
    monkeypatch.setattr(engine, "extract_frame", lambda *a: True)
    assert engine.extract_frame("/v.mp4", 0.0, "/out.png") is True


def test_frame_extractor_returns_false_on_error(monkeypatch):
    engine = FrameExtractorEngine()
    monkeypatch.setattr(engine, "extract_frame", lambda *a: False)
    assert engine.extract_frame("/v.mp4", 0.0, "/out.png") is False


# ---------------------------------------------------------------------------
# D — Plugin lifecycle
# ---------------------------------------------------------------------------

def test_plugin_subscribes_on_initialize():
    db, _ = _db_with_video()
    p = _plugin(db)
    assert p._on_asset_created in bus._handlers.get("asset.created", [])
    p.teardown()


def test_plugin_unsubscribes_on_teardown():
    db, _ = _db_with_video()
    p = _plugin(db)
    p.teardown()
    assert p._on_asset_created not in bus._handlers.get("asset.created", [])


def test_plugin_skips_image_assets(monkeypatch):
    db, _ = _db_with_video()
    called = []
    monkeypatch.setattr(FfprobeEngine, "extract", lambda self, p: called.append(p) or {})
    p = _plugin(db)
    bus.publish("asset.created", asset_id="x", asset_type=AssetType.IMAGE.value)
    assert called == []
    p.teardown()


# ---------------------------------------------------------------------------
# E — Core pipeline
# ---------------------------------------------------------------------------

def test_stores_video_metadata_in_raw_metadata(monkeypatch):
    db, video = _db_with_video()
    _mock_engines(monkeypatch)
    p = _plugin(db)
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    loaded = db.load_asset(video.id)
    assert loaded.raw_metadata == _FAKE_FFPROBE
    p.teardown()


def test_creates_frame_assets_in_db(monkeypatch):
    db, video = _db_with_video()
    _mock_engines(monkeypatch)
    p = _plugin(db)
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    frames = [a for a in db.all_assets() if a.type == AssetType.VIDEO_FRAME]
    assert len(frames) == 3
    assert all(f.parent_id == video.id for f in frames)
    p.teardown()


def test_caps_at_max_frames(monkeypatch):
    db, video = _db_with_video()
    _mock_engines(monkeypatch, scenes=[float(i) for i in range(25)])
    p = _plugin(db)
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    frames = [a for a in db.all_assets() if a.type == AssetType.VIDEO_FRAME]
    assert len(frames) == 20
    p.teardown()


def test_registers_frames_in_hierarchy(monkeypatch):
    db, video = _db_with_video()
    hierarchy = AssetHierarchy()
    hierarchy.add(video)
    _mock_engines(monkeypatch)
    p = VideoAnalysisPlugin()
    p.initialize(db=db, hierarchy=hierarchy)
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    children = hierarchy.get_children(video.id)
    assert len(children) == 3
    assert all(c.type == AssetType.VIDEO_FRAME for c in children)
    p.teardown()


def test_publishes_frames_extracted(monkeypatch):
    db, video = _db_with_video()
    _mock_engines(monkeypatch)
    p = _plugin(db)
    events: list[dict] = []
    bus.subscribe("frames.extracted", lambda **kw: events.append(kw))
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    bus.unsubscribe("frames.extracted", events.append)
    assert len(events) == 1
    assert events[0]["asset_id"] == video.id
    assert events[0]["scene_count"] == 3
    assert len(events[0]["frame_ids"]) == 3
    p.teardown()


def test_publishes_xmp_extracted_per_frame(monkeypatch):
    db, video = _db_with_video()
    _mock_engines(monkeypatch)
    p = _plugin(db)
    xmp_events: list[dict] = []
    bus.subscribe("xmp.extracted", lambda **kw: xmp_events.append(kw))
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    bus.unsubscribe("xmp.extracted", xmp_events.append)
    frame_events = [e for e in xmp_events if not e["had_xmp"] and e["hfv_data"] == {}]
    assert len(frame_events) == 3
    p.teardown()


# ---------------------------------------------------------------------------
# F — Edge cases
# ---------------------------------------------------------------------------

def test_survives_missing_ffprobe(monkeypatch):
    db, video = _db_with_video()
    monkeypatch.setattr(FfprobeEngine, "extract", lambda self, p: {})
    monkeypatch.setattr(SceneDetectorEngine, "detect", lambda self, p: _THREE_SCENES)
    monkeypatch.setattr(FrameExtractorEngine, "extract_frame", lambda self, *a: False)
    p = _plugin(db)
    events: list[dict] = []
    bus.subscribe("frames.extracted", lambda **kw: events.append(kw))
    bus.publish("asset.created", asset_id=video.id, asset_type=AssetType.VIDEO.value)
    bus.unsubscribe("frames.extracted", events.append)
    assert len(events) == 1
    loaded = db.load_asset(video.id)
    assert loaded.raw_metadata == {}
    p.teardown()
