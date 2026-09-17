from app.services.standardizer import normalize_text, extract_attributes
from app.services.matcher import compare_materials


def test_bearing_alias_normalization():
    assert "6205 zz" in normalize_text("Bearing 6205-2Z")


def test_similar_bearings_score_high():
    a = {
        "normalized_description": normalize_text("BRG 6205 ZZ bearing"),
        "extracted_attributes": extract_attributes("BRG 6205 ZZ bearing"),
        "manufacturer_part_no": None,
    }
    b = {
        "normalized_description": normalize_text("Bearing 6205-2Z"),
        "extracted_attributes": extract_attributes("Bearing 6205-2Z"),
        "manufacturer_part_no": None,
    }
    score, explanation = compare_materials(a, b)
    assert score >= 0.6
    assert any("same series" in x for x in explanation)
