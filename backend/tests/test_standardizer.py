from app.services.matcher import compare_materials
from app.services.standardizer import (
    extract_attributes,
    normalize_text,
    normalize_uom,
)


def test_uom_canonicalisation():
    assert normalize_uom("NOS") == "each"
    assert normalize_uom("No.") == "each"
    assert normalize_uom("PC") == "each"
    assert normalize_uom("RMT") == "metre"
    assert normalize_uom("MTR") == "metre"
    assert normalize_uom("SET") == "set"
    assert normalize_uom(None) is None


def test_matching_notes_equivalent_uom():
    def brg(desc, uom):
        return {
            "normalized_description": normalize_text(desc),
            "extracted_attributes": extract_attributes(
                desc, material_family="Bearing"
            ),
            "material_family": "Bearing",
            "manufacturer_part_no": None,
            "uom": uom,
        }

    a = brg("Ball bearing deep groove 6205 ZZ", "NOS")
    b = brg("Bearing 6205-2Z deep groove", "EA")
    score, explanation = compare_materials(a, b)
    assert any("same unit of measure: each" in line for line in explanation)
    assert score >= 0.6


def test_sqmm_alias_normalisation():
    assert "sq mm" in normalize_text("25 SQMM cable")
    assert "sq mm" in normalize_text("25 sq.mm cable")


def test_pipe_template_extracts_bore_schedule_material():
    attrs = extract_attributes(
        "PIPE SEAMLESS CS 100NB SCH40 ASTM A106 GR B", material_family="Pipe"
    )
    assert attrs["nominal_bore_mm"] == 100.0
    assert attrs["schedule"] == "sch40"
    assert attrs["pipe_material"] == "cs"


def test_motor_conflict_is_penalised():
    def motor(desc):
        return {
            "normalized_description": normalize_text(desc),
            "extracted_attributes": extract_attributes(
                desc, material_family="Motor"
            ),
            "material_family": "Motor",
            "manufacturer_part_no": None,
        }

    a = motor("Motor 3ph induction 30 kW 4 pole 415V IE3")
    b = motor("Motor 3ph induction 5.5 kW 4 pole 415V IE2")
    score, explanation = compare_materials(a, b)
    assert any("conflict in power_kw" in line for line in explanation)
    assert score < 0.6
