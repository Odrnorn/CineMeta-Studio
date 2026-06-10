import pytest
from cinemeta.domain.assets import AssetType, MediaAsset
from cinemeta.domain.hierarchy import AssetHierarchy


def _asset(id_: str, parent_id: str | None = None) -> MediaAsset:
    return MediaAsset(id=id_, type=AssetType.IMAGE, source_path=f"/{id_}", parent_id=parent_id)


def test_add_and_get_root():
    h = AssetHierarchy()
    a = _asset("film1")
    h.add(a)
    assert h.get("film1") is a
    assert h.get_root_assets() == [a]


def test_add_child():
    h = AssetHierarchy()
    film = _asset("film1")
    scene = _asset("scene1")
    h.add(film)
    h.add_child("film1", scene)
    assert scene.parent_id == "film1"
    assert h.get_children("film1") == [scene]


def test_walk_film_scene_frame():
    h = AssetHierarchy()
    film = _asset("film")
    scene = _asset("scene")
    frame = _asset("frame")
    h.add(film)
    h.add_child("film", scene)
    h.add_child("scene", frame)

    ids = [a.id for a in h.walk("film")]
    assert ids == ["film", "scene", "frame"]


def test_get_nonexistent_returns_none():
    h = AssetHierarchy()
    assert h.get("missing") is None


def test_walk_nonexistent_yields_nothing():
    h = AssetHierarchy()
    assert list(h.walk("missing")) == []
