from app.services.attribute_templates import critical_keys, resolve_family
from app.services.matcher import compare_materials
from app.services.standardizer import extract_attributes


def test_family_alias_resolves():
    assert resolve_family("Bearings") == "bearing"
    assert resolve_family("BRG") == "bearing"
    assert resolve_family("Power Cable") == "cable"
    assert resolve_family(None) is None
    assert resolve_family("mystery") is None


def test_cable_attributes_extracted():
    attrs = extract_attributes(
        "3 core 25 sq mm cable 1.1KV", material_family="Cable"
    )
    assert attrs["cores"] == 3
    assert attrs["conductor_csa_sqmm"] == 25.0
    assert attrs["voltage"] == 1.1


def test_valve_attributes_extracted():
    attrs = extract_attributes(
        "Gate valve 50 mm class 150 carbon steel", material_family="Valve"
    )
    assert attrs["valve_type"] == "gate"
    assert attrs["nominal_bore_mm"] == 50.0
    assert attrs["pressure_rating"] == "class 150"


def test_unknown_family_falls_back_to_generic_extractors():
    attrs = extract_attributes("BRG 6205 ZZ bearing")
    assert attrs["series"] == "6205"
    assert attrs["closure"] == "zz"


def test_critical_keys_are_family_scoped():
    assert "voltage" in critical_keys("Cable")
    assert "series" not in critical_keys("Cable")
    assert "series" in critical_keys(None)  # union fallback


def test_conflicting_cable_voltage_is_penalised():
    def cable(desc):
        return {
            "normalized_description": desc,
            "extracted_attributes": extract_attributes(
                desc, material_family="Cable"
            ),
            "material_family": "Cable",
            "manufacturer_part_no": None,
        }

    a = cable("power cable 1.1 kv 3c x 25 sq mm")
    b = cable("power cable 11 kv 3c x 25 sq mm")

    score, explanation = compare_materials(a, b)

    assert any("critical" in line.lower() for line in explanation)
    assert score < 0.6
