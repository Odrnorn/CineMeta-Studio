from __future__ import annotations
import re
from pathlib import Path
from typing import Any

try:
    from libxmp import XMPFiles as _XMPFiles
    _LIBXMP_AVAILABLE = True
except ImportError:
    _LIBXMP_AVAILABLE = False

from lxml import etree

# XMP namespace URIs
_NS = {
    "dc":            "http://purl.org/dc/elements/1.1/",
    "xmp":           "http://ns.adobe.com/xap/1.0/",
    "photoshop":     "http://ns.adobe.com/photoshop/1.0/",
    "Iptc4xmpCore":  "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/",
    "rdf":           "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "x":             "adobe:ns:meta/",
}

# Maps (namespace_uri, local_name) → HFV field name
_KNOWN: dict[tuple[str, str], str] = {
    (_NS["dc"],           "title"):       "title",
    (_NS["xmp"],          "CreateDate"):  "year",
    (_NS["photoshop"],    "DateCreated"): "year",
    (_NS["photoshop"],    "Country"):     "country",
    (_NS["Iptc4xmpCore"], "CountryName"): "country",
    (_NS["dc"],           "creator"):     "director",
    (_NS["photoshop"],    "Credit"):      "director",
}

_YEAR_RE = re.compile(r"(\d{4})")


def _first_text(el: etree._Element) -> str:
    """Return the first non-empty text from an element or its rdf:Alt/rdf:Seq children."""
    for child in el.iter():
        if child.text and child.text.strip():
            return child.text.strip()
    return ""


def _parse_xmp_xml(xml_bytes: bytes) -> dict[str, Any]:
    """Parse raw XMP XML bytes and return a flat dict keyed by '{ns_uri}local'."""
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError:
        return {}

    result: dict[str, Any] = {}
    for el in root.iter():
        if el.tag and el.tag.startswith("{") and el.text and el.text.strip():
            result[el.tag] = el.text.strip()
        for attr_name, attr_val in el.attrib.items():
            if attr_name.startswith("{") and attr_val.strip():
                result[attr_name] = attr_val.strip()
    return result


def _extract_sidecar(source_path: str) -> dict[str, Any]:
    """Look for a .xmp sidecar file next to *source_path* and parse it."""
    sidecar = Path(source_path).with_suffix(".xmp")
    if not sidecar.exists():
        return {}
    try:
        return _parse_xmp_xml(sidecar.read_bytes())
    except OSError:
        return {}


def _extract_embedded_jpeg(source_path: str) -> dict[str, Any]:
    """Extract XMP packet embedded in a JPEG APP1 marker."""
    _XMP_MARKER = b"http://ns.adobe.com/xap/1.0/\x00"
    try:
        data = Path(source_path).read_bytes()
    except OSError:
        return {}

    idx = data.find(_XMP_MARKER)
    if idx == -1:
        return {}

    start = idx + len(_XMP_MARKER)
    end = data.find(b"<?xpacket end", start)
    end = data.find(b">", end) + 1 if end != -1 else start + 65536
    return _parse_xmp_xml(data[start:end])


class XmpEngine:
    """Extract XMP metadata and map it to HFV-1.0 fields."""

    def extract(self, source_path: str) -> dict[str, Any]:
        """Return raw XMP as a flat dict keyed by '{ns_uri}localName'.

        Strategy (in order):
        1. python-xmp-toolkit (if Exempi available)
        2. Embedded JPEG XMP packet
        3. .xmp sidecar file
        """
        if not Path(source_path).exists():
            return {}

        # 1. libxmp (requires Exempi)
        if _LIBXMP_AVAILABLE:
            try:
                xf = _XMPFiles(file_path=source_path)
                xmp = xf.get_xmp()
                xf.close_file()
                if xmp:
                    result: dict[str, Any] = {}
                    for schema_ns, prop_name, prop_value, _ in xmp:
                        result[f"{{{schema_ns}}}{prop_name}"] = prop_value
                    return result
            except Exception:
                pass

        # 2. Embedded JPEG XMP packet
        suffix = Path(source_path).suffix.lower()
        if suffix in (".jpg", ".jpeg"):
            embedded = _extract_embedded_jpeg(source_path)
            if embedded:
                return embedded

        # 3. Sidecar
        return _extract_sidecar(source_path)

    def map_to_hfv(self, raw_xmp: dict[str, Any]) -> dict[str, Any]:
        """Map known XMP tags to HFV-1.0 fields; everything else goes to 'passthrough'."""
        hfv: dict[str, Any] = {}
        passthrough: dict[str, Any] = {}

        for tag, value in raw_xmp.items():
            # Parse Clark notation: {ns_uri}localName
            if tag.startswith("{"):
                close = tag.index("}")
                ns_uri = tag[1:close]
                local = tag[close + 1:]
            else:
                ns_uri, local = "", tag

            hfv_field = _KNOWN.get((ns_uri, local))
            if hfv_field:
                if hfv_field == "year":
                    m = _YEAR_RE.search(str(value))
                    hfv["year"] = m.group(1) if m else str(value)
                elif hfv_field in hfv:
                    pass  # first mapping wins (priority order in _KNOWN)
                else:
                    hfv[hfv_field] = str(value).strip()
            else:
                passthrough[tag] = value

        if passthrough:
            hfv["passthrough"] = passthrough

        return hfv
