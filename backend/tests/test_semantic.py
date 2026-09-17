from app.services.semantic import SemanticModel
from app.services.standardizer import normalize_text
from app.services.matcher import compare_materials

CORPUS = [
    "deep groove ball bearing 6205 zz 25 x 52 x 15 mm",
    "ball bearing deep groove 6205 2z 25x52x15mm",
    "gate valve 50 nominal bore class 150 raised face carbon steel",
    "power cable 11 kv 3 core 240 sq mm aluminium xlpe armoured",
]


def test_same_item_scores_higher_than_different():
    m = SemanticModel(CORPUS)
    same = m.similarity(CORPUS[0], CORPUS[1])
    diff = m.similarity(CORPUS[0], CORPUS[2])
    assert same > diff
    assert 0.0 <= diff <= same <= 1.0


def test_abbreviation_expansion_lifts_match():
    left = {
        "normalized_description": normalize_text("DGBB 6205 ZZ 25X52X15"),
        "material_family": "Bearing", "extracted_attributes": {"series": "6205"},
    }
    right = {
        "normalized_description": normalize_text(
            "Deep groove ball bearing 6205 2Z 25x52x15 mm"
        ),
        "material_family": "Bearing", "extracted_attributes": {"series": "6205"},
    }
    model = SemanticModel([left["normalized_description"], right["normalized_description"]])
    score, _ = compare_materials(left, right, model)
    assert score >= 0.6


def test_semantic_never_lowers_score():
    left = {"normalized_description": "gate valve 50 class 150",
            "material_family": "Valve", "extracted_attributes": {}}
    right = {"normalized_description": "gate valve 50 class 150",
             "material_family": "Valve", "extracted_attributes": {}}
    model = SemanticModel([left["normalized_description"], right["normalized_description"]])
    with_sem, _ = compare_materials(left, right, model)
    without, _ = compare_materials(left, right)
    assert with_sem >= without
