"""Classify a material into a Federal Supply Classification (FSC) class.

FSC is the 2-digit group / 4-digit class backbone of the NATO Codification
System. Grounding the National Material Code in FSC (``NMC-<FSC>-<seq>``) gives
every harmonized identity a real, external commodity anchor instead of an opaque
running number.

The classifier is deliberately rule-based and explainable: a steward can see
exactly which term drove the class.
"""

from functools import lru_cache

from .reference_data import load_csv
from .standardizer import normalize_text

UNCLASSIFIED_FSC = "9999"


@lru_cache(maxsize=1)
def _class_titles() -> dict[str, str]:
    titles = {row["fsc"]: row["title"] for row in load_csv("fsc_classes.csv")}
    titles[UNCLASSIFIED_FSC] = "Unclassified — pending steward classification"
    return titles


@lru_cache(maxsize=1)
def _group_titles() -> dict[str, str]:
    groups = {row["fsg"]: row["title"] for row in load_csv("fsc_groups.csv")}
    groups["99"] = "Miscellaneous"
    return groups


# (fsc, family hint, keyword phrases). Order matters: earlier rules are more
# specific and win. All matching is on normalized (lower-cased) text.
_RULES: list[tuple[str, str | None, tuple[str, ...]]] = [
    # --- tyres (FSG 26) ---
    ("2610", None, ("tyre", "tire", " otr ", "off the road tyre", "off the road tire")),
    # --- bearings (FSG 31) ---
    ("3130", "bearing", ("pillow block", "plummer block", "plumber block", "mounted bearing", "bearing unit", "take up unit")),
    ("3120", "bearing", ("bush bearing", "bushing bearing", "plain bearing", "bronze bearing", "sleeve bearing", "journal bearing")),
    ("3110", "bearing", ("ball bearing", "roller bearing", "deep groove", "taper roller", "tapered roller", "spherical roller", "angular contact", "needle bearing", "thrust bearing", "antifriction")),
    # --- gaskets / seals (FSG 53) ---
    ("5331", "seal", ("o-ring", "o ring", "oring")),
    ("5330", "gasket", ("gasket", "spiral wound", "packing rope", "gland packing", "ptfe packing", "graphite packing", "caf ")),
    ("5330", "seal", ("oil seal", "mechanical seal", "lip seal", "shaft seal")),
    # --- fasteners (FSG 53). Order: studs & nuts before the generic " bolt " catch. ---
    ("5307", "fastener", ("stud bolt", "studbolt", "threaded stud", "double end stud", "double ended stud", " stud ")),
    ("5310", "fastener", ("hex nut", "hexagon nut", "lock nut", "nyloc", "flat washer", "spring washer", "plain washer", " washer", " nut ")),
    ("5306", "fastener", ("hex bolt", "hexagon bolt", "hex head bolt", "hexagon head", "foundation bolt", "anchor bolt", "u bolt", "eye bolt", " bolt ")),
    ("5305", "fastener", ("cap screw", "machine screw", "set screw", "socket head", "self tapping", "grub screw", " screw ")),
    ("5315", "fastener", ("split pin", "cotter pin", "dowel pin", "taper pin", "machine key", "parallel key", "gib head key")),
    ("5320", "fastener", ("rivet", "pop rivet", "blind rivet")),
    ("5360", None, ("compression spring", "tension spring", "helical spring", "disc spring", "belleville", "leaf spring")),
    # --- valves (FSG 48). Checked before pipe fittings so "globe valve ... socket
    #     weld" is a valve, not a weld fitting. ---
    ("4810", "valve", ("motor operated", "motorised", "motorized", "actuated valve", "solenoid valve", "control valve", "pneumatic valve", "power operated", "electro hydraulic")),
    ("4820", "valve", ("gate valve", "globe valve", "ball valve", "check valve", "butterfly valve", "needle valve", "plug valve", "safety valve", "relief valve", "non return valve", "valve gate", "valve globe", "valve ball", " valve ")),
    # --- pipe, hose, fittings (FSG 47) ---
    ("4720", None, ("hose", "flexible tubing", "flexible hose", "braided hose", "hydraulic hose")),
    ("4730", "pipe", ("pipe fitting", "elbow", "reducer", "tee ", "coupling pipe", "pipe coupling", "nipple", "flange", "union", "bush pipe", "socket weld fitting", "weld fitting", "buttweld fitting", "bend ")),
    ("4710", "pipe", ("seamless pipe", "erw pipe", "welded pipe", " pipe ", "steel pipe", "gi pipe", "ms pipe", "tube ", "rigid tubing", "casing pipe")),
    # --- electrical wire & power (FSG 61) ---
    ("6105", "motor", ("induction motor", "electric motor", "squirrel cage", " motor ", "slip ring motor", "tefc motor")),
    ("6120", None, ("power transformer", "distribution transformer", "current transformer", "potential transformer", " transformer")),
    ("6115", None, ("diesel generator", "generator set", " genset", "alternator")),
    ("6110", None, ("switchgear", "contactor", "starter panel", "mcc panel", "control panel", "vfd", "variable frequency drive", "soft starter", "dol starter")),
    ("6145", "cable", ("power cable", "control cable", "instrumentation cable", "xlpe cable", "pvc cable", "armoured cable", "armored cable", "flexible cable", "building wire", "house wire", "acsr", "aaac", "overhead conductor", "earthing conductor", " cable ", " wire ")),
    ("6150", None, ("cable gland", "cable tray", "cable lug", "junction box", "bus bar", "busbar")),
    # --- electronic components (FSG 59) ---
    ("5925", None, ("circuit breaker", "mccb", "mcb", "acb", "vcb", "elcb", "rccb")),
    ("5930", None, ("selector switch", "limit switch", "push button", "toggle switch", "proximity switch")),
    ("5935", None, ("connector", "terminal block", "plug and socket")),
    ("5945", None, ("relay", "timer relay", "overload relay", "auxiliary relay")),
    ("5910", None, ("capacitor", "power capacitor", "apfc")),
    # --- instruments (FSG 66) ---
    ("6685", "instrument", ("pressure gauge", "pressure transmitter", "temperature gauge", "temperature transmitter", "thermocouple", "rtd ", "pt100", "thermometer", "humidity")),
    ("6680", "instrument", ("flow meter", "flowmeter", "flow transmitter", "level transmitter", "level gauge", "level switch", "rotameter", "orifice")),
    ("6625", "instrument", ("multimeter", "clamp meter", "insulation tester", "megger", "energy meter", "power analyzer")),
    ("6695", "instrument", ("transmitter", "indicator", "controller", "gauge")),
    # --- pumps & compressors (FSG 43) ---
    ("4320", None, ("centrifugal pump", "submersible pump", "gear pump", "screw pump", "dosing pump", "vacuum pump", " pump ")),
    ("4310", None, ("air compressor", "reciprocating compressor", "screw compressor", " compressor")),
    ("4330", "filter", ("cartridge filter", "bag filter", "strainer", "process filter", "filter element", " filter ")),
    # --- power transmission (FSG 30) ---
    ("3030", None, ("v-belt", "v belt", "timing belt", "drive belt", "conveyor belt")),
    ("3020", None, ("sprocket", "chain sprocket", "roller chain", "gear wheel", "spur gear", "pulley", "coupling flexible", "gear coupling", "tyre coupling")),
    # --- metal stock (FSG 95) ---
    ("9515", "plate", ("ms plate", "steel plate", "chequered plate", "checkered plate", "steel sheet", "gi sheet", "ss sheet", "strip ", " plate ", " sheet ")),
    ("9510", "plate", ("round bar", "square bar", "flat bar", "steel rod", "tmt bar", "tmt", "reinforcement bar", "rebar", "bright bar", " billet")),
    ("9520", "plate", ("angle iron", "ms angle", "channel ", "ismc", "isa ", "i beam", "ib ", "h beam", "joist", "structural steel")),
    # --- fuels, oils, greases (FSG 91) ---
    ("9150", "grease", ("grease", "lubricating oil", "lube oil", "hydraulic oil", "gear oil", "turbine oil", "cutting oil", "coolant oil", "compressor oil", "transformer oil")),
    ("9140", None, ("diesel", "hsd", "furnace oil", "fuel oil", "ldo ")),
    # --- welding (FSG 34) ---
    ("3439", None, ("welding electrode", "welding rod", "filler wire", "flux cored wire", "mig wire", "tig filler", "e7018", "e6013")),
    # --- refractories & nonmetallic (FSG 93) ---
    ("9350", None, ("refractory brick", "fire brick", "firebrick", "castable refractory", "high alumina brick", "insulating brick", "ramming mass")),
    ("9330", None, ("rubber lining", "rubber sheet", "mill liner", "rubber liner", "nylon sheet", "hdpe sheet", "ptfe sheet")),
    # --- electrical insulators (FSG 59) ---
    ("5970", None, ("disc insulator", "pin insulator", "post insulator", "bushing insulator", "insulator string", "epoxy bushing")),
    # --- chemicals (FSG 68) ---
    ("6830", None, ("oxygen gas", "nitrogen gas", "argon", "acetylene", "co2 gas", "lpg cylinder", "compressed gas")),
    ("6810", None, ("caustic soda", "sulphuric acid", "hydrochloric acid", "sodium hypochlorite", "methanol", "mercaptan", "odorant", "corrosion inhibitor", "activated carbon", "ion exchange resin", "chemical ")),
    # --- mining / earthmoving wear parts (FSG 38) ---
    ("3820", None, ("rock bit", "tricone", "drill bit", "dth hammer", "drill rod", "bucket tooth", "tooth point", "get adapter", "ground engaging", "cutting edge", "ripper tip")),
    # --- paints & adhesives (FSG 80) ---
    ("8010", None, ("enamel paint", "primer", "epoxy paint", "zinc primer", "red oxide", " paint ")),
    ("8040", None, ("adhesive", "sealant", "loctite", "araldite", "silicone sealant", "thread sealant")),
    # --- lighting (FSG 62) ---
    ("6210", None, ("light fitting", "led fixture", "flood light", "street light", "tube light", "high bay", "well glass")),
    ("6240", None, ("led lamp", "led bulb", "halogen lamp", "sodium vapour", "metal halide", "fluorescent tube")),
    # --- hand / measuring tools (FSG 51 / 52) ---
    ("5120", None, ("spanner", "wrench", "screwdriver", "plier", "hammer", "chisel", "hex key", "allen key")),
    ("5210", None, ("vernier caliper", "micrometer", "measuring tape", "dial gauge", "feeler gauge", "try square")),
]

