import re
from typing import Any

from .attribute_templates import GENERIC_EXTRACTORS, template_for

UNIT_ALIASES = {
    "millimetre": "mm",
    "millimeter": "mm",
    "millimeters": "mm",
    "mm.": "mm",
    "volt": "v",
    "volts": "v",
    "kilovolt": "kv",
    "kilovolts": "kv",
    "sqmm": "sq mm",
    "sq.mm": "sq mm",
    "mm2": "sq mm",
    "kg/cm2": "bar",
}

# Domain shorthand -> its expansion. CPSEs abbreviate heavily and inconsistently;
# expanding to a common phrase makes "DGBB 6205 2Z" and "deep groove ball bearing
# 6205 ZZ" align lexically and semantically. Applied on word boundaries only.
ABBREVIATIONS = {
    "dgbb": "deep groove ball bearing",
    "srb": "spherical roller bearing",
    "crb": "cylindrical roller bearing",
    "brg": "bearing",
    "brgs": "bearings",
    "sgl": "single",
    "sw": "socket weld",
    "bw": "butt weld",
    "rf": "raised face",
    "ff": "flat face",
    "cs": "carbon steel",
    "ss": "stainless steel",
    "ms": "mild steel",
    "fs": "forged steel",
    "gi": "galvanised iron",
    "hdg": "hot dip galvanised",
    "galv": "galvanised",
    "galvanized": "galvanised",
    "smls": "seamless",
    "nb": "nominal bore",
    "nps": "nominal bore",
    "dia": "diameter",
    "od": "outer diameter",
    "thk": "thick",
    "mov": "motor operated valve",
    "nrv": "non return valve",
    "gt": "gate",
    "vlv": "valve",
    "al": "aluminium",
    "alu": "aluminium",
    "cu": "copper",
    "cond": "conductor",
    "armd": "armoured",
    "armored": "armoured",
    "ht": "high tension",
    "lt": "low tension",
    "3ph": "three phase",
    "3-ph": "three phase",
    "1ph": "single phase",
    "ptfe": "teflon",
    "caf": "compressed asbestos fibre",
    "grs": "grease",
    "lub": "lubricating",
    "hyd": "hydraulic",
    "qty": "quantity",
}


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9./+\-# ]+", " ", text)
    # Treat an in-word hyphen as a separator so "6205-2Z" and "6205 ZZ" align.
    text = re.sub(r"(?<=[a-z0-9])-(?=[a-z0-9])", " ", text)
    text = re.sub(r"\s+", " ", text)
    for source, target in UNIT_ALIASES.items():
        text = re.sub(rf"\b{re.escape(source)}\b", target, text)
    # "CL150" / "CL 300" -> "class 150" (pressure class in valve/flange descriptions)
    text = re.sub(r"\bcl\.?\s*(\d{2,4})\b", r"class \1", text)
    for source, target in ABBREVIATIONS.items():
        text = re.sub(rf"\b{re.escape(source)}\b", target, text)
    # Normalize common bearing closure spelling: 2Z and ZZ are retained as comparable tokens.
    text = re.sub(r"\b2z\b", "zz", text)
    return text.strip()


def normalize_uom(uom: str | None) -> str | None:
    """Canonical unit-of-measure *name*, resolved against UN/CEFACT Rec 20.

    e.g. ``NOS`` / ``No.`` / ``PC`` -> ``each`` (Rec 20 code ``EA``). Kept as a
    thin string API; :func:`app.services.uom_registry.resolve_uom` returns the
    full standard entry (common code, symbol, quantity).
    """
    from .uom_registry import canonical_uom

    return canonical_uom(uom)


def extract_attributes(
    description: str,
    supplied: dict[str, Any] | None = None,
    material_family: str | None = None,
) -> dict[str, Any]:
    """Derive structured attributes from a description.

    When ``material_family`` matches a known template only that family's
    extractors run, which sharpens precision per family. An unknown/absent
    family falls back to the generic extractor set.
    """
    normalized = normalize_text(description)
    attrs: dict[str, Any] = dict(supplied or {})

    template = template_for(material_family)
    extractors = template["extractors"] if template else GENERIC_EXTRACTORS

    for extractor in extractors:
        for key, value in extractor(normalized).items():
            attrs.setdefault(key, value)

    return attrs
