"""Family-aware attribute templates.

Each material family declares:

- ``attributes`` : attribute keys that matter for that family (documentation / UI hint)
- ``critical``   : the subset whose *conflict* should strongly reduce a match score
- ``extractors`` : callables run against the normalized description that return
                   ``{attribute: value}`` fragments

A material whose family is unknown falls back to :data:`GENERIC_EXTRACTORS` and to
the union of every family's critical keys, so behaviour degrades safely.
"""

from __future__ import annotations

import re
from typing import Any, Callable

Extractor = Callable[[str], dict[str, Any]]


# ---------------------------------------------------------------------------
# Extractors (operate on already normalized, lower-cased text)
# ---------------------------------------------------------------------------

def _bearing_extractor(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    match = re.search(r"\b(\d{4,5})(?:[- ]?(zz|2rs|rs|z))?\b", text)
    if match:
        out["series"] = match.group(1)
        if match.group(2):
            out["closure"] = match.group(2)
    return out


def _dimensions_extractor(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*[x×]\s*"
        r"(\d+(?:\.\d+)?)\s*(mm|cm|m)?\b",
        text,
    )
    if match:
        out["dimensions"] = [float(match.group(i)) for i in range(1, 4)]
        if match.group(4):
            out["dimension_unit"] = match.group(4)
    return out


def _voltage_extractor(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(kv|v)\b", text)
    if match:
        out["voltage"] = float(match.group(1))
        out["voltage_unit"] = match.group(2)
    return out


def _cable_extractor(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cores = re.search(r"\b(\d+)\s*(?:c|core|cores|p|pair|pr)\b", text)
    if cores:
        out["cores"] = int(cores.group(1))
    csa = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:sq\s*mm|mm2|sqmm)\b", text)
    if csa:
        out["conductor_csa_sqmm"] = float(csa.group(1))
    if "copper" in text or re.search(r"\bcu\b", text):
        out["conductor"] = "cu"
    elif "aluminium" in text or "aluminum" in text or re.search(r"\bal\b", text):
        out["conductor"] = "al"
    return out


# Standard nominal-bore ladder (DN, mm). Inch and raw mm sizes are snapped onto
# it so "2 inch", "50 mm" and "50 NB" all resolve to the same nominal bore.
_DN_LADDER = [
    6, 8, 10, 15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150,
    200, 250, 300, 350, 400, 450, 500, 600,
]


def _snap_dn(mm: float) -> float:
    return float(min(_DN_LADDER, key=lambda dn: abs(dn - mm)))


def _bore_mm(text: str) -> float | None:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:mm|nb|nps|nd)\b", text)
    if match:
        return _snap_dn(float(match.group(1)))
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:inch|inches)\b", text)
    if match:
        return _snap_dn(float(match.group(1)) * 25.4)
    return None


