from cinemeta.domain.assets import AssetStatus, AssetType, MediaAsset


def test_create_image_asset():
    a = MediaAsset(id="a1", type=AssetType.IMAGE, source_path="/img/foo.jpg")
    assert a.id == "a1"
    assert a.type == AssetType.IMAGE
    assert a.status == AssetStatus.PENDING
    assert a.parent_id is None


def test_asset_type_enum_values():
    assert AssetType("VIDEO") == AssetType.VIDEO
    assert AssetType("VIDEO_FRAME") == AssetType.VIDEO_FRAME


def test_asset_status_enum_values():
    assert AssetStatus("GREEN") == AssetStatus.GREEN
    assert AssetStatus("VALIDATED") == AssetStatus.VALIDATED


def test_hfv_data_defaults_to_empty_dict():
    a = MediaAsset(id="x", type=AssetType.TEXT, source_path="/doc.txt")
    assert a.hfv_data == {}
    assert a.raw_metadata == {}
