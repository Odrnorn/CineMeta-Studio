from __future__ import annotations
import json
import uuid
from pathlib import Path

import pytest

from cinemeta.domain.assets import AssetStatus, AssetType, MediaAsset
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from plugins.universal_export.plugin import CatalogModel, UniversalExportPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validated_asset(db: Database, title: str = "Metropolis") -> MediaAsset:
    asset = MediaAsset(
        id=str(uuid.uuid4()),
        type=AssetType.IMAGE,
        source_path=f"/fake/{title.lower()}.jpg",
    )
    asset.status = AssetStatus.VALIDATED
    asset.hfv_data = {"title": title, "year": "1927"}
    db.save_asset(asset)
    return asset


def _plugin(db: Database) -> UniversalExportPlugin:
    p = UniversalExportPlugin()
    p.initialize(db=db)
    return p


# ---------------------------------------------------------------------------
# A — Plugin lifecycle
# ---------------------------------------------------------------------------

def test_plugin_subscribes_on_initialize():
    db = Database(":memory:")
    p = _plugin(db)
    assert p._on_asset_validated in bus._handlers.get("asset.validated", [])
    p.teardown()


def test_plugin_unsubscribes_on_teardown():
    db = Database(":memory:")
    p = _plugin(db)
    p.teardown()
    assert p._on_asset_validated not in bus._handlers.get("asset.validated", [])


def test_plugin_has_workbench():
    db = Database(":memory:")
    p = _plugin(db)
    assert len(p.workbenches) == 1
    assert p.workbenches[0].id == "universal_export"
    p.teardown()


# ---------------------------------------------------------------------------
# B — Pre-population on initialize
# ---------------------------------------------------------------------------

def test_initialize_loads_existing_validated_assets():
    db = Database(":memory:")
    a1 = _validated_asset(db, "Metropolis")
    a2 = _validated_asset(db, "Nosferatu")
    # Third asset — not validated
    a3 = MediaAsset(id=str(uuid.uuid4()), type=AssetType.IMAGE, source_path="/f.jpg")
    db.save_asset(a3)

    p = _plugin(db)
    assert p.catalog_model.rowCount() == 2
    p.teardown()


def test_asset_validated_event_adds_to_catalog():
    db = Database(":memory:")
    p = _plugin(db)
    assert p.catalog_model.rowCount() == 0

    asset = _validated_asset(db)
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")
    assert p.catalog_model.rowCount() == 1
    p.teardown()


def test_duplicate_asset_not_added_twice():
    db = Database(":memory:")
    asset = _validated_asset(db)
    p = _plugin(db)
    # Trigger twice
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")
    assert p.catalog_model.rowCount() == 1
    p.teardown()


# ---------------------------------------------------------------------------
# C — CatalogModel roles
# ---------------------------------------------------------------------------

def test_catalog_model_data_roles():
    db = Database(":memory:")
    p = _plugin(db)
    asset = _validated_asset(db, "Metropolis")
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")

    UserRole = 0x0100
    idx = p.catalog_model.index(0, 0)
    assert p.catalog_model.data(idx, UserRole + 1) == asset.id      # assetId
    assert p.catalog_model.data(idx, UserRole + 3) == "Metropolis"  # title
    assert p.catalog_model.data(idx, UserRole + 4) == "1927"        # year
    assert p.catalog_model.data(idx, UserRole + 6) is True          # selected
    p.teardown()


def test_set_selected_toggles_item():
    db = Database(":memory:")
    p = _plugin(db)
    asset = _validated_asset(db)
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Film")

    p.catalog_model.set_selected(asset.id, False)
    entries = p.catalog_model.selected_entries()
    assert len(entries) == 0

    p.catalog_model.set_selected(asset.id, True)
    entries = p.catalog_model.selected_entries()
    assert len(entries) == 1
    p.teardown()


# ---------------------------------------------------------------------------
# D — export() writes file
# ---------------------------------------------------------------------------

def test_export_writes_json_file(tmp_path):
    db = Database(":memory:")
    p = _plugin(db)
    out = tmp_path / "export.json"
    entries = [{"assetId": "abc", "title": "Metropolis"}]
    p.export(entries, str(out))

    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["assets"][0]["title"] == "Metropolis"
    p.teardown()


def test_export_creates_parent_dirs(tmp_path):
    db = Database(":memory:")
    p = _plugin(db)
    out = tmp_path / "sub" / "dir" / "out.json"
    p.export([], str(out))
    assert out.exists()
    p.teardown()


def test_export_handles_unicode_path(tmp_path):
    """Paths with umlauts (like on this machine) must not fail."""
    db = Database(":memory:")
    p = _plugin(db)
    out = tmp_path / "Prüfung" / "export.json"
    p.export([{"title": "Über Film"}], str(out))
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["assets"][0]["title"] == "Über Film"
    p.teardown()


# ---------------------------------------------------------------------------
# E — export_to() slot
# ---------------------------------------------------------------------------

def test_export_to_publishes_export_completed(tmp_path):
    db = Database(":memory:")
    asset = _validated_asset(db)
    p = _plugin(db)
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")

    events: list[dict] = []
    def _h(**kw): events.append(kw)
    bus.subscribe("export.completed", _h)
    p.export_to("json-ld", str(tmp_path / "out.json"))
    bus.unsubscribe("export.completed", _h)

    assert len(events) == 1
    assert events[0]["asset_count"] == 1
    assert events[0]["format_id"] == "json-ld"
    p.teardown()


def test_export_to_empty_path_sets_error_status():
    db = Database(":memory:")
    p = _plugin(db)
    p.export_to("csv", "")
    assert "Fehler" in p.last_status()
    p.teardown()


def test_export_to_empty_catalog_sets_error_status(tmp_path):
    db = Database(":memory:")
    p = _plugin(db)
    p.export_to("csv", str(tmp_path / "out.csv"))
    assert "Fehler" in p.last_status()
    p.teardown()


def test_export_to_success_sets_ok_status(tmp_path):
    db = Database(":memory:")
    asset = _validated_asset(db)
    p = _plugin(db)
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")
    p.export_to("json-ld", str(tmp_path / "out.json"))
    assert p.last_status().startswith("✓")
    p.teardown()
