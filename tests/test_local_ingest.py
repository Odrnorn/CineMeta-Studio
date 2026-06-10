import io
import struct
from pathlib import Path

import pytest

from cinemeta.domain.assets import AssetType
from cinemeta.event_bus import EventBus
from cinemeta.persistence import Database
from plugins.local_ingest.lo_fi_renderer import ThumbnailRenderer, _FALLBACK_PNG
from plugins.local_ingest.plugin import LocalIngestPlugin, _asset_type


# ---------------------------------------------------------------------------
# AssetType detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,expected", [
    ("photo.jpg",  AssetType.IMAGE),
    ("photo.JPEG", AssetType.IMAGE),
    ("scan.tiff",  AssetType.IMAGE),
    ("doc.txt",    AssetType.TEXT),
    ("report.pdf", AssetType.TEXT),
    ("clip.mp4",   AssetType.VIDEO),
    ("film.mov",   AssetType.VIDEO),
    ("unknown.xyz",AssetType.TEXT),  # fallback
    ("no_ext",     AssetType.TEXT),  # fallback
])
def test_asset_type_from_extension(path, expected):
    assert _asset_type(path) == expected


# ---------------------------------------------------------------------------
# Plugin — ingest logic (no Qt, no UI)
# ---------------------------------------------------------------------------

def _plugin_with_db():
    db = Database(":memory:")
    plugin = LocalIngestPlugin()
    plugin.initialize(db=db)
    return plugin, db


def test_ingest_creates_asset(tmp_path):
    (tmp_path / "img.png").write_bytes(b"fake")
    plugin, _ = _plugin_with_db()
    result = plugin.ingest_file(str(tmp_path / "img.png"))
    assert "asset_id" in result
    assert result["asset_type"] == AssetType.IMAGE.value


def test_ingest_saves_to_db(tmp_path):
    (tmp_path / "doc.txt").write_text("hello")
    plugin, db = _plugin_with_db()
    result = plugin.ingest_file(str(tmp_path / "doc.txt"))
    loaded = db.load_asset(result["asset_id"])
    assert loaded is not None
    assert loaded.type == AssetType.TEXT


def test_ingest_publishes_event(tmp_path):
    (tmp_path / "vid.mp4").write_bytes(b"data")
    plugin, _ = _plugin_with_db()

    received = []
    from cinemeta.event_bus import bus
    bus.subscribe("asset.created", lambda **kw: received.append(kw))

    plugin.ingest_file(str(tmp_path / "vid.mp4"))
    bus.unsubscribe("asset.created", received.append)  # cleanup attempt

    assert len(received) == 1
    assert received[0]["asset_type"] == AssetType.VIDEO.value


def test_ingest_nonexistent_file_still_creates_asset():
    plugin, db = _plugin_with_db()
    result = plugin.ingest_file("/nonexistent/missing.jpg")
    assert result["asset_id"]  # asset created regardless — file validation is UI concern


def test_list_files_filters_supported_extensions(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.txt").write_bytes(b"")
    (tmp_path / "c.exe").write_bytes(b"")
    plugin, _ = _plugin_with_db()
    files = plugin.list_files(str(tmp_path))
    names = {Path(f).name for f in files}
    assert names == {"a.jpg", "b.txt"}


def test_list_files_nonexistent_dir():
    plugin, _ = _plugin_with_db()
    assert plugin.list_files("/nonexistent/dir") == []


# ---------------------------------------------------------------------------
# ThumbnailRenderer
# ---------------------------------------------------------------------------

def _make_png_bytes(size=(4, 4)) -> bytes:
    """Create a minimal valid PNG via Pillow."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, color=(128, 64, 32)).save(buf, format="PNG")
    return buf.getvalue()


def test_thumbnail_returns_bytes(tmp_path):
    img_path = tmp_path / "test.png"
    img_path.write_bytes(_make_png_bytes())
    renderer = ThumbnailRenderer()
    result = renderer.generate(str(img_path))
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result[:4] == b"\x89PNG"


def test_thumbnail_unknown_file_returns_fallback(tmp_path):
    renderer = ThumbnailRenderer()
    result = renderer.generate(str(tmp_path / "missing.jpg"))
    assert result == _FALLBACK_PNG


def test_thumbnail_non_image_file_returns_fallback(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    renderer = ThumbnailRenderer()
    result = renderer.generate(str(bad))
    assert result == _FALLBACK_PNG


def test_thumbnail_respects_size(tmp_path):
    from PIL import Image
    img_path = tmp_path / "big.png"
    img_path.write_bytes(_make_png_bytes((512, 512)))
    renderer = ThumbnailRenderer()
    result = renderer.generate(str(img_path), size=(64, 64))
    img = Image.open(io.BytesIO(result))
    assert img.width <= 64 and img.height <= 64
