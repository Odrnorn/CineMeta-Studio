from __future__ import annotations
from typing import Iterator
from .assets import MediaAsset


class AssetHierarchy:
    def __init__(self) -> None:
        self._assets: dict[str, MediaAsset] = {}
        self._children: dict[str, list[str]] = {}

    def add(self, asset: MediaAsset) -> None:
        self._assets[asset.id] = asset
        self._children.setdefault(asset.id, [])
        if asset.parent_id is not None:
            self._children.setdefault(asset.parent_id, []).append(asset.id)

    def add_child(self, parent_id: str, child: MediaAsset) -> None:
        child.parent_id = parent_id
        self.add(child)

    def get(self, asset_id: str) -> MediaAsset | None:
        return self._assets.get(asset_id)

    def get_children(self, parent_id: str) -> list[MediaAsset]:
        return [self._assets[cid] for cid in self._children.get(parent_id, []) if cid in self._assets]

    def get_root_assets(self) -> list[MediaAsset]:
        return [a for a in self._assets.values() if a.parent_id is None]

    def walk(self, root_id: str) -> Iterator[MediaAsset]:
        if root_id not in self._assets:
            return
        yield self._assets[root_id]
        for child in self.get_children(root_id):
            yield from self.walk(child.id)
