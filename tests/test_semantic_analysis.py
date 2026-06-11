from __future__ import annotations
import json
import uuid

import pytest

from cinemeta.domain.assets import AssetStatus, AssetType, MediaAsset
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from plugins.semantic_analysis.plugin import SemanticAnalysisPlugin, SemanticAssetModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db_with_validated_asset() -> tuple[Database, MediaAsset]:
    db = Database(":memory:")
    asset = MediaAsset(
        id=str(uuid.uuid4()),
        type=AssetType.IMAGE,
        source_path="/fake/photo.jpg",
    )
    asset.status = AssetStatus.VALIDATED
    asset.hfv_data = {"title": "Metropolis", "year": "1927"}
    db.save_asset(asset)
    return db, asset


def _plugin(db: Database) -> SemanticAnalysisPlugin:
    p = SemanticAnalysisPlugin()
    p.initialize(db=db)
    return p


# ---------------------------------------------------------------------------
# A — Plugin lifecycle
# ---------------------------------------------------------------------------

def test_plugin_subscribes_on_initialize():
    db, _ = _db_with_validated_asset()
    p = _plugin(db)
    assert p._on_asset_validated in bus._handlers.get("asset.validated", [])
    p.teardown()


def test_plugin_unsubscribes_on_teardown():
    db, _ = _db_with_validated_asset()
    p = _plugin(db)
    p.teardown()
    assert p._on_asset_validated not in bus._handlers.get("asset.validated", [])


def test_plugin_has_workbench():
    db, _ = _db_with_validated_asset()
    p = _plugin(db)
    assert len(p.workbenches) == 1
    assert p.workbenches[0].id == "semantic_analysis"
    p.teardown()


# ---------------------------------------------------------------------------
# B — Cluster assignment & position
# ---------------------------------------------------------------------------

def test_cluster_assignment_is_deterministic():
    """Same asset_id → same cluster across two independent plugin instances."""
    db, asset = _db_with_validated_asset()
    p1 = _plugin(db)
    p2 = _plugin(db)

    events1: list[dict] = []
    events2: list[dict] = []

    def _handler1(**kw): events1.append(kw)
    def _handler2(**kw): events2.append(kw)

    bus.subscribe("similarity.ready", _handler1)
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")
    bus.unsubscribe("similarity.ready", _handler1)

    # Reset model
    p2.asset_model._items.clear()
    bus.subscribe("similarity.ready", _handler2)
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")
    bus.unsubscribe("similarity.ready", _handler2)

    assert events1[0]["cluster_id"] == events2[0]["cluster_id"]
    p1.teardown(); p2.teardown()


def test_position_is_within_unit_square():
    db, asset = _db_with_validated_asset()
    p = _plugin(db)
    events: list[dict] = []

    def _h(**kw): events.append(kw)
    bus.subscribe("similarity.ready", _h)
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")
    bus.unsubscribe("similarity.ready", _h)

    assert 0.0 <= events[0]["x"] <= 1.0
    assert 0.0 <= events[0]["y"] <= 1.0
    p.teardown()


def test_cluster_id_is_valid():
    db, asset = _db_with_validated_asset()
    p = _plugin(db)
    events: list[dict] = []

    def _h(**kw): events.append(kw)
    bus.subscribe("similarity.ready", _h)
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")
    bus.unsubscribe("similarity.ready", _h)

    assert events[0]["cluster_id"] in (0, 1, 2)
    assert events[0]["cluster_label"] in ("Stummfilm Drama", "Komödie", "Dokumentation")
    p.teardown()


# ---------------------------------------------------------------------------
# C — DB persistence
# ---------------------------------------------------------------------------

def test_semantic_coords_saved_to_db():
    db, asset = _db_with_validated_asset()
    p = _plugin(db)
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")
    loaded = db.load_asset(asset.id)
    assert "semantic" in loaded.hfv_data
    sem = loaded.hfv_data["semantic"]
    assert "cluster_id" in sem and "x" in sem and "y" in sem
    p.teardown()


def test_semantic_does_not_crash_without_db():
    p = SemanticAnalysisPlugin()
    p.initialize(db=None)
    bus.publish("asset.validated", asset_id="test-id", chosen_label="Film")
    p.teardown()


# ---------------------------------------------------------------------------
# D — SemanticAssetModel
# ---------------------------------------------------------------------------

def test_model_row_count_after_validation():
    db, asset = _db_with_validated_asset()
    p = _plugin(db)
    assert p.asset_model.rowCount() == 0
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")
    assert p.asset_model.rowCount() == 1
    p.teardown()


def test_model_data_roles():
    db, asset = _db_with_validated_asset()
    p = _plugin(db)
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")

    from plugins.semantic_analysis.plugin import Qt
    idx = p.asset_model.index(0, 0)
    UserRole = 0x0100
    assert p.asset_model.data(idx, UserRole + 1) == asset.id       # assetId
    assert p.asset_model.data(idx, UserRole + 2) == "Metropolis"   # title
    assert p.asset_model.data(idx, UserRole + 3) in (0, 1, 2)      # clusterId
    assert isinstance(p.asset_model.data(idx, UserRole + 6), float)  # posX
    p.teardown()


def test_model_neighbors_is_valid_json():
    db, asset = _db_with_validated_asset()
    p = _plugin(db)
    bus.publish("asset.validated", asset_id=asset.id, chosen_label="Metropolis")

    UserRole = 0x0100
    idx = p.asset_model.index(0, 0)
    neighbor_json = p.asset_model.data(idx, UserRole + 8)
    neighbors = json.loads(neighbor_json)
    assert isinstance(neighbors, list)
    p.teardown()


# ---------------------------------------------------------------------------
# E — Integration: multiple assets
# ---------------------------------------------------------------------------

def test_three_validations_add_three_model_entries():
    db = Database(":memory:")
    p = SemanticAnalysisPlugin()
    p.initialize(db=db)

    for title in ["Metropolis", "Nosferatu", "Battleship Potemkin"]:
        asset = MediaAsset(id=str(uuid.uuid4()), type=AssetType.IMAGE, source_path="/f.jpg")
        asset.status = AssetStatus.VALIDATED
        asset.hfv_data = {"title": title}
        db.save_asset(asset)
        bus.publish("asset.validated", asset_id=asset.id, chosen_label=title)

    assert p.asset_model.rowCount() == 3
    p.teardown()


def test_neighbors_populated_for_second_asset_in_same_cluster(monkeypatch):
    """After two assets land in the same cluster, the second gets one neighbour."""
    db = Database(":memory:")
    p = SemanticAnalysisPlugin()
    # Force both assets into cluster 0 by patching stable_hash
    original_hash = SemanticAnalysisPlugin._stable_hash
    call_count = [0]

    def _forced_zero(text):
        call_count[0] += 1
        return 0  # always cluster 0, deterministic offset near 0

    monkeypatch.setattr(SemanticAnalysisPlugin, "_stable_hash", staticmethod(_forced_zero))
    p.initialize(db=db)

    for title in ["Film A", "Film B"]:
        asset = MediaAsset(id=str(uuid.uuid4()), type=AssetType.IMAGE, source_path="/f.jpg")
        asset.hfv_data = {"title": title}
        db.save_asset(asset)
        bus.publish("asset.validated", asset_id=asset.id, chosen_label=title)

    # Second asset should have Film A as neighbour
    UserRole = 0x0100
    idx = p.asset_model.index(1, 0)
    neighbors = json.loads(p.asset_model.data(idx, UserRole + 8))
    assert len(neighbors) >= 1
    p.teardown()
