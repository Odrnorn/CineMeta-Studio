from __future__ import annotations
import io
from pathlib import Path

from PIL import Image, UnidentifiedImageError

try:
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage
    from PySide6.QtQuick import QQuickImageProvider
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

_FALLBACK_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ThumbnailRenderer:
    """Generate PNG thumbnail bytes using Pillow. No Qt dependency."""

    def generate(self, source_path: str, size: tuple[int, int] = (256, 256)) -> bytes:
        try:
            with Image.open(source_path) as img:
                img = img.convert("RGBA")
                img.thumbnail(size, Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
        except (OSError, UnidentifiedImageError, FileNotFoundError):
            return _FALLBACK_PNG


if _QT_AVAILABLE:
    class ThumbnailImageProvider(QQuickImageProvider):
        """Qt ImageProvider bridging QML image://thumbnails/<asset_id> to Pillow."""

        def __init__(self) -> None:
            super().__init__(QQuickImageProvider.ImageType.Image)
            self._renderer = ThumbnailRenderer()
            # asset_id → source_path, populated by the plugin
            self._path_map: dict[str, str] = {}

        def register_path(self, asset_id: str, source_path: str) -> None:
            self._path_map[asset_id] = source_path

        def requestImage(self, asset_id: str, size: QSize, requested_size: QSize) -> QImage:
            path = self._path_map.get(asset_id, "")
            png_bytes = self._renderer.generate(path)
            image = QImage()
            image.loadFromData(png_bytes, "PNG")
            if not requested_size.isEmpty():
                image = image.scaled(requested_size)
            return image
else:
    class ThumbnailImageProvider:  # type: ignore[no-redef]
        """Stub when PySide6 is not available (e.g. during testing)."""
        def __init__(self) -> None:
            self._renderer = ThumbnailRenderer()
            self._path_map: dict[str, str] = {}

        def register_path(self, asset_id: str, source_path: str) -> None:
            self._path_map[asset_id] = source_path
