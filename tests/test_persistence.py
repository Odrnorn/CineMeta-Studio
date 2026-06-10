from cinemeta.domain.assets import AssetStatus, AssetType, MediaAsset
from cinemeta.persistence import Database


def _db() -> Database:
    return Database(":memory:")


def test_save_and_load_asset():
    db = _db()
    a = MediaAsset(id="a1", type=AssetType.IMAGE, source_path="/img/foo.jpg")
    db.save_asset(a)
    loaded = db.load_asset("a1")
    assert loaded is not None
    assert loaded.id == "a1"
    assert loaded.type == AssetType.IMAGE
    assert loaded.source_path == "/img/foo.jpg"
    assert loaded.status == AssetStatus.PENDING
    db.close()


def test_load_nonexistent_returns_none():
    db = _db()
    assert db.load_asset("missing") is None
    db.close()


def test_save_updates_existing():
    db = _db()
    a = MediaAsset(id="a1", type=AssetType.IMAGE, source_path="/old.jpg")
    db.save_asset(a)
    a.source_path = "/new.jpg"
    a.status = AssetStatus.GREEN
    db.save_asset(a)
    loaded = db.load_asset("a1")
    assert loaded.source_path == "/new.jpg"
    assert loaded.status == AssetStatus.GREEN
    db.close()


def test_all_assets():
    db = _db()
    for i in range(3):
        db.save_asset(MediaAsset(id=str(i), type=AssetType.TEXT, source_path=f"/f{i}.txt"))
    assert len(db.all_assets()) == 3
    db.close()


def test_metadata_roundtrip():
    db = _db()
    a = MediaAsset(
        id="m1", type=AssetType.VIDEO, source_path="/vid.mp4",
        raw_metadata={"fps": 25}, hfv_data={"title": "Test Film"},
    )
    db.save_asset(a)
    loaded = db.load_asset("m1")
    assert loaded.raw_metadata == {"fps": 25}
    assert loaded.hfv_data == {"title": "Test Film"}
    db.close()
