"""Unit-of-measure harmonization against UN/CEFACT Recommendation 20.

CPSEs record the same physical unit in dozens of local ways (``EA`` / ``NOS`` /
``No.`` / ``PC`` / ``Nr`` ...). We map every one of them onto an authoritative
Rec 20 *common code*, so harmonized data speaks a single international vocabulary
instead of one team's house style.
"""

from functools import lru_cache

from .reference_data import load_csv


@lru_cache(maxsize=1)
def _registry() -> dict[str, dict]:
    """Rec 20 common code -> {code, name, symbol, quantity}."""
    return {row["code"].upper(): row for row in load_csv("unece_rec20_units.csv")}


# Free-text local unit -> Rec 20 common code. The registry itself has no aliases;
# this is the CPSE-vocabulary layer on top of it.
_ALIASES = {
    # count
    "ea": "EA", "each": "EA", "no": "EA", "no.": "EA", "nos": "EA", "nos.": "EA",
    "nr": "EA", "num": "EA", "number": "EA", "unit": "EA", "units": "EA",
    "u": "EA", "pc": "EA", "pcs": "EA", "pce": "EA", "piece": "EA",
    "pieces": "EA", "qty": "EA", "item": "EA", "items": "EA",
    # articles / sets / pairs
    "set": "SET", "sets": "SET", "st": "SET", "kit": "SET",
    "pr": "PR", "pair": "PR", "pairs": "PR", "prs": "PR",
    "dz": "DZN", "doz": "DZN", "dozen": "DZN",
    # length
    "m": "MTR", "mtr": "MTR", "mtrs": "MTR", "mts": "MTR", "mt.": "MTR",
    "meter": "MTR", "metre": "MTR", "rmt": "MTR", "rm": "MTR", "r.mtr": "MTR",
    "mm": "MMT", "millimetre": "MMT", "millimeter": "MMT",
    "cm": "CMT", "km": "KMT", "kms": "KMT",
    "ft": "FOT", "feet": "FOT", "foot": "FOT", "inch": "INH", "in": "INH",
    # mass
    "kg": "KGM", "kgs": "KGM", "kg.": "KGM", "kilogram": "KGM",
    "kilograms": "KGM", "kgm": "KGM",
    "g": "GRM", "gm": "GRM", "gms": "GRM", "gram": "GRM", "grams": "GRM",
    "mg": "MGM",
    "mt": "TNE", "ton": "TNE", "tons": "TNE", "tonne": "TNE", "tonnes": "TNE",
    "te": "TNE", "t": "TNE", "m.ton": "TNE", "mton": "TNE",
    "quintal": "DTN", "qtl": "DTN", "q": "DTN",
    # volume
    "l": "LTR", "ltr": "LTR", "ltrs": "LTR", "lit": "LTR", "litre": "LTR",
    "litres": "LTR", "liter": "LTR", "liters": "LTR",
    "ml": "MLT", "kl": "MTQ",
    "cum": "MTQ", "m3": "MTQ", "cu.m": "MTQ", "cubic metre": "MTQ",
    "gal": "GLL", "gallon": "GLL", "gallons": "GLL",
    "bbl": "BLL", "barrel": "BLL", "barrels": "BLL",
    # area
    "sqm": "MTK", "sq.m": "MTK", "sqmt": "MTK", "m2": "MTK",
    "square metre": "MTK", "sq metre": "MTK",
    "sqft": "FTK", "sq.ft": "FTK", "sqmm": "MMK", "sq.mm": "MMK",
    # bulk packaging — Rec 20 has no unit code for these; procurement counts them
    # as a number of packages, so they harmonize to EA.
    "roll": "EA", "rolls": "EA", "coil": "EA", "coils": "EA",
    "drum": "EA", "drums": "EA", "can": "EA", "cans": "EA",
    "box": "EA", "boxes": "EA", "bag": "EA", "bags": "EA",
    "bottle": "EA", "bottles": "EA", "packet": "EA", "pkt": "EA", "pack": "EA",
}


def _key(raw: str) -> str:
    return raw.strip().lower().replace(" ", "").rstrip(".") or raw.strip().lower()


def resolve_uom(raw: str | None) -> dict | None:
    """Map a free-text unit onto its Rec 20 entry.

    Returns ``{"code", "name", "symbol", "quantity", "input", "matched"}`` or
    ``None`` when ``raw`` is empty. ``matched`` is ``False`` when we fall back to
    echoing the cleaned input (no standard code found).
    """
    if not raw or not raw.strip():
        return None

    registry = _registry()
    cleaned = raw.strip()
    lowered = cleaned.lower()
    compact = _key(cleaned)

    # CPSE-vocabulary aliases win first: "MT" means tonne here, not the registry's
    # "MT" entry; "KGS" means kilogram, not kilogram-per-second.
    code = None
    if compact in _ALIASES:
        code = _ALIASES[compact]
    elif lowered in _ALIASES:
        code = _ALIASES[lowered]
    elif cleaned.upper() in registry:
        code = cleaned.upper()
    else:
        for row in registry.values():
            if row["name"].lower() == lowered or (
                row["symbol"] and row["symbol"].lower() == lowered
            ):
                code = row["code"]
                break

    if code and code in registry:
        row = registry[code]
        return {
            "code": row["code"],
            "name": row["name"],
            "symbol": row["symbol"],
            "quantity": row["quantity"],
            "input": cleaned,
            "matched": True,
        }

    return {
        "code": None,
        "name": lowered,
        "symbol": "",
        "quantity": "",
        "input": cleaned,
        "matched": False,
    }


def canonical_uom(raw: str | None) -> str | None:
    """Just the canonical unit name (back-compatible with the old string API)."""
    resolved = resolve_uom(raw)
    return resolved["name"] if resolved else None


def uom_code(raw: str | None) -> str | None:
    resolved = resolve_uom(raw)
    return resolved["code"] if resolved else None
