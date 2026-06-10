from __future__ import annotations
from pathlib import Path
from lxml import etree

_DEFINITIONS_DIR = Path(__file__).parent / "definitions"


class SchemaManager:
    def __init__(self) -> None:
        self._schemas: dict[str, etree.XMLSchema] = {}

    def load(self, name: str = "hfv-1.0") -> etree.XMLSchema:
        if name not in self._schemas:
            xsd_path = _DEFINITIONS_DIR / f"{name}.xsd"
            if not xsd_path.exists():
                raise FileNotFoundError(f"Schema '{name}' not found at {xsd_path}")
            with xsd_path.open("rb") as f:
                doc = etree.parse(f)
            self._schemas[name] = etree.XMLSchema(doc)
        return self._schemas[name]

    def validate(self, xml_bytes: bytes, name: str = "hfv-1.0") -> list[str]:
        schema = self.load(name)
        doc = etree.fromstring(xml_bytes)
        schema.validate(doc)
        return [str(e) for e in schema.error_log]
