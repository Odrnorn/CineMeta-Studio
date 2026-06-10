from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AssetType(Enum):
    IMAGE = "IMAGE"
    TEXT = "TEXT"
    VIDEO = "VIDEO"
    VIDEO_FRAME = "VIDEO_FRAME"


class AssetStatus(Enum):
    PENDING = "PENDING"
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    VALIDATED = "VALIDATED"


@dataclass
class MediaAsset:
    id: str
    type: AssetType
    source_path: str
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    hfv_data: dict[str, Any] = field(default_factory=dict)
    status: AssetStatus = AssetStatus.PENDING
    parent_id: str | None = None