def _valve_extractor(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    bore = _bore_mm(text)
    if bore is not None:
        out["nominal_bore_mm"] = bore
    rating = re.search(r"\b(?:class\s*|cl\s*|pn\s*)(\d{2,4})\s*#?\b", text)
    if not rating:
        rating = re.search(r"\b(\d{2,4})\s*#", text)
    if rating:
        out["pressure_rating"] = f"class {rating.group(1)}"
    if re.search(r"\bbf valve\b", text) or "butterfly" in text:
        out["valve_type"] = "butterfly"
    elif re.search(r"\bnrv\b", text) or "non return" in text or "non-return" in text:
        out["valve_type"] = "check"
    else:
        for kind in ("gate", "globe", "ball", "check", "needle", "plug"):
            if re.search(rf"\b{kind}\b", text):
                out["valve_type"] = kind
                break
    return out


def _fastener_extractor(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    thread = re.search(r"\bm(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\b", text)
    if thread:
        out["thread"] = f"m{thread.group(1)}"
        out["length_mm"] = float(thread.group(2))
    grade = re.search(
        r"\b(?:grade|gr|property class|class|pc)\s*(\d(?:\.\d)?)\b", text
    )
    if grade:
        out["material_grade"] = grade.group(1)
    return out


def _pipe_extractor(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    bore = _bore_mm(text)
    if bore is not None:
        out["nominal_bore_mm"] = bore
    sch = re.search(r"\bsch(?:edule)?\s*(\d+)\s*s?\b", text)
    if sch:
        out["schedule"] = f"sch{sch.group(1)}"
    if re.search(r"\bss\s*316", text):
        out["pipe_material"] = "ss316"
    elif re.search(r"\bss\s*304", text):
        out["pipe_material"] = "ss304"
    elif re.search(r"\b(a106|a53|a333|carbon steel|cs)\b", text):
        out["pipe_material"] = "cs"
    return out


def _motor_extractor(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    power = re.search(r"\b(\d+(?:\.\d+)?)\s*kw\b", text)
    if power:
        out["power_kw"] = float(power.group(1))
    poles = re.search(r"\b(\d+)\s*pole\b", text) or re.search(r"\b(\d+)p\b", text)
    if poles:
        out["poles"] = int(poles.group(1))
    return out


def _plate_extractor(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    thickness = re.search(r"\b(\d+(?:\.\d+)?)\s*mm\b", text)
    if thickness:
        out["thickness_mm"] = float(thickness.group(1))
    grade = re.search(
        r"\b(e250\w*|e350\w*|fe\s*500\s*d?|is\s*2062|is\s*1786)\b", text
    )
    if grade:
        out["steel_grade"] = grade.group(1).replace(" ", "")
    return out


# ---------------------------------------------------------------------------
# Family registry
# ---------------------------------------------------------------------------

MATERIAL_FAMILIES: dict[str, dict[str, Any]] = {
    "bearing": {
        "attributes": ["series", "closure", "dimensions", "dimension_unit"],
        "critical": ["series", "closure", "dimensions", "dimension_unit"],
        "extractors": [_bearing_extractor, _dimensions_extractor],
    },
    "cable": {
        "attributes": [
            "cores",
            "conductor_csa_sqmm",
            "conductor",
            "voltage",
            "voltage_unit",
        ],
        "critical": ["cores", "conductor_csa_sqmm", "voltage", "voltage_unit"],
        "extractors": [_cable_extractor, _voltage_extractor],
    },
    "valve": {
        "attributes": [
            "valve_type",
            "nominal_bore_mm",
            "pressure_rating",
            "material_grade",
        ],
        "critical": ["valve_type", "nominal_bore_mm", "pressure_rating"],
        "extractors": [_valve_extractor, _dimensions_extractor],
    },
    "fastener": {
        "attributes": ["thread", "length_mm", "material_grade"],
        "critical": ["thread", "material_grade"],
        "extractors": [_fastener_extractor],
    },
    "pipe": {
        "attributes": ["nominal_bore_mm", "schedule", "pipe_material"],
        "critical": ["nominal_bore_mm", "schedule", "pipe_material"],
        "extractors": [_pipe_extractor],
    },
    "motor": {
        "attributes": ["power_kw", "poles", "voltage", "voltage_unit"],
        "critical": ["power_kw", "poles"],
        "extractors": [_motor_extractor, _voltage_extractor],
    },
    "plate": {
        "attributes": ["thickness_mm", "steel_grade"],
        "critical": ["thickness_mm", "steel_grade"],
        "extractors": [_plate_extractor],
    },
}

# Applied when the family is unknown; keeps the pre-template behaviour.
GENERIC_EXTRACTORS: list[Extractor] = [
    _bearing_extractor,
    _dimensions_extractor,
    _voltage_extractor,
]

_FAMILY_ALIASES = {
    "bearings": "bearing",
    "brg": "bearing",
    "ball bearing": "bearing",
    "roller bearing": "bearing",
    "deep groove ball bearing": "bearing",
    "cables": "cable",
    "power cable": "cable",
    "control cable": "cable",
    "instrumentation cable": "cable",
    "wire": "cable",
    "valves": "valve",
    "fasteners": "fastener",
    "bolt": "fastener",
    "bolts": "fastener",
    "screw": "fastener",
    "screws": "fastener",
    "nut": "fastener",
    "pipes": "pipe",
    "piping": "pipe",
    "tube": "pipe",
    "motors": "motor",
    "electric motor": "motor",
    "induction motor": "motor",
    "plates": "plate",
    "ms plate": "plate",
    "steel plate": "plate",
    "structural steel": "plate",
}


def resolve_family(material_family: str | None) -> str | None:
    """Map a free-text family label to a known template key, or ``None``."""
    if not material_family:
        return None
    key = material_family.strip().lower()
    if key in MATERIAL_FAMILIES:
        return key
    return _FAMILY_ALIASES.get(key)


def template_for(material_family: str | None) -> dict[str, Any] | None:
    family = resolve_family(material_family)
    return MATERIAL_FAMILIES.get(family) if family else None


def critical_keys(material_family: str | None = None) -> set[str]:
    """Critical attribute keys for a family (union of all families if unknown)."""
    template = template_for(material_family)
    if template:
        return set(template["critical"])
    keys: set[str] = set()
    for tpl in MATERIAL_FAMILIES.values():
        keys.update(tpl["critical"])
    return keys
