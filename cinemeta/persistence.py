from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from .domain.assets import AssetStatus, AssetType, MediaAsset


_SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    source_path TEXT NOT NULL,
    raw_metadata TEXT NOT NULL DEFAULT '{}',
    hfv_data    TEXT NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'PENDING',
    parent_id   TEXT REFERENCES assets(id)
);

CREATE TABLE IF NOT EXISTS relations (
    parent_id   TEXT NOT NULL REFERENCES assets(id),
    child_id    TEXT NOT NULL REFERENCES assets(id),
    relation    TEXT NOT NULL DEFAULT 'contains',
    PRIMARY KEY (parent_id, child_id)
);
"""


class Database:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save_asset(self, asset: MediaAsset) -> None:
        self._conn.execute(
            """INSERT INTO assets (id, type, source_path, raw_metadata, hfv_data, status, parent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 type=excluded.type, source_path=excluded.source_path,
                 raw_metadata=excluded.raw_metadata, hfv_data=excluded.hfv_data,
                 status=excluded.status, parent_id=excluded.parent_id""",
            (
                asset.id, asset.type.value, asset.source_path,
                json.dumps(asset.raw_metadata), json.dumps(asset.hfv_data),
                asset.status.value, asset.parent_id,
            ),
        )
        self._conn.commit()

    def load_asset(self, asset_id: str) -> MediaAsset | None:
        row = self._conn.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if row is None:
            return None
        return MediaAsset(
            id=row["id"],
            type=AssetType(row["type"]),
            source_path=row["source_path"],
            raw_metadata=json.loads(row["raw_metadata"]),
            hfv_data=json.loads(row["hfv_data"]),
            status=AssetStatus(row["status"]),
            parent_id=row["parent_id"],
        )

    def all_assets(self) -> list[MediaAsset]:
        rows = self._conn.execute("SELECT * FROM assets").fetchall()
        return [self.load_asset(r["id"]) for r in rows]  # type: ignore[misc]

    def close(self) -> None:
        self._conn.close()