_FAMILY_TO_FSC = {
    "bearing": "3110",
    "cable": "6145",
    "valve": "4820",
    "fastener": "5306",
    "pipe": "4710",
    "motor": "6105",
    "plate": "9515",
    "gasket": "5330",
    "seal": "5330",
    "hose": "4720",
    "filter": "4330",
    "grease": "9150",
    "instrument": "6695",
    "electrical": "6150",
}


def _pad(text: str) -> str:
    return f" {text} "


def fsc_meta(fsc: str | None) -> dict:
    """Expand a stored FSC code into ``{fsc, fsc_title, fsg, fsg_title}``."""
    if not fsc:
        fsc = UNCLASSIFIED_FSC
    fsg = fsc[:2]
    return {
        "fsc": fsc,
        "fsc_title": _class_titles().get(fsc, "Unknown class"),
        "fsg": fsg,
        "fsg_title": _group_titles().get(fsg, "Unknown group"),
    }


def classify(
    description: str,
    material_family: str | None = None,
    normalized: str | None = None,
) -> dict:
    """Return ``{fsc, fsc_title, fsg, fsg_title, confidence, basis}``."""
    text = _pad(normalized if normalized is not None else normalize_text(description))
    fam = (material_family or "").strip().lower() or None

    hit_fsc: str | None = None
    basis = ""
    confidence = "low"

    for fsc, fam_hint, phrases in _RULES:
        for phrase in phrases:
            if phrase in text:
                hit_fsc = fsc
                basis = f"matched term “{phrase.strip()}”"
                # family agreement lifts confidence
                if fam_hint and fam and (fam_hint in fam or fam in fam_hint):
                    confidence = "high"
                    basis += f" + declared family “{material_family}”"
                else:
                    confidence = "medium"
                break
        if hit_fsc:
            break

    if hit_fsc is None and fam:
        for key, fsc in _FAMILY_TO_FSC.items():
            if key in fam:
                hit_fsc = fsc
                basis = f"declared family “{material_family}”"
                confidence = "medium"
                break

    if hit_fsc is None:
        hit_fsc = UNCLASSIFIED_FSC
        basis = "no classifying term found"
        confidence = "none"

    fsg = hit_fsc[:2]
    return {
        "fsc": hit_fsc,
        "fsc_title": _class_titles().get(hit_fsc, "Unknown class"),
        "fsg": fsg,
        "fsg_title": _group_titles().get(fsg, "Unknown group"),
        "confidence": confidence,
        "basis": basis,
    }
