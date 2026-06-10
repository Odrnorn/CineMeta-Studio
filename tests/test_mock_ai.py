from __future__ import annotations
import uuid

import pytest

from cinemeta.domain.assets import AssetStatus, AssetType, MediaAsset
from cinemeta.domain.confidence_logic import AmpelStatus, classify
from cinemeta.event_bus import bus
from cinemeta.persistence import Database
from plugins.mock_ai.plugin import MockAiPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db_with_asset(asset_type: AssetType = AssetType.IMAGE) -> tuple[Database, MediaAsset]:
    db = Database(":memory:")
    asset = MediaAsset(id=str(uuid.uuid4()), type=asset_type, source_path="/fake/photo.jpg")
    db.save_asset(asset)
    return db, asset


def _initialized_plugin(db: Database | None = None) -> MockAiPlugin:
    if db is None:
        db, _ = _db_with_asset()
    plugin = MockAiPlugin()
    plugin.initialize(db=db)
    return plugin


# ---------------------------------------------------------------------------
# analyze_asset
# ---------------------------------------------------------------------------

def test_analyze_asset_returns_candidate_list():
    plugin = _initialized_plugin()
    candidates = plugin.analyze_asset("any-id", {})
    assert isinstance(candidates, list)
    assert all("label" in c and "score" in c for c in candidates)
    plugin.teardown()


def test_analyze_asset_is_deterministic():
    plugin = _initialized_plugin()
    aid = str(uuid.uuid4())
    assert plugin.analyze_asset(aid, {}) == plugin.analyze_asset(aid, {})
    plugin.teardown()


def test_analyze_asset_all_three_scenarios_reachable():
    plugin = _initialized_plugin()
    seen_scenarios = set()
    for _ in range(300):
        aid = str(uuid.uuid4())
        candidates = plugin.analyze_asset(aid, {})
        result = classify(candidates)
        seen_scenarios.add(result.status)
    assert AmpelStatus.GREEN  in seen_scenarios
    assert AmpelStatus.YELLOW in seen_scenarios
    assert AmpelStatus.RED    in seen_scenarios
    plugin.teardown()


# ---------------------------------------------------------------------------
# mock_data scenarios map to correct AmpelStatus
# ---------------------------------------------------------------------------

def _plugin_with_fixed_scenario(scenario_index: int) -> MockAiPlugin:
    plugin = _initialized_plugin()
    # Replace scenarios so we can control which one is picked
    plugin._scenarios = [plugin._scenarios[scenario_index]]
    return plugin


def test_green_scenario_classifies_green():
    plugin = _plugin_with_fixed_scenario(0)
    candidates = plugin.analyze_asset("any", {})
    assert classify(candidates).status == AmpelStatus.GREEN
    plugin.teardown()


def test_yellow_scenario_classifies_yellow():
    plugin = _plugin_with_fixed_scenario(1)
    candidates = plugin.analyze_asset("any", {})
    assert classify(candidates).status == AmpelStatus.YELLOW
    plugin.teardown()


def test_red_scenario_classifies_red():
    plugin = _plugin_with_fixed_scenario(2)
    candidates = plugin.analyze_asset("any", {})
    assert classify(candidates).status == AmpelStatus.RED
    plugin.teardown()


# ---------------------------------------------------------------------------
# Plugin lifecycle — event bus
# ---------------------------------------------------------------------------

def test_plugin_subscribes_on_initialize():
    plugin = _initialized_plugin()
    assert plugin._on_xmp_extracted in bus._handlers.get("xmp.extracted", [])
    plugin.teardown()


def test_plugin_unsubscribes_on_teardown():
    plugin = _initialized_plugin()
    plugin.teardown()
    assert plugin._on_xmp_extracted not in bus._handlers.get("xmp.extracted", [])


# ---------------------------------------------------------------------------
# _on_xmp_extracted
# ---------------------------------------------------------------------------

def test_on_xmp_extracted_updates_asset_status():
    db, asset = _db_with_asset()
    plugin = _initialized_plugin(db)

    bus.publish("xmp.extracted", asset_id=asset.id, hfv_data={}, had_xmp=False)

    loaded = db.load_asset(asset.id)
    assert loaded.status in (AssetStatus.GREEN, AssetStatus.YELLOW, AssetStatus.RED)
    plugin.teardown()


def test_on_xmp_extracted_enqueues_to_validation_model():
    db, asset = _db_with_asset()
    plugin = _initialized_plugin(db)

    bus.publish("xmp.extracted", asset_id=asset.id, hfv_data={}, had_xmp=False)

    assert plugin.validation_model.rowCount() == 1
    plugin.teardown()


def test_on_xmp_extracted_publishes_confidence_ready():
    db, asset = _db_with_asset()
    plugin = _initialized_plugin(db)

    received: list[dict] = []
    bus.subscribe("confidence.ready", lambda **kw: received.append(kw))
    bus.publish("xmp.extracted", asset_id=asset.id, hfv_data={}, had_xmp=False)
    bus.unsubscribe("confidence.ready", received.append)

    assert len(received) == 1
    assert received[0]["asset_id"] == asset.id
    assert received[0]["status"] in ("GREEN", "YELLOW", "RED")
    plugin.teardown()


# ---------------------------------------------------------------------------
# accept()
# ---------------------------------------------------------------------------

def test_accept_sets_validated_status():
    db, asset = _db_with_asset()
    plugin = _initialized_plugin(db)
    bus.publish("xmp.extracted", asset_id=asset.id, hfv_data={}, had_xmp=False)

    plugin.accept(asset.id, "Metropolis (1927)")

    loaded = db.load_asset(asset.id)
    assert loaded.status == AssetStatus.VALIDATED
    assert loaded.hfv_data.get("title") == "Metropolis (1927)"
    plugin.teardown()


def test_accept_removes_from_queue():
    db, asset = _db_with_asset()
    plugin = _initialized_plugin(db)
    bus.publish("xmp.extracted", asset_id=asset.id, hfv_data={}, had_xmp=False)
    assert plugin.validation_model.rowCount() == 1

    plugin.accept(asset.id, "Some Film")

    assert plugin.validation_model.rowCount() == 0
    plugin.teardown()


def test_accept_publishes_asset_validated():
    db, asset = _db_with_asset()
    plugin = _initialized_plugin(db)
    bus.publish("xmp.extracted", asset_id=asset.id, hfv_data={}, had_xmp=False)

    events: list[dict] = []
    bus.subscribe("asset.validated", lambda **kw: events.append(kw))
    plugin.accept(asset.id, "Nosferatu (1922)")
    bus.unsubscribe("asset.validated", events.append)

    assert len(events) == 1
    assert events[0]["asset_id"] == asset.id
    assert events[0]["chosen_label"] == "Nosferatu (1922)"
    plugin.teardown()


def test_accept_with_unknown_asset_does_not_crash():
    plugin = _initialized_plugin()
    plugin.accept("non-existent-id", "Label")  # should not raise
    plugin.teardown()
