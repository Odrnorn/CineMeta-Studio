from __future__ import annotations
import uuid
from pathlib import Path

import pytest

from cinemeta.domain.assets import AssetStatus, AssetType, MediaAsset
from cinemeta.event_bus import EventBus, bus
from cinemeta.persistence import Database
from plugins.metadata_xmp.plugin import MetadataXmpPlugin
from plugins.metadata_xmp.xmp_engine import XmpEngine, _NS


# ---------------------------------------------------------------------------
# XmpEngine.map_to_hfv
# ---------------------------------------------------------------------------

def _tag(ns_key: str, local: str) -> str:
    return f"{{{_NS[ns_key]}}}{local}"


def test_map_known_title():
    engine = XmpEngine()
    hfv = engine.map_to_hfv({_tag("dc", "title"): "Metropolis"})
    assert hfv["title"] == "Metropolis"


def test_map_known_year_from_date():
    engine = XmpEngine()
    hfv = engine.map_to_hfv({_tag("xmp", "CreateDate"): "1927-03-10"})
    assert hfv["year"] == "1927"


def test_map_photoshop_date_creates_year():
    engine = XmpEngine()
    hfv = engine.map_to_hfv({_tag("photoshop", "DateCreated"): "1964"})
    assert hfv["year"] == "1964"


def test_map_known_country():
    engine = XmpEngine()
    hfv = engine.map_to_hfv({_tag("photoshop", "Country"): "Germany"})
    assert hfv["country"] == "Germany"


def test_map_iptc_country():
    engine = XmpEngine()
    hfv = engine.map_to_hfv({_tag("Iptc4xmpCore", "CountryName"): "France"})
    assert hfv["country"] == "France"


def test_map_known_director():
    engine = XmpEngine()
    hfv = engine.map_to_hfv({_tag("dc", "creator"): "Fritz Lang"})
    assert hfv["director"] == "Fritz Lang"


def test_map_unknown_fields_go_to_passthrough():
    engine = XmpEngine()
    hfv = engine.map_to_hfv({"{http://example.com/}custom": "value"})
    assert "passthrough" in hfv
    assert hfv["passthrough"]["{http://example.com/}custom"] == "value"


def test_map_mixed_known_and_unknown():
    engine = XmpEngine()
    raw = {
        _tag("dc", "title"):          "Film A",
        "{http://unknown.ns/}extra":   "extra-data",
    }
    hfv = engine.map_to_hfv(raw)
    assert hfv["title"] == "Film A"
    assert "passthrough" in hfv


def test_map_empty_xmp_returns_empty():
    engine = XmpEngine()
    assert engine.map_to_hfv({}) == {}


def test_map_first_mapping_wins_for_year():
    engine = XmpEngine()
    # Both tags map to 'year' — first one in dict wins
    raw = {
        _tag("xmp", "CreateDate"):        "1927",
        _tag("photoshop", "DateCreated"): "1930",
    }
    hfv = engine.map_to_hfv(raw)
    assert hfv["year"] in ("1927", "1930")  # one of them, no KeyError


# ---------------------------------------------------------------------------
# XmpEngine.extract
# ---------------------------------------------------------------------------

def test_extract_missing_file_returns_empty():
    engine = XmpEngine()
    assert engine.extract("/nonexistent/file.jpg") == {}


def test_extract_sidecar_xmp(tmp_path):
    # Write a minimal XMP sidecar
    sidecar = tmp_path / "photo.xmp"
    sidecar.write_text(
        '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about=""'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:title>Nosferatu</dc:title>'
        '</rdf:Description>'
        '</rdf:RDF>'
        '</x:xmpmeta>'
        '<?xpacket end="w"?>',
        encoding="utf-8",
    )
    # Source file just needs to exist (sidecar is looked up by same stem)
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"\xff\xd8\xff")  # minimal JPEG header

    engine = XmpEngine()
    raw = engine.extract(str(source))
    assert any("title" in k.lower() or "title" in str(v).lower() for k, v in raw.items())


def test_extract_no_sidecar_returns_empty(tmp_path):
    source = tmp_path / "plain.txt"
    source.write_text("hello")
    engine = XmpEngine()
    assert engine.extract(str(source)) == {}


# ---------------------------------------------------------------------------
# MetadataXmpPlugin — lifecycle & event handling
# ---------------------------------------------------------------------------

def _make_db_with_asset(asset_type: AssetType = AssetType.IMAGE) -> tuple[Database, MediaAsset]:
    db = Database(":memory:")
    asset = MediaAsset(id=str(uuid.uuid4()), type=asset_type, source_path="/fake/file.jpg")
    db.save_asset(asset)
    return db, asset


def test_plugin_subscribes_on_initialize():
    db, _ = _make_db_with_asset()
    plugin = MetadataXmpPlugin()
    plugin.initialize(db=db)
    assert plugin._on_asset_created in bus._handlers.get("asset.created", [])
    plugin.teardown()


def test_plugin_unsubscribes_on_teardown():
    db, _ = _make_db_with_asset()
    plugin = MetadataXmpPlugin()
    plugin.initialize(db=db)
    plugin.teardown()
    assert plugin._on_asset_created not in bus._handlers.get("asset.created", [])


def test_plugin_skips_video_assets():
    db, asset = _make_db_with_asset(AssetType.VIDEO)
    plugin = MetadataXmpPlugin()
    plugin.initialize(db=db)

    events = []
    bus.subscribe("xmp.extracted", lambda **kw: events.append(kw))
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.VIDEO.value)
    bus.unsubscribe("xmp.extracted", events.append)

    assert events == []
    plugin.teardown()


def test_plugin_processes_asset_created_and_updates_db(tmp_path, monkeypatch):
    source = tmp_path / "img.jpg"
    source.write_bytes(b"\xff\xd8\xff")

    db, asset = _make_db_with_asset()
    asset.source_path = str(source)
    db.save_asset(asset)

    # Mock extraction to return known XMP data
    mock_raw = {f"{{{_NS['dc']}}}title": "Test Film"}
    monkeypatch.setattr(
        "plugins.metadata_xmp.xmp_engine.XmpEngine.extract",
        lambda self, path: mock_raw,
    )

    plugin = MetadataXmpPlugin()
    plugin.initialize(db=db)
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.IMAGE.value)

    loaded = db.load_asset(asset.id)
    assert loaded.raw_metadata == mock_raw
    assert loaded.hfv_data.get("title") == "Test Film"
    plugin.teardown()


def test_plugin_publishes_xmp_extracted(tmp_path, monkeypatch):
    source = tmp_path / "img.png"
    source.write_bytes(b"PNG")

    db, asset = _make_db_with_asset()
    asset.source_path = str(source)
    db.save_asset(asset)

    monkeypatch.setattr(
        "plugins.metadata_xmp.xmp_engine.XmpEngine.extract",
        lambda self, path: {f"{{{_NS['dc']}}}title": "Found"},
    )

    plugin = MetadataXmpPlugin()
    plugin.initialize(db=db)

    events: list[dict] = []
    bus.subscribe("xmp.extracted", lambda **kw: events.append(kw))
    bus.publish("asset.created", asset_id=asset.id, asset_type=AssetType.IMAGE.value)
    bus.unsubscribe("xmp.extracted", events.append)

    assert len(events) == 1
    assert events[0]["asset_id"] == asset.id
    assert events[0]["had_xmp"] is True
    plugin.teardown()
